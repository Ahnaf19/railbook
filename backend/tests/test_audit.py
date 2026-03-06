import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditTrail, Compartment, Schedule, Seat
from app.payments.gateway import payment_gateway


async def _get_schedule_seat(db_session, schedule_offset, seat_offset):
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


async def test_reserve_creates_audit_entry(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_seat(db_session, schedule_offset=10, seat_offset=35)

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
    booking_id = resp.json()["id"]

    result = await db_session.execute(
        select(AuditTrail)
        .where(AuditTrail.booking_id == uuid.UUID(booking_id))
        .order_by(AuditTrail.created_at)
    )
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].action == "reserved"


async def test_payment_success_creates_entries(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_seat(db_session, schedule_offset=11, seat_offset=36)
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
    booking_id = resp.json()["id"]

    await client.post(
        f"/bookings/{booking_id}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    payment_gateway.latency_ms = 500

    result = await db_session.execute(
        select(AuditTrail)
        .where(AuditTrail.booking_id == uuid.UUID(booking_id))
        .order_by(AuditTrail.created_at)
    )
    entries = result.scalars().all()
    assert len(entries) == 3  # reserved + payment_attempted + confirmed
    actions = [e.action for e in entries]
    assert "reserved" in actions
    assert "payment_attempted" in actions
    assert "confirmed" in actions


async def test_payment_failure_creates_entries(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_seat(db_session, schedule_offset=12, seat_offset=37)

    resp = await client.post(
        "/bookings",
        json={
            "schedule_id": str(schedule.id),
            "seat_id": str(seat.id),
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=auth_headers,
    )
    booking_id = resp.json()["id"]

    payment_gateway.failure_rate = 1.0
    payment_gateway.latency_ms = 10
    await client.post(
        f"/bookings/{booking_id}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    payment_gateway.failure_rate = 0.0
    payment_gateway.latency_ms = 500

    result = await db_session.execute(
        select(AuditTrail)
        .where(AuditTrail.booking_id == uuid.UUID(booking_id))
        .order_by(AuditTrail.created_at)
    )
    entries = result.scalars().all()
    assert len(entries) == 3  # reserved + payment_attempted + payment_failed
    actions = [e.action for e in entries]
    assert "payment_failed" in actions


async def test_refund_creates_audit_entry(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_seat(db_session, schedule_offset=13, seat_offset=38)
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
    booking_id = resp.json()["id"]

    await client.post(
        f"/bookings/{booking_id}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    await client.post(f"/bookings/{booking_id}/refund", headers=auth_headers)
    payment_gateway.latency_ms = 500

    result = await db_session.execute(
        select(AuditTrail)
        .where(AuditTrail.booking_id == uuid.UUID(booking_id))
        .order_by(AuditTrail.created_at)
    )
    entries = result.scalars().all()
    actions = [e.action for e in entries]
    assert "refunded" in actions


async def test_entries_are_chronological(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    schedule, seat = await _get_schedule_seat(db_session, schedule_offset=14, seat_offset=39)
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
    booking_id = resp.json()["id"]

    await client.post(
        f"/bookings/{booking_id}/pay",
        json={"idempotency_key": str(uuid.uuid4())},
        headers=auth_headers,
    )
    payment_gateway.latency_ms = 500

    result = await db_session.execute(
        select(AuditTrail)
        .where(AuditTrail.booking_id == uuid.UUID(booking_id))
        .order_by(AuditTrail.created_at)
    )
    entries = result.scalars().all()
    for i in range(1, len(entries)):
        assert entries[i].created_at >= entries[i - 1].created_at
