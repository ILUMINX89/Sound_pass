from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src import models, schemas
from src.database import get_db
from src.catalog import query_catalog, serialize, public_detail, sync_status
from src.config import settings
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
    rows, _ = query_catalog(db, city=city, genre=genre, sort=sort)
    return [serialize(c) for c in rows]


# ============================================================
# OBTENER UN CONCIERTO
# ============================================================


@router.get("/catalog-status")
def catalog_status(db: Session = Depends(get_db)):
    status, last = sync_status(db)
    return {"status": status, "last_success_at": last, "scope": settings.catalog_key}


@router.get("/{concert_id}", response_model=schemas.ConcertDetailOut)
def get_concert(concert_id: int, db: Session = Depends(get_db)):
    concert = public_detail(db, concert_id)

    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    return {**schemas.ConcertDetailOut.model_validate(concert).model_dump(), "price_from": concert.provider_price}


# ============================================================
# CREAR CONCIERTO
# ============================================================


@router.post("", response_model=schemas.ConcertDetailOut, status_code=201)
def create_concert(payload: schemas.ConcertCreate, db: Session = Depends(get_db)):
    raise HTTPException(403, "La escritura del catalogo esta reservada al importador.")


# ============================================================
# ACTUALIZAR CONCIERTO
# ============================================================


@router.put("/{concert_id}", response_model=schemas.ConcertDetailOut)
def update_concert(
    concert_id: int, payload: schemas.ConcertUpdate, db: Session = Depends(get_db)
):
    raise HTTPException(403, "La escritura del catalogo esta reservada al importador.")


# ============================================================
# ELIMINAR CONCIERTO
# ============================================================


@router.delete("/{concert_id}", status_code=204)
def delete_concert(concert_id: int, db: Session = Depends(get_db)):
    raise HTTPException(403, "La escritura del catalogo esta reservada al importador.")


# ============================================================
# TIPOS DE BOLETO DEL CONCIERTO
# ============================================================


@router.get("/{concert_id}/ticket_types", response_model=list[schemas.TicketTypeOut])
def get_concert_ticket_types(concert_id: int, db: Session = Depends(get_db)):
    """
    Endpoint de relación explícito:
    boletos de un concierto puntual.
    """

    concert = public_detail(db, concert_id)

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
    concert = public_detail(db, concert_id)

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
    if public_detail(db, concert_id) is None:
        raise HTTPException(404, "Concierto no encontrado")
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
    if public_detail(db, concert_id) is None:
        raise HTTPException(404, "Concierto no encontrado")
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
    from src.ticketmaster import TicketmasterError, get_artist_upcoming_events

    if public_detail(db, concert_id) is None:
        raise HTTPException(404, "Concierto no encontrado")
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
    import json
    c = public_detail(db, concert_id)
    credits = json.loads(c.artist_provenance or "[]")
    ids = {credit.get("ticketmaster_id") for credit in credits if credit.get("ticketmaster_id")}
    attraction_id = next(iter(ids)) if len(ids) == 1 else None
    if len(ids) > 1:
        return {"concert_id": concert_id, "artist": artist, "source": "ticketmaster", "status": "ambiguous", "events": [], "message": "El evento tiene varios artistas; consulta una atraccion individual."}
    db.rollback()

    try:
        result = get_artist_upcoming_events(artist, attraction_id)
    except TicketmasterError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={
                "code": error.code,
                "message": error.message,
            },
        ) from None

    return {"concert_id": concert_id, **result}
