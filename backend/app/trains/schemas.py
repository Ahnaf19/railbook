import uuid
from datetime import datetime

from pydantic import BaseModel


class TrainResponse(BaseModel):
    id: uuid.UUID
    name: str
    train_number: str
    origin: str
    destination: str

    model_config = {"from_attributes": True}


class ScheduleResponse(BaseModel):
    id: uuid.UUID
    train_id: uuid.UUID
    departure_time: datetime
    arrival_time: datetime
    status: str

    model_config = {"from_attributes": True}


class SeatInfo(BaseModel):
    id: uuid.UUID
    seat_number: int
    position: str
    compartment_name: str
    comp_type: str
    booking_status: str | None = None


class SeatAvailabilityResponse(BaseModel):
    schedule_id: uuid.UUID
    train_name: str
    total_seats: int
    available_seats: int
    seats: list[SeatInfo]
