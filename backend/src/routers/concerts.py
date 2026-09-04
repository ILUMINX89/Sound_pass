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
    )

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
