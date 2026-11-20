"""Run once or run one periodic importer. PostgreSQL locks cover all processes."""
import argparse
import logging
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config import settings
from src.database import engine
from src.models import Concert, Venue, CatalogSync
from src.ticketmaster import discover_events, map_event, TicketmasterError

log = logging.getLogger(__name__)
LOCK = 7294102

def apply_snapshot(db, mapped, seen, country, start, end, now):
    existing = {c.external_id: c for c in db.query(Concert).filter(Concert.source == "ticketmaster")}
    for data in mapped:
        data = dict(data)
        venue_data = data.pop("venue")
        external_venue = venue_data["external_id"]
        venue = db.query(Venue).filter(Venue.external_id == external_venue).first() if external_venue else None
        c = existing.get(data["external_id"])
        if venue is None:
            venue = c.venue if c and not external_venue and not c.venue.external_id else Venue()
            db.add(venue)
        for key, value in venue_data.items():
            setattr(venue, key, value)
        if c is None:
            c = Concert(source="ticketmaster")
            db.add(c)
        for key, value in data.items():
            setattr(c, key, value)
        c.catalog_scope = country
        c.venue = venue
        c.catalog_status = "active"
        c.synced_at = now
        c.missing_count = 0
        db.flush()
    published_ids = {row["external_id"] for row in mapped}
    for external_id, c in existing.items():
        # Scope absence to the country and inclusive local-date coverage; never touch history.
        from zoneinfo import ZoneInfo
        from src.catalog import aware
        local_day = datetime.combine(c.event_date, datetime.min.time(), ZoneInfo(c.timezone or "America/Bogota"))
        in_window = (start <= aware(c.starts_at) <= end) if c.starts_at else (start <= local_day and local_day + timedelta(days=1) <= end)
        if c.catalog_scope == country and external_id not in published_ids and in_window:
            if external_id in seen:  # explicit cancellation, TBA, or unverifiable artist
                c.catalog_status = "inactive"
            else:
                c.missing_count += 1
                if c.missing_count >= 2:
                    c.catalog_status = "inactive"
    state = db.get(CatalogSync, country)
    if state is None:
        state = CatalogSync(country_code=country)
        db.add(state)
    state.last_success_at, state.window_start, state.window_end = now, start, end
    state.event_count = len(mapped)

def sync_once():
    if not settings.ticketmaster_api_key.strip():
        log.warning("catalog status=unavailable reason=missing_key")
        return False
    began = time.monotonic()
    country = settings.catalog_key
    now = datetime.now(timezone.utc)
    # Start at Bogota midnight to retain events with an unknown hour throughout today.
    from zoneinfo import ZoneInfo
    start = now.astimezone(ZoneInfo("America/Bogota")).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    end = start + timedelta(days=settings.ticketmaster_window_days)
    with engine.connect() as connection:
        locked = connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK}).scalar()
        connection.commit()  # session lock persists; no write transaction while downloading
        if not locked:
            log.info("catalog cycle=skipped reason=locked")
            return False
        try:
            if settings.ticketmaster_scope == "artist_origin":
                from src.artist_origins import discover_selected_artists
                events, mapped, artist_count = discover_selected_artists(start, end)
                log.info("catalog scope=%s verified_artists=%d", country, artist_count)
            else:
                events = discover_events(country, start, end)
                mapped = [row for event in events if (row := map_event(event, country)) is not None]
            with Session(bind=connection) as db, db.begin():
                apply_snapshot(db, mapped, {e["id"] for e in events}, country, start, end, now)
            log.info("catalog cycle=success scope=%s received=%d published=%d omitted=%d priced=%d seconds=%.2f", country, len(events), len(mapped), len(events)-len(mapped), sum(row["provider_price"] is not None for row in mapped), time.monotonic()-began)
            return True
        except Exception as error:
            connection.rollback()
            log.warning("catalog cycle=failed kind=%s provider_http=%s seconds=%.2f", type(error).__name__, getattr(error, "provider_status", None), time.monotonic()-began)
            return False
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
            connection.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.once:
        raise SystemExit(0 if sync_once() else 1)
    while True:
        try:
            sync_once()
        except Exception as error:
            log.warning("catalog cycle=failed kind=%s", type(error).__name__)
        time.sleep(settings.ticketmaster_sync_interval_seconds)

if __name__ == "__main__":
    main()
