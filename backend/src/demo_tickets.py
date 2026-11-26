from datetime import date

from sqlalchemy.orm import Session

from src import models, schemas
from src.artist_origins import concert_metadata, origin_evidence

DEMO_TICKET_ID = 0
DEMO_TICKET_NAME = "General (demostración)"
DEMO_TICKET_STOCK = 100
INACTIVE_STATUSES = {"canceled", "cancelled", "postponed", "rescheduled", "inactive"}


def demo_concerts(db: Session):
    source, external_id, provenance, status = concert_metadata(db, "catalog_status")
    return (
        db.query(models.Concert, provenance, status)
        .filter(source == "ticketmaster", external_id.isnot(None))
    ), external_id


def demo_is_available(concert: models.Concert, provenance, status: str | None) -> bool:
    return (
        concert.event_date >= date.today()
        and (status or "").lower() not in INACTIVE_STATUSES
        and any(origin.allowed for _, origin in origin_evidence(provenance))
    )


def demo_ticket_type(concert: models.Concert) -> models.TicketType | None:
    return next((ticket for ticket in concert.ticket_types if ticket.name == DEMO_TICKET_NAME), None)


def demo_ticket_preview(concert: models.Concert) -> schemas.TicketTypeOut:
    ticket = demo_ticket_type(concert)
    return schemas.TicketTypeOut(
        id=DEMO_TICKET_ID,
        name=DEMO_TICKET_NAME,
        price=0,
        quantity_available=ticket.quantity_available if ticket else DEMO_TICKET_STOCK,
    )
