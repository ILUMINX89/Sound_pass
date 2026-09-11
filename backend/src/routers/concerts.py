from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src import models, schemas
from src.database import get_db

router = APIRouter(prefix="/concerts", tags=["concerts"])


@router.get("", response_model=list[schemas.ConcertListOut])
def list_concerts(
    city: str | None = Query(default=None, description="Filtrar por ciudad"),
    genre: str | None = Query(default=None, description="Filtrar por género"),
    sort: str = Query(default="date", pattern="^(date|price_asc|price_desc)$"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Concert).options(
        joinedload(models.Concert.venue), joinedload(models.Concert.ticket_types)
    ).filter(models.Concert.event_date >= date.today())

    if city:
        query = query.join(models.Venue).filter(func.lower(models.Venue.city) == city.lower())
    if genre:
        query = query.filter(func.lower(models.Concert.genre) == genre.lower())

    concerts = query.all()

    results = []
    for c in concerts:
        price_from = min((t.price for t in c.ticket_types), default=0)
        results.append(
            schemas.ConcertListOut(
                id=c.id,
                artist=c.artist,
                tour_name=c.tour_name,
                genre=c.genre,
                event_date=c.event_date,
                event_time=c.event_time,
                venue=c.venue,
                price_from=price_from,
            )
        )

    if sort == "date":
        results.sort(key=lambda r: r.event_date)
    elif sort == "price_asc":
        results.sort(key=lambda r: r.price_from)
    elif sort == "price_desc":
        results.sort(key=lambda r: r.price_from, reverse=True)

    return results


@router.get("/{concert_id}", response_model=schemas.ConcertDetailOut)
def get_concert(concert_id: int, db: Session = Depends(get_db)):
    concert = (
        db.query(models.Concert)
        .options(joinedload(models.Concert.venue), joinedload(models.Concert.ticket_types))
        .filter(models.Concert.id == concert_id)
        .first()
    )
    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")
    return concert

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


@router.put("/{concert_id}", response_model=schemas.ConcertDetailOut)
def update_concert(concert_id: int, payload: schemas.ConcertUpdate, db: Session = Depends(get_db)):
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


@router.delete("/{concert_id}", status_code=204)
def delete_concert(concert_id: int, db: Session = Depends(get_db)):
    concert = db.get(models.Concert, concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")
    db.delete(concert)
    db.commit()
    return None


@router.get("/{concert_id}/ticket_types", response_model=list[schemas.TicketTypeOut])
def get_concert_ticket_types(concert_id: int, db: Session = Depends(get_db)):
    """Endpoint de relación explícito: boletos de un concierto puntual."""
    concert = db.get(models.Concert, concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")
    return concert.ticket_types
