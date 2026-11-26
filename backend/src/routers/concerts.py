from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from src import models, schemas, security
from src.artist_origins import artist_catalog, concert_metadata, origin_evidence
from src.ticketmaster import (
    TicketmasterError, add_fallback_price, get_artist_upcoming_events, get_event_detail, get_public_concerts,
    spotify_identity,
)
from src.database import get_db
from src.demo_tickets import INACTIVE_STATUSES, demo_concerts, demo_is_available, demo_ticket_preview
from src.spotify import (
    SpotifyArtistError,
    get_artist_gallery,
    get_artist_player,
)

from fastapi.responses import JSONResponse
from src.wikipedia import get_artist_bio, WikipediaUnavailableError

router = APIRouter(prefix="/concerts", tags=["concerts"])


# ============================================================
# LISTAR CONCIERTOS
# ============================================================


@router.get("", response_model=list[schemas.ConcertListOut])
def list_concerts(
    city: str | None = Query(default=None, description="Filtrar por ciudad"),
    genre: str | None = Query(default=None, description="Filtrar por género"),
    sort: str = Query(default="date", pattern="^(date|price_asc|price_desc)$"),
    db: Session = Depends(get_db),
):
    metadata = concert_metadata(db, "starts_at", "timezone", "catalog_status")
    query = (
        db.query(models.Concert, *metadata)
        .options(
            joinedload(models.Concert.venue),
            joinedload(models.Concert.ticket_types),
        )
        .filter(models.Concert.event_date >= date.today() - timedelta(days=1))
    )

    # Filtrar por ciudad
    if city:
        query = query.join(models.Venue).filter(
            func.lower(models.Venue.city) == city.lower()
        )

    # Filtrar por género
    if genre:
        query = query.filter(func.lower(models.Concert.genre) == genre.lower())

    concerts = query.all()

    results = []

    for c, catalog_source, provider_id, evidence, starts_at, timezone, status in concerts:
        imported = catalog_source == "ticketmaster"
        eligible = [(artist_id, origin) for artist_id, origin in origin_evidence(evidence) if origin.allowed]
        if imported and (not provider_id or not eligible):
            continue
        artist_ids = {artist_id for artist_id, origin in eligible if artist_id
                      and origin.name.casefold() == c.artist.casefold()}

        # ----------------------------------------------------
        # PRECIO MÁS BAJO DEL CONCIERTO
        # ----------------------------------------------------

        price_from = min((t.price for t in c.ticket_types), default=0)
        tickets_available = sum(t.quantity_available for t in c.ticket_types)

        # ----------------------------------------------------
        # RESPUESTA DEL CONCIERTO
        # ----------------------------------------------------

        results.append(
            schemas.ConcertListOut(
                id=c.id,
                external_id=provider_id if imported else None,
                artist_id=next(iter(artist_ids)) if len(artist_ids) == 1 else None,
                starts_at=starts_at,
                timezone=timezone,
                status=status if imported else None,
                artist=c.artist,
                tour_name=c.tour_name,
                genre=c.genre,
                event_date=c.event_date,
                event_time=c.event_time,
                image_url=c.image_url,
                venue=c.venue,
                price_from=price_from,
                tickets_available=tickets_available,
            )
        )

    # --------------------------------------------------------
    # ORDENAMIENTO
    # --------------------------------------------------------

    if sort == "date":
        results.sort(key=lambda r: r.event_date)

    elif sort == "price_asc":
        results.sort(key=lambda r: r.price_from)

    elif sort == "price_desc":
        results.sort(key=lambda r: r.price_from, reverse=True)

    return results


# ============================================================
# OBTENER UN CONCIERTO
# ============================================================



@router.get("/ticketmaster")
def list_ticketmaster_concerts(q: str = Query(default="", max_length=100), db: Session = Depends(get_db)):
    catalog = artist_catalog(db)
    db.rollback()
    try:
        return {"source": "ticketmaster", "events": get_public_concerts(q, catalog)}
    except TicketmasterError as error:
        raise HTTPException(
            status_code=error.status_code, detail=error.message
        ) from None


def _external_event(event_id, db):
    catalog = artist_catalog(db)
    source, external_id, provenance = concert_metadata(db)
    rows = (db.query(provenance).select_from(models.Concert)
            .filter(source == "ticketmaster", external_id == event_id).distinct().all())
    db.rollback()
    imported = [item for (value,) in rows for item in origin_evidence(value)]
    try:
        card, event = get_event_detail(event_id, catalog, imported)
    except TicketmasterError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from None
    return card, event, catalog


@router.get("/ticketmaster/{event_id}")
def get_external_concert(event_id: str, db: Session = Depends(get_db)):
    card, _, _ = _external_event(event_id, db)
    detail = {**add_fallback_price(card), "ticket_types": []}
    if (card.get("status") or "").lower() in INACTIVE_STATUSES:
        return detail

    query, external_id = demo_concerts(db)
    row = query.filter(external_id == event_id).one_or_none()
    if row is not None and demo_is_available(*row):
        concert = row[0]
        detail["checkout_concert_id"] = concert.id
        detail["ticket_types"] = [demo_ticket_preview(concert)]
    return detail


@router.get("/ticketmaster/{event_id}/spotify")
def get_external_spotify(event_id: str, db: Session = Depends(get_db)):
    card, event, catalog = _external_event(event_id, db)
    artist_id = spotify_identity(event, card["artist_id"], catalog)
    return _spotify_player_response(event_id, card["artist"], spotify_id=artist_id)


@router.get("/ticketmaster/{event_id}/artist-bio")
def get_external_artist_bio(event_id: str, db: Session = Depends(get_db)):
    card, _, _ = _external_event(event_id, db)
    return _artist_bio_response(event_id, card["artist"])


@router.get("/ticketmaster/{event_id}/upcoming-events")
def get_external_upcoming_events(event_id: str, db: Session = Depends(get_db)):
    card, _, catalog = _external_event(event_id, db)
    try:
        result = get_artist_upcoming_events(card["artist"], catalog,
                                            artist_id=card["artist_id"], exclude_event=event_id)
    except TicketmasterError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from None
    return {"concert_id": event_id, **result}


@router.get("/{concert_id}", response_model=schemas.ConcertDetailOut)
def get_concert(concert_id: int, db: Session = Depends(get_db)):
    concert = (
        db.query(models.Concert)
        .options(
            joinedload(models.Concert.venue), joinedload(models.Concert.ticket_types)
        )
        .filter(models.Concert.id == concert_id)
        .first()
    )

    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    return concert


# ============================================================
# CREAR CONCIERTO
# ============================================================


@router.post(
    "",
    response_model=schemas.ConcertDetailOut,
    status_code=201,
    dependencies=[Depends(security.require_admin)],
)
def create_concert(payload: schemas.ConcertCreate, db: Session = Depends(get_db)):
    venue = db.get(models.Venue, payload.venue_id)

    if not venue:
        raise HTTPException(status_code=404, detail="Recinto no encontrado")

    concert = models.Concert(**payload.model_dump())

    db.add(concert)

    db.commit()

    db.refresh(concert)

    return concert


# ============================================================
# ACTUALIZAR CONCIERTO
# ============================================================


@router.put(
    "/{concert_id}",
    response_model=schemas.ConcertDetailOut,
    dependencies=[Depends(security.require_admin)],
)
def update_concert(
    concert_id: int, payload: schemas.ConcertUpdate, db: Session = Depends(get_db)
):
    concert = db.get(models.Concert, concert_id)

    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    if payload.venue_id is not None:

        venue = db.get(models.Venue, payload.venue_id)

        if not venue:
            raise HTTPException(status_code=404, detail="Recinto no encontrado")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(concert, field, value)

    db.commit()

    db.refresh(concert)

    return concert


# ============================================================
# ELIMINAR CONCIERTO
# ============================================================


@router.delete(
    "/{concert_id}",
    status_code=204,
    dependencies=[Depends(security.require_admin)],
)
def delete_concert(concert_id: int, db: Session = Depends(get_db)):
    concert = db.get(models.Concert, concert_id)

    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    has_orders = db.query(models.Order.id).filter(models.Order.concert_id == concert_id).first()
    if has_orders:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el concierto tiene órdenes asociadas",
        )

    db.delete(concert)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el concierto tiene datos asociados",
        )

    return None


# ============================================================
# TIPOS DE BOLETO DEL CONCIERTO
# ============================================================


@router.get("/{concert_id}/ticket_types", response_model=list[schemas.TicketTypeOut])
def get_concert_ticket_types(concert_id: int, db: Session = Depends(get_db)):
    """
    Endpoint de relación explícito:
    boletos de un concierto puntual.
    """

    concert = db.get(models.Concert, concert_id)

    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    return concert.ticket_types

# ============================================================
# BIOGRAFÍA DEL ARTISTA — WIKIPEDIA
# ============================================================


@router.get(
    "/{concert_id}/artist-bio",
    response_model=schemas.ArtistBioOut,
    summary="Consultar biografía del artista desde Wikipedia",
    responses={
        404: {"description": "Concierto no encontrado"},
        503: {
            "model": schemas.ArtistBioOut,
            "description": "Wikipedia no está disponible",
        },
    },
)
def get_concert_artist_bio(
    concert_id: int,
    db: Session = Depends(get_db),
):
    """Obtiene una biografía breve en español y el enlace a su fuente.

    Puede devolver los estados ok, not_found o ambiguous.
    Si el proveedor falla, devuelve HTTP 503 y estado unavailable.
    """
    concert = db.get(models.Concert, concert_id)

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concierto no encontrado",
        )

    artist = concert.artist
    db.rollback()
    return _artist_bio_response(concert_id, artist)


def _artist_bio_response(concert_id, artist):
    try:
        result = get_artist_bio(artist)
    except WikipediaUnavailableError:
        payload = {"concert_id": concert_id, "artist": artist, "status": "unavailable",
                   "biography": None, "article_title": None, "article_url": None, "source": "Wikipedia"}
        return JSONResponse(
            status_code=503,
            content=payload,
        )

    return {"concert_id": concert_id, "artist": artist, **result}



# ============================================================
# REPRODUCTOR OFICIAL DE SPOTIFY
# ============================================================

@router.get(
    "/{concert_id}/spotify",
    response_model=schemas.ConcertSpotifyOut,
    summary="Consultar el reproductor de Spotify del artista",
    responses={
        404: {
            "description": "Concierto inexistente",
            "model": schemas.SpotifyErrorOut,
        },
        502: {
            "description": "Respuesta inválida de Spotify",
            "model": schemas.SpotifyErrorOut,
        },
        503: {
            "description": (
                "Spotify sin configurar, acceso rechazado, "
                "límite de consultas o servicio no disponible"
            ),
            "model": schemas.SpotifyErrorOut,
        },
    },
)
def get_concert_spotify(
    concert_id: int,
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.Concert.artist)
        .filter(models.Concert.id == concert_id)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concert_not_found",
                "message": "Concierto no encontrado.",
            },
        )

    artist_name = row[0] or ""

    # Termina la lectura y libera la conexión antes de consultar Spotify.
    db.rollback()

    return _spotify_player_response(concert_id, artist_name)


def _spotify_player_response(concert_id, artist_name, *, spotify_id=None):
    try:
        result = get_artist_player(artist_name, spotify_id=spotify_id)

    except SpotifyArtistError as error:
        headers = None

        if error.retry_after is not None:
            headers = {"Retry-After": error.retry_after}

        raise HTTPException(
            status_code=error.status_code,
            detail={
                "code": error.code,
                "message": error.message,
            },
            headers=headers,
        ) from None

    return {
        "concert_id": concert_id,
        **result,
    }


# ============================================================
# GALERÍA DEL ARTISTA — SPOTIFY
# ============================================================

@router.get(
    "/{concert_id}/artist-gallery",
    response_model=schemas.ConcertArtistGalleryOut,
    summary="Consultar imágenes del artista desde Spotify",
    responses={
        404: {
            "description": "Concierto inexistente",
            "model": schemas.SpotifyErrorOut,
        },
        502: {
            "description": "Respuesta inválida de Spotify",
            "model": schemas.SpotifyErrorOut,
        },
        503: {
            "description": (
                "Spotify sin configurar, acceso rechazado, "
                "límite de consultas o servicio no disponible"
            ),
            "model": schemas.SpotifyErrorOut,
        },
    },
)
def get_concert_artist_gallery(
    concert_id: int,
    db: Session = Depends(get_db),
):
    """Devuelve imágenes que pueden ser la misma foto en distintos tamaños."""
    row = (
        db.query(models.Concert.artist)
        .filter(models.Concert.id == concert_id)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concert_not_found",
                "message": "Concierto no encontrado.",
            },
        )

    artist_name = row[0] or ""

    # Libera la conexión antes de consultar el servicio externo.
    db.rollback()

    try:
        result = get_artist_gallery(artist_name)
    except SpotifyArtistError as error:
        headers = (
            {"Retry-After": error.retry_after}
            if error.retry_after is not None
            else None
        )

        raise HTTPException(
            status_code=error.status_code,
            detail={
                "code": error.code,
                "message": error.message,
            },
            headers=headers,
        ) from None

    return {
        "concert_id": concert_id,
        **result,
    }


# Ticketmaster — próximos conciertos del artista
@router.get(
    "/{concert_id}/upcoming-events",
    response_model=schemas.ConcertUpcomingEventsOut,
    summary="Consultar próximos conciertos del artista en Ticketmaster",
)
def get_concert_upcoming_events(
    concert_id: int,
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.Concert.artist)
        .filter(models.Concert.id == concert_id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concert_not_found",
                "message": "Concierto no encontrado.",
            },
        )

    artist = row[0] or ""
    catalog = artist_catalog(db)
    db.rollback()

    try:
        result = get_artist_upcoming_events(artist, catalog)
    except TicketmasterError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={
                "code": error.code,
                "message": error.message,
            },
        ) from None

    return {"concert_id": concert_id, **result}
