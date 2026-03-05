import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Compartment, Schedule, Seat
from app.payments.gateway import payment_gateway


async def _book_seat(client, auth_headers, db_session, schedule_offset=5, seat_offset=120):
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
    return resp.json()


async def test_successful_payment(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    booking = await _book_seat(client, auth_headers, db_session, schedule_offset=5, seat_offset=120)
    payment_gateway.failure_rate = 0.0
    payment_gateway.latency_ms = 10

    resp = await client.post(
        f"/bookings/{booking['id']}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    payment_gateway.latency_ms = 500

    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


async def test_failed_payment(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    booking = await _book_seat(client, auth_headers, db_session, schedule_offset=6, seat_offset=121)
    payment_gateway.failure_rate = 1.0
    payment_gateway.latency_ms = 10

    resp = await client.post(
        f"/bookings/{booking['id']}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    payment_gateway.failure_rate = 0.0
    payment_gateway.latency_ms = 500

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_payment_idempotency(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    booking = await _book_seat(client, auth_headers, db_session, schedule_offset=7, seat_offset=122)
    pay_key = str(uuid.uuid4())
    payment_gateway.failure_rate = 0.0
    payment_gateway.latency_ms = 10

    resp1 = await client.post(
        f"/bookings/{booking['id']}/pay",
        json={"idempotency_key": pay_key},
        headers=auth_headers,
    )
    resp2 = await client.post(
        f"/bookings/{booking['id']}/pay",
        json={"idempotency_key": pay_key},
        headers=auth_headers,
    )
    payment_gateway.latency_ms = 500

    assert resp1.status_code == 200
    assert resp2.status_code in (200, 400)
