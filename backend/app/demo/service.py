import asyncio
import time
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bookings.service import create_booking


@dataclass
class AttemptResult:
    user_label: str
    status_code: int
    detail: str
    elapsed_ms: float


@dataclass
class RaceResult:
    attempt_a: AttemptResult
    attempt_b: AttemptResult
    winner: str | None


async def _attempt_booking(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    user_label: str,
    schedule_id: uuid.UUID,
    seat_id: uuid.UUID,
    start_time: float,
) -> AttemptResult:
    async with session_factory() as session:
        try:
            await create_booking(
                session,
                user_id,
                schedule_id,
                seat_id,
                idempotency_key=uuid.uuid4(),
                ip_address="demo",
            )
            return AttemptResult(
                user_label=user_label,
                status_code=201,
                detail="Booking created",
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 1),
            )
        except Exception as e:
            return AttemptResult(
                user_label=user_label,
                status_code=getattr(e, "status_code", 500),
                detail=getattr(e, "detail", str(e)),
                elapsed_ms=round((time.monotonic() - start_time) * 1000, 1),
            )


async def run_race(
    session_factory: async_sessionmaker[AsyncSession],
    schedule_id: uuid.UUID,
    seat_id: uuid.UUID,
    user_id_a: uuid.UUID,
    user_id_b: uuid.UUID,
) -> RaceResult:
    start = time.monotonic()

    result_a, result_b = await asyncio.gather(
        _attempt_booking(session_factory, user_id_a, "A", schedule_id, seat_id, start),
        _attempt_booking(session_factory, user_id_b, "B", schedule_id, seat_id, start),
    )

    winner = None
    if result_a.status_code == 201 and result_b.status_code != 201:
        winner = "A"
    elif result_b.status_code == 201 and result_a.status_code != 201:
        winner = "B"

    return RaceResult(attempt_a=result_a, attempt_b=result_b, winner=winner)
