import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from src import models, schemas, security
from src.database import get_db

router = APIRouter(prefix="/orders", tags=["orders"])

SERVICE_FEE_PER_TICKET = 6000


def _generate_order_code(db: Session) -> str:
    while True:
        code = f"SP-{random.randint(100000, 999999)}"
        if not db.query(models.Order).filter(models.Order.order_code == code).first():
            return code


def _serialize_order(order: models.Order) -> schemas.OrderOut:
    price_from = min((t.price for t in order.concert.ticket_types), default=0)
    return schemas.OrderOut(
        id=order.id,
        order_code=order.order_code,
        status=order.status,
        payment_method=order.payment_method,
        subtotal=order.subtotal,
        service_fee=order.service_fee,
        total=order.total,
        created_at=order.created_at,
        cancelled_at=order.cancelled_at,
        concert=schemas.ConcertListOut(
            id=order.concert.id,
            artist=order.concert.artist,
            tour_name=order.concert.tour_name,
            genre=order.concert.genre,
            event_date=order.concert.event_date,
            event_time=order.concert.event_time,
            venue=order.concert.venue,
            price_from=price_from,
        ),
        items=[
            schemas.OrderItemOut(
                ticket_type_name=item.ticket_type.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
    )


@router.post("", response_model=schemas.OrderOut, status_code=201)
def create_order(
    payload: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    concert = db.get(models.Concert, payload.concert_id)
    if not concert:
        raise HTTPException(status_code=404, detail="Concierto no encontrado")

    subtotal = 0
    total_qty = 0
    order_items: list[models.OrderItem] = []

    for item in payload.items:
        ticket_type = db.get(models.TicketType, item.ticket_type_id)
        if not ticket_type or ticket_type.concert_id != concert.id:
            raise HTTPException(status_code=400, detail="Tipo de boleto inválido para este concierto")
        if item.quantity > ticket_type.quantity_available:
            raise HTTPException(
                status_code=409,
                detail=f"No hay suficientes boletos disponibles de tipo {ticket_type.name}",
            )
        subtotal += float(ticket_type.price) * item.quantity
        total_qty += item.quantity
        order_items.append(
            models.OrderItem(
                ticket_type_id=ticket_type.id,
                quantity=item.quantity,
                unit_price=ticket_type.price,
            )
        )
        ticket_type.quantity_available -= item.quantity

    service_fee = SERVICE_FEE_PER_TICKET * total_qty
    total = subtotal + service_fee

    order = models.Order(
        order_code=_generate_order_code(db),
        user_id=current_user.id,
        concert_id=concert.id,
        status="confirmed",
        payment_method=payload.payment_method,
        subtotal=subtotal,
        service_fee=service_fee,
        total=total,
        items=order_items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    order = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.concert).joinedload(models.Concert.venue),
            joinedload(models.Order.concert).joinedload(models.Concert.ticket_types),
            joinedload(models.Order.items).joinedload(models.OrderItem.ticket_type),
        )
        .filter(models.Order.id == order.id)
        .first()
    )
    return _serialize_order(order)


@router.get("/me", response_model=list[schemas.OrderOut])
def my_orders(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    """Mis boletos — próximos / historial, filtered by ?status_filter=confirmed|cancelled"""
    query = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.concert).joinedload(models.Concert.venue),
            joinedload(models.Order.concert).joinedload(models.Concert.ticket_types),
            joinedload(models.Order.items).joinedload(models.OrderItem.ticket_type),
        )
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
    )
    if status_filter:
        query = query.filter(models.Order.status == status_filter)

    return [_serialize_order(o) for o in query.all()]


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    order = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.concert).joinedload(models.Concert.venue),
            joinedload(models.Order.concert).joinedload(models.Concert.ticket_types),
            joinedload(models.Order.items).joinedload(models.OrderItem.ticket_type),
        )
        .filter(models.Order.id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return _serialize_order(order)


@router.post("/{order_id}/cancel", response_model=schemas.OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user),
):
    order = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.concert).joinedload(models.Concert.venue),
            joinedload(models.Order.concert).joinedload(models.Concert.ticket_types),
            joinedload(models.Order.items).joinedload(models.OrderItem.ticket_type),
        )
        .filter(models.Order.id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="Esta compra ya fue cancelada")

    # release the reserved tickets back into inventory
    for item in order.items:
        item.ticket_type.quantity_available += item.quantity

    order.status = "cancelled"
    order.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return _serialize_order(order)
