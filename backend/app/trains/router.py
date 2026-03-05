import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.trains.schemas import (
    ScheduleResponse,
    SeatAvailabilityResponse,
    TrainResponse,
)
from app.trains.service import get_seat_availability, list_schedules, list_trains

router = APIRouter(prefix="/trains", tags=["trains"])


def _get_redis():
    """Get Redis connection from pool, or None if unavailable."""
    try:
        from app.redis import get_redis

        return get_redis()
    except Exception:
        return None


@router.get("", response_model=list[TrainResponse])
async def get_trains(session: AsyncSession = Depends(get_db)):
    return await list_trains(session)


@router.get("/{train_id}/schedules", response_model=list[ScheduleResponse])
async def get_schedules(train_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await list_schedules(session, train_id)


@router.get(
    "/schedules/{schedule_id}/seats",
    response_model=SeatAvailabilityResponse,
)
async def get_seats(schedule_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    redis = _get_redis()
    try:
        result = await get_seat_availability(session, schedule_id, redis)
    finally:
        if redis:
            await redis.aclose()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return result
