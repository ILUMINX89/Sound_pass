"""Shared public catalog; no provider calls and no HTTP request dependency."""
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from src.models import Concert, CatalogSync
from src.config import settings
from src.schemas import ConcertListOut

BOGOTA = ZoneInfo("America/Bogota")
def utcnow():
    return datetime.now(timezone.utc)

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

def visible(c, now=None):
    now = now or utcnow()
    if c.source != "ticketmaster" or c.catalog_status != "active":
        return False
    local = now.astimezone(ZoneInfo(c.timezone or "America/Bogota"))
    if c.event_time is None:
        return c.event_date >= local.date()
    if c.starts_at:
        return aware(c.starts_at) >= now
    return datetime.combine(c.event_date, c.event_time, local.tzinfo) >= now

def public_detail(db, concert_id, now=None):
    c = db.query(Concert).options(joinedload(Concert.venue), joinedload(Concert.ticket_types)).filter(Concert.id == concert_id).first()
    return c if c and c.catalog_scope == settings.catalog_key and visible(c, now) else None

def query_catalog(db, city=None, genre=None, artist=None, order="nearest_first", sort="date", limit=None, now=None):
    now = now or utcnow()
    query = db.query(Concert).options(joinedload(Concert.venue)).filter(
        Concert.source == "ticketmaster", Concert.catalog_status == "active",
        Concert.catalog_scope == settings.catalog_key)
    if genre:
        query = query.filter(func.lower(Concert.genre) == genre.lower())
    rows = [c for c in query.all() if visible(c, now)
            and (not city or c.venue.city.casefold() == city.casefold())
            and (not artist or artist.casefold() in c.artist.casefold())]
    # Compare confirmed instants across countries using Bogota's clock.
    # Unknown hours use the end of their local day only as an ordering boundary;
    # the stored/displayed hour remains null. They follow confirmed hours per Bogota day.
    def sort_instant(c):
        local = datetime.combine(c.event_date, c.event_time or time.max, ZoneInfo(c.timezone or "America/Bogota"))
        return (aware(c.starts_at) if c.starts_at and c.event_time is not None else local).astimezone(BOGOTA)
    rows.sort(key=lambda c: c.id)
    rows.sort(key=lambda c: sort_instant(c).time(), reverse=order == "latest_first")
    rows.sort(key=lambda c: c.event_time is None)
    rows.sort(key=lambda c: sort_instant(c).date(), reverse=order == "latest_first")
    currencies = {c.currency for c in rows if c.provider_price is not None}
    if sort in {"price_asc", "price_desc"} and len(currencies) <= 1:
        rows.sort(key=lambda c: c.provider_price or 0, reverse=sort == "price_desc")
        rows.sort(key=lambda c: c.provider_price is None)
    total = len(rows)
    return rows[:limit] if limit is not None else rows, total

def serialize(c):
    return ConcertListOut.model_validate({
        **{k: getattr(c, k) for k in ("id", "artist", "tour_name", "genre", "event_date", "event_time", "venue", "image_url", "source", "official_url", "currency", "timezone", "starts_at", "catalog_status")},
        "price_from": c.provider_price, "tickets_available": None})

def sync_status(db, now=None):
    state = db.get(CatalogSync, settings.catalog_key)
    if not state or not state.last_success_at:
        return "unavailable", None
    last = aware(state.last_success_at)
    stale = (now or utcnow()) - last > timedelta(seconds=settings.ticketmaster_sync_interval_seconds * 2)
    return "stale" if stale else "updated", last
