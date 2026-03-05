import json
import uuid

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Compartment, Schedule, Seat, Train


async def list_trains(session: AsyncSession) -> list[Train]:
    result = await session.execute(select(Train).order_by(Train.name))
    return list(result.scalars().all())


async def list_schedules(session: AsyncSession, train_id: uuid.UUID) -> list[Schedule]:
    result = await session.execute(
        select(Schedule)
        .where(Schedule.train_id == train_id, Schedule.departure_time > func.now())
        .order_by(Schedule.departure_time)
    )
    return list(result.scalars().all())


async def get_seat_availability(
    session: AsyncSession,
    schedule_id: uuid.UUID,
    redis: Redis | None = None,
) -> dict:
    # Check Redis cache
    cache_key = f"seats:{schedule_id}"
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            logger.warning("Redis unavailable for seat cache read")

    # Query DB
    schedule = await session.get(Schedule, schedule_id)
    if not schedule:
        return None

    train = await session.get(Train, schedule.train_id)

    result = await session.execute(
        select(
            Seat.id,
            Seat.seat_number,
            Seat.position,
            Compartment.name.label("compartment_name"),
            Compartment.comp_type,
            Booking.status.label("booking_status"),
        )
        .outerjoin(
            Booking,
            and_(
                Booking.seat_id == Seat.id,
                Booking.schedule_id == schedule_id,
                Booking.status.in_(["reserved", "confirmed"]),
            ),
        )
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .order_by(Compartment.name, Seat.seat_number)
    )

    seats = []
    available_count = 0
    for row in result.all():
        seat_dict = {
            "id": str(row.id),
            "seat_number": row.seat_number,
            "position": row.position,
            "compartment_name": row.compartment_name,
            "comp_type": row.comp_type,
            "booking_status": row.booking_status,
        }
        seats.append(seat_dict)
        if row.booking_status is None:
            available_count += 1

    payload = {
        "schedule_id": str(schedule_id),
        "train_name": train.name,
        "total_seats": len(seats),
        "available_seats": available_count,
        "seats": seats,
    }

    # Cache result
    if redis:
        try:
            await redis.set(cache_key, json.dumps(payload), ex=5)
        except Exception:
            logger.warning("Redis unavailable for seat cache write")

    return payload
