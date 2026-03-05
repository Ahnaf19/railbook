import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Compartment, Schedule, Seat


async def _get_schedule_and_seat(db_session: AsyncSession, schedule_offset=2, seat_offset=2):
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(schedule_offset).limit(1)
    )
    schedule = result.scalar_one()
    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(seat_offset)
        .limit(1)
    )
    seat = result.scalar_one()
    return schedule, seat


async def test_happy_path_reserve_pay_confirm(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_and_seat(db_session, schedule_offset=2, seat_offset=100)

    # Reserve
    resp = await client.post(
        "/bookings",
        json={
            "schedule_id": str(schedule.id),
            "seat_id": str(seat.id),
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    booking = resp.json()
    assert booking["status"] == "reserved"
    booking_id = booking["id"]

    # Pay
    resp = await client.post(
        f"/bookings/{booking_id}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["confirmed_at"] is not None


async def test_list_user_bookings(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_and_seat(db_session, schedule_offset=3, seat_offset=101)

    resp = await client.post(
        "/bookings",
        json={
            "schedule_id": str(schedule.id),
            "seat_id": str(seat.id),
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    resp = await client.get("/bookings", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
