"""Taste questionnaire and "Para ti" recommendations. Every route acts only on the caller's own row."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src import models, schemas, security
from src.artist_origins import artist_catalog
from src.database import get_db
from src.recommendation import engine, loader
from src.ticketmaster import TicketmasterError, get_public_concerts

router = APIRouter(prefix="/preferences", tags=["preferences"])
SCALE_FIELDS = engine.SCALE_FIELDS


def _service():
    service = loader.get_service()
    if service is None:
        raise HTTPException(status_code=503, detail="El recomendador no está disponible.")
    return service


def _out(row):
    if row is None:
        return schemas.PreferencesOut(status="unset")
    scales = None
    if row.scale_danceability is not None:
        scales = schemas.TasteScales(
            danceability=row.scale_danceability, energy=row.scale_energy,
            acousticness=row.scale_acousticness, mood=row.scale_mood)
    return schemas.PreferencesOut(
        status=row.status, genres=list(row.genres or []), artist_ids=list(row.artist_ids or []), scales=scales)


def _row(db, user):
    return db.get(models.UserPreference, user.id)


@router.get("/options")
def options():
    service = loader.get_service()
    if service is None:
        return {"available": False, "genres": [], "artists": [], "scale_fields": list(SCALE_FIELDS)}
    model, store = service.model, service.store
    return {
        "available": True,
        "genres": [{"id": g, "label": store.genres.get(g, g)} for g in sorted(model.genre_prototypes)],
        "artists": [{"id": a.id, "name": a.name} for a in sorted(store.by_id.values(), key=lambda a: a.name.casefold())],
        "scale_fields": list(SCALE_FIELDS),
    }


@router.get("/me", response_model=schemas.PreferencesOut)
def get_preferences(db: Session = Depends(get_db), user: models.User = Depends(security.get_current_user)):
    return _out(_row(db, user))


@router.put("/me", response_model=schemas.PreferencesOut)
def save_preferences(
    payload: schemas.PreferencesIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(security.get_current_user),
):
    service = _service()
    allowed_genres = set(service.model.genre_prototypes)
    if len(set(payload.genres)) != len(payload.genres) or not allowed_genres.issuperset(payload.genres):
        raise HTTPException(status_code=422, detail="Selecciona géneros válidos y sin repetir.")
    if (len(set(payload.artist_ids)) != len(payload.artist_ids)
            or any(artist_id not in service.store.by_id for artist_id in payload.artist_ids)):
        raise HTTPException(status_code=422, detail="Selecciona artistas válidos y sin repetir.")
    if not payload.genres and not payload.artist_ids and payload.scales is None:
        raise HTTPException(status_code=422, detail="Responde al menos una pregunta u omite el formulario.")
    scales = payload.scales
    row = _row(db, user) or models.UserPreference(user_id=user.id)
    row.status = "answered"
    row.genres, row.artist_ids = list(payload.genres), list(payload.artist_ids)
    row.scale_danceability = scales.danceability if scales else None
    row.scale_energy = scales.energy if scales else None
    row.scale_acousticness = scales.acousticness if scales else None
    row.scale_mood = scales.mood if scales else None
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return _out(row)


@router.post("/me/skip", response_model=schemas.PreferencesOut)
def skip_preferences(db: Session = Depends(get_db), user: models.User = Depends(security.get_current_user)):
    """Skipping never erases answers the user already saved."""
    row = _row(db, user)
    if row is None:
        row = models.UserPreference(user_id=user.id, status="skipped", genres=[], artist_ids=[],
                                    updated_at=datetime.now(timezone.utc))
        db.add(row)
        db.commit()
    return _out(row)


def _general(reason):
    return {"available": False, "reason": reason, "profile": None, "model_version": None, "items": []}


@router.get("/me/recommendations")
def recommendations(db: Session = Depends(get_db), user: models.User = Depends(security.get_current_user)):
    row = _row(db, user)
    if row is None or row.status != "answered":
        return _general("no_preferences")
    service = loader.get_service()
    if service is None:
        return _general("model_unavailable")
    prefs = _out(row)
    scales = None
    if prefs.scales:
        scales = [getattr(prefs.scales, field) for field in SCALE_FIELDS]
    vector = engine.user_vector(service.model, service.store, prefs.genres, prefs.artist_ids, scales)
    if vector is None:
        return _general("no_preferences")
    catalog = artist_catalog(db)
    db.rollback()
    try:
        events = get_public_concerts("", catalog)
    except TicketmasterError:
        return _general("catalog_unavailable")
    cluster, items = engine.rank(service.model, service.store, vector, events, date.today())
    if not items:
        return _general("no_matches")
    profile = service.model.clusters[cluster]
    return {
        "available": True, "reason": "ok",
        "profile": {"id": profile["id"], "name": profile["name"], "description": profile["description"]},
        "model_version": service.model.version, "items": items,
    }
