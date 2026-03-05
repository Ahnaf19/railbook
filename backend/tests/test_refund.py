import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Compartment, Schedule, Seat
from app.payments.gateway import payment_gateway


async def _book_and_pay(client, auth_headers, db_session, schedule_offset=8, seat_offset=130):
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

    payment_gateway.failure_rate = 0.0
    payment_gateway.latency_ms = 10

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

    resp = await client.post(
        f"/bookings/{booking['id']}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    payment_gateway.latency_ms = 500
    return resp.json()


async def test_successful_refund(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    payment_gateway.latency_ms = 10
    booking = await _book_and_pay(
        client, auth_headers, db_session, schedule_offset=8, seat_offset=130
    )
    assert booking["status"] == "confirmed"

    resp = await client.post(f"/bookings/{booking['id']}/refund", headers=auth_headers)
    payment_gateway.latency_ms = 500
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"


async def test_refund_non_confirmed_fails(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(9).limit(1)
    )
    schedule = result.scalar_one()
    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(131)
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
    booking = resp.json()

    resp = await client.post(f"/bookings/{booking['id']}/refund", headers=auth_headers)
    assert resp.status_code == 400
