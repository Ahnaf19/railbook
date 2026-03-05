import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Compartment, Schedule, Seat, Train, User


async def test_list_trains(client: AsyncClient):
    resp = await client.get("/trains")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    names = {t["train_number"] for t in data}
    assert names == {"SE-701", "EE-501", "MP-301"}


async def test_schedules_returns_future_only(client: AsyncClient, db_session: AsyncSession):
    result = await db_session.execute(select(Train).limit(1))
    train = result.scalar_one()
    resp = await client.get(f"/trains/{train.id}/schedules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    # All schedules should be in the future
    for s in data:
        assert s["status"] == "scheduled"


async def test_seat_availability(client: AsyncClient, db_session: AsyncSession, auth_headers):
    # Get a schedule
    result = await db_session.execute(select(Schedule).limit(1))
    schedule = result.scalar_one()

    resp = await client.get(f"/trains/schedules/{schedule.id}/seats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_seats"] == 250  # 5 compartments x 50 seats
    assert data["available_seats"] == 250  # No bookings yet


async def test_seat_shows_booked_after_booking(client: AsyncClient, db_session: AsyncSession):
    # Use a unique schedule (offset 18) to avoid collisions with other tests
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(18).limit(1)
    )
    schedule = result.scalar_one()

    # Pick a seat that's not yet booked
    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(200)
        .limit(1)
    )
    seat = result.scalar_one()

    result = await db_session.execute(select(User).where(User.email == "alice@example.com"))
    user = result.scalar_one()

    booking = Booking(
        user_id=user.id,
        schedule_id=schedule.id,
        seat_id=seat.id,
        status="confirmed",
        idempotency_key=uuid.uuid4(),
        total_amount=1500,
    )
    db_session.add(booking)
    await db_session.commit()

    # Invalidate Redis cache so the next GET reads from DB
    try:
        from app.redis import get_redis

        r = get_redis()
        await r.delete(f"seats:{schedule.id}")
        await r.aclose()
    except Exception:
        pass

    resp = await client.get(f"/trains/schedules/{schedule.id}/seats")
    assert resp.status_code == 200
    data = resp.json()

    booked = [s for s in data["seats"] if s["id"] == str(seat.id)]
    assert len(booked) == 1
    assert booked[0]["booking_status"] == "confirmed"
    assert data["available_seats"] < data["total_seats"]
