"""Descarga autenticada de boletas individuales en PDF."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from src import models, security
from src.database import get_db
from src.ticket_pdf import build_tickets_pdf

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get(
    "/{order_id}/tickets/pdf",
    response_class=Response,
    summary="Descargar las boletas de una orden en PDF",
    description=(
        "Requiere autenticación y ser propietario de la orden. "
        "Emite los códigos individuales en la primera descarga y "
        "los conserva en las siguientes. No registra el ingreso al evento."
    ),
    responses={
        200: {
            "description": "PDF con una página por entrada.",
            "content": {
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        },
        401: {"description": "Autenticación requerida o inválida."},
        404: {"description": "Orden inexistente o de otro usuario."},
        409: {"description": "La orden no está confirmada."},
    },
)
def download_order_tickets_pdf(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    try:
        # Bloquear solo la orden, sin joins, para serializar la emisión.
        order = (
            db.query(models.Order)
            .filter(
                models.Order.id == order_id,
                models.Order.user_id == current_user.id,
            )
            .with_for_update()
            .populate_existing()
            .first()
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Orden no encontrada",
            )

        if order.status != "confirmed":
            raise HTTPException(
                status_code=409,
                detail="Solo se pueden descargar órdenes confirmadas",
            )

        items = (
            db.query(models.OrderItem)
            .options(joinedload(models.OrderItem.ticket_type))
            .filter(models.OrderItem.order_id == order.id)
            .order_by(models.OrderItem.id)
            .all()
        )

        if not items:
            raise HTTPException(
                status_code=409,
                detail="La orden no contiene entradas",
            )

        issued = (
            db.query(models.IssuedTicket)
            .join(
                models.OrderItem,
                models.OrderItem.id == models.IssuedTicket.order_item_id,
            )
            .filter(models.OrderItem.order_id == order.id)
            .all()
        )

        existing = {
            (ticket.order_item_id, ticket.sequence_number): ticket
            for ticket in issued
        }

        expected = {
            (item.id, number)
            for item in items
            for number in range(1, item.quantity + 1)
        }

        if any(item.quantity <= 0 for item in items):
            raise HTTPException(
                status_code=409,
                detail="La orden contiene cantidades inválidas",
            )

        if set(existing) - expected:
            raise HTTPException(
                status_code=409,
                detail="Las boletas emitidas no coinciden con la orden",
            )

        pdf_tickets = []

        for item in items:
            for number in range(1, item.quantity + 1):
                key = (item.id, number)
                ticket = existing.get(key)

                if ticket is None:
                    ticket = models.IssuedTicket(
                        order_item_id=item.id,
                        sequence_number=number,
                        public_code=secrets.token_urlsafe(32),
                    )
                    db.add(ticket)
                    existing[key] = ticket

                pdf_tickets.append(
                    {
                        "public_code": ticket.public_code,
                        "category": item.ticket_type.name,
                    }
                )

        # Verificar restricciones únicas antes de construir el documento.
        db.flush()

        concert = order.concert
        venue = concert.venue

        pdf = build_tickets_pdf(
            order_code=order.order_code,
            buyer_name=current_user.full_name,
            concert={
                "artist": concert.artist,
                "tour_name": concert.tour_name,
                "event_date": concert.event_date,
                "event_time": concert.event_time,
                "venue_name": venue.name,
                "city": venue.city,
                "address": venue.address,
            },
            tickets=pdf_tickets,
        )

        # Nombre seguro que no depende de texto introducido por el usuario.
        filename = f"soundpass-orden-{order.id}.pdf"

        # Guardar los códigos antes de devolver el PDF.
        db.commit()

    except Exception:
        db.rollback()
        raise

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
