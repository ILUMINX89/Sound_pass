from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src import models, schemas
from src.database import get_db
from src.spotify import SpotifyArtistError, get_artist_player

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
    query = (
        db.query(models.Concert)
        .options(
            joinedload(models.Concert.venue),
            joinedload(models.Concert.ticket_types),
        )
        .filter(models.Concert.event_date >= date.today())
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

    for c in concerts:

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


@router.post("", response_model=schemas.ConcertDetailOut, status_code=201)
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


@router.put("/{concert_id}", response_model=schemas.ConcertDetailOut)
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


@router.delete("/{concert_id}", status_code=204)
def delete_concert(concert_id: int, db: Session = Depends(get_db)):
    concert = db.get(models.Concert, concert_id)

    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    db.delete(concert)

    db.commit()

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

    try:
        result = get_artist_bio(concert.artist)
    except WikipediaUnavailableError:
        payload = schemas.ArtistBioOut(
            concert_id=concert.id,
            artist=concert.artist,
            status="unavailable",
        )
        return JSONResponse(
            status_code=503,
            content=payload.model_dump(mode="json"),
        )

    return schemas.ArtistBioOut(
        concert_id=concert.id,
        artist=concert.artist,
        **result,
    )



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

    try:
        result = get_artist_player(artist_name)

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
    from src.ticketmaster import TicketmasterError, get_artist_upcoming_events

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
    db.rollback()

    try:
        result = get_artist_upcoming_events(artist)
    except TicketmasterError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={
                "code": error.code,
                "message": error.message,
            },
        ) from None

    return {"concert_id": concert_id, **result}
