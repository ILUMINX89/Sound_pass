from datetime import date, time, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============================================================
# Auth / Users
# ============================================================
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=6)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ============================================================
# Venues
# ============================================================
class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    city: str
    address: str | None = None


# ============================================================
# Ticket types
# ============================================================
class TicketTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Decimal
    quantity_available: int


# ============================================================
# Concerts
# ============================================================
class ConcertListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    artist: str
    tour_name: str
    genre: str
    event_date: date
    event_time: time
    venue: VenueOut
    price_from: Decimal


class ConcertDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    artist: str
    tour_name: str
    genre: str
    event_date: date
    event_time: time
    description: str | None
    image_url: str | None
    venue: VenueOut
    ticket_types: list[TicketTypeOut]


# ============================================================
# Orders / checkout
# ============================================================
class OrderItemCreate(BaseModel):
    ticket_type_id: int
    quantity: int = Field(gt=0, le=10)


class OrderCreate(BaseModel):
    concert_id: int
    payment_method: Literal["card", "pse", "nequi"]
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticket_type_name: str
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_code: str
    status: Literal["confirmed", "cancelled"]
    payment_method: str
    subtotal: Decimal
    service_fee: Decimal
    total: Decimal
    created_at: datetime
    cancelled_at: datetime | None
    concert: ConcertListOut
    items: list[OrderItemOut]

# ============================================================
# Venues — CRUD
# ============================================================
class VenueCreate(BaseModel):
    name: str
    city: str
    address: str | None = None
    capacity: int | None = None