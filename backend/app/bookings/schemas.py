import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CreateBookingRequest(BaseModel):
    schedule_id: uuid.UUID
    seat_id: uuid.UUID
    idempotency_key: uuid.UUID


class PayBookingRequest(BaseModel):
    idempotency_key: uuid.UUID


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    schedule_id: uuid.UUID
    seat_id: uuid.UUID
    status: str
    total_amount: Decimal
    reserved_at: datetime
    expires_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    idempotency_key: uuid.UUID

    model_config = {"from_attributes": True}
