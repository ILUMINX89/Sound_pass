from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src import models, schemas
from src.database import get_db

router = APIRouter(prefix="/venues", tags=["venues"])

@router.get("", response_model=list[schemas.VenueOut])
def list_venues(db: Session = Depends(get_db)):
    return db.query(models.Venue).all()

@router.post("", response_model=schemas.VenueOut, status_code=201)
def create_venue(payload: schemas.VenueCreate, db: Session = Depends(get_db)):
    venue = models.Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue

@router.delete("/{venue_id}", status_code=204)
def delete_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = db.get(models.Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Recinto no encontrado")
    if venue.concerts:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el recinto tiene conciertos asociados",
        )
    db.delete(venue)
    db.commit()
    return None