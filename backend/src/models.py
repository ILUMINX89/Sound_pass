from datetime import datetime, date, time

from sqlalchemy import (
    String, Integer, Numeric, Text, Date, Time, DateTime, ForeignKey, CheckConstraint,
)
from sqlalchemy import UniqueConstraint, func
from sqlalchemy import JSON, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="customer", server_default="customer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    capacity: Mapped[int | None] = mapped_column(Integer)

    concerts: Mapped[list["Concert"]] = relationship(back_populates="venue")


class Concert(Base):
    __tablename__ = "concerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artist: Mapped[str] = mapped_column(String(150), nullable=False)
    tour_name: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_time: Mapped[time] = mapped_column(Time, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    venue: Mapped["Venue"] = relationship(back_populates="concerts")
    ticket_types: Mapped[list["TicketType"]] = relationship(
        back_populates="concert", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="concert")


class TicketType(Base):
    __tablename__ = "ticket_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concert_id: Mapped[int] = mapped_column(ForeignKey("concerts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False)

    concert: Mapped["Concert"] = relationship(back_populates="ticket_types")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="ticket_type")

    __table_args__ = (CheckConstraint("price >= 0", name="ck_ticket_types_price_positive"),)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    concert_id: Mapped[int] = mapped_column(ForeignKey("concerts.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    service_fee: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="orders")
    concert: Mapped["Concert"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_orders_status"),
        CheckConstraint("payment_method IN ('card', 'pse', 'nequi')", name="ck_orders_payment_method"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    ticket_type_id: Mapped[int] = mapped_column(ForeignKey("ticket_types.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    ticket_type: Mapped["TicketType"] = relationship(back_populates="order_items")

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),)

class IssuedTicket(Base):
    __tablename__ = "issued_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    public_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "public_code",
            name="uq_issued_tickets_public_code",
        ),
        UniqueConstraint(
            "order_item_id",
            "sequence_number",
            name="uq_issued_tickets_item_sequence",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_issued_tickets_sequence_positive",
        ),
    )


class UserPreference(Base):
    """Recommendation questionnaire answers: one row per user, only reachable through that user's token."""
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    genres: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    artist_ids: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    scale_danceability: Mapped[int | None] = mapped_column(SmallInteger)
    scale_energy: Mapped[int | None] = mapped_column(SmallInteger)
    scale_acousticness: Mapped[int | None] = mapped_column(SmallInteger)
    scale_mood: Mapped[int | None] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
