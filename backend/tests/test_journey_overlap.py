import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Compartment, Schedule, Seat


async def test_overlapping_journey_blocked(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Two bookings on the same schedule for the same user should fail (overlap)."""
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(4).limit(1)
    )
    schedule = result.scalar_one()

    # Two different seats on same train
    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(15)
        .limit(2)
    )
    seats = result.scalars().all()
    assert len(seats) == 2

    # Book first seat
    resp = await client.post(
        "/bookings",
        json={
            "schedule_id": str(schedule.id),
            "seat_id": str(seats[0].id),
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    # Try second seat on same schedule -> overlap
    resp = await client.post(
        "/bookings",
        json={
            "schedule_id": str(schedule.id),
            "seat_id": str(seats[1].id),
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "overlapping" in resp.json()["detail"].lower()
