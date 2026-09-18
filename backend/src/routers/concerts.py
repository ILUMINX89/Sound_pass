from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src import models, schemas
from src.database import get_db
from src.spotify import get_artist_image

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

    database_changed = False

    for c in concerts:

        # ----------------------------------------------------
        # IMAGEN DEL ARTISTA
        # ----------------------------------------------------
        #
        # Si no existe imagen o tiene una ruta local vieja
        # como /images/shakira.jpg, buscarla en Spotify.
        #
        needs_spotify_image = (
            not c.image_url
            or c.image_url.startswith("/images/")
            or c.image_url.startswith("images/")
        )

        if needs_spotify_image:
            print(f"Buscando imagen de " f"{c.artist} en Spotify...")

            image = get_artist_image(c.artist)

            if image:
                print(f"Imagen encontrada para " f"{c.artist}: {image}")

                c.image_url = image

                database_changed = True

            else:
                print(f"No se encontró imagen " f"para {c.artist}")

        # ----------------------------------------------------
        # PRECIO MÁS BAJO DEL CONCIERTO
        # ----------------------------------------------------

        price_from = min((t.price for t in c.ticket_types), default=0)

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
            )
        )

    # Guardar las imágenes encontradas en PostgreSQL
    if database_changed:
        db.commit()

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

    # Si tiene una imagen local vieja,
    # intentar reemplazarla también aquí.
    needs_spotify_image = (
        not concert.image_url
        or concert.image_url.startswith("/images/")
        or concert.image_url.startswith("images/")
    )

    if needs_spotify_image:
        print(f"Buscando imagen de " f"{concert.artist} en Spotify...")

        image = get_artist_image(concert.artist)

        if image:
            concert.image_url = image

            db.commit()
            db.refresh(concert)

            print(f"Imagen encontrada para " f"{concert.artist}: {image}")

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

    # Si no se envía una imagen,
    # buscar automáticamente en Spotify.
    if not concert.image_url:
        print(f"Buscando imagen de " f"{concert.artist} en Spotify...")

        image = get_artist_image(concert.artist)

        if image:
            concert.image_url = image

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

    # Si se cambió el artista o la imagen está vacía/local,
    # volver a intentar obtener imagen de Spotify.
    needs_spotify_image = (
        not concert.image_url
        or concert.image_url.startswith("/images/")
        or concert.image_url.startswith("images/")
    )

    if needs_spotify_image:

        image = get_artist_image(concert.artist)

        if image:
            concert.image_url = image

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
