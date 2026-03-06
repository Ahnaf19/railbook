import asyncio
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from app.models import Compartment, Schedule, Seat
from app.ratelimit.dependencies import rate_limit_auth, rate_limit_booking, rate_limit_payment
from tests.conftest import TestSession


async def _register_user(client: AsyncClient, suffix: str) -> dict:
    email = f"racer-{suffix}-{uuid.uuid4().hex[:6]}@test.com"
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "pass123", "full_name": f"Racer {suffix}"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _make_client():
    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[rate_limit_auth] = lambda: None
    app.dependency_overrides[rate_limit_booking] = lambda: None
    app.dependency_overrides[rate_limit_payment] = lambda: None
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_double_booking_prevented(db_session: AsyncSession):
    """Two concurrent bookings for same seat -> exactly one 201, one 409."""
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(15).limit(1)
    )
    schedule = result.scalar_one()
    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(40)
        .limit(1)
    )
    seat = result.scalar_one()

    client_a = await _make_client()
    client_b = await _make_client()
    headers_a = await _register_user(client_a, "a")
    headers_b = await _register_user(client_b, "b")

    async def book(client, headers):
        return await client.post(
            "/bookings",
            json={
                "schedule_id": str(schedule.id),
                "seat_id": str(seat.id),
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )

    result_a, result_b = await asyncio.gather(book(client_a, headers_a), book(client_b, headers_b))
    await client_a.aclose()
    await client_b.aclose()

    statuses = sorted([result_a.status_code, result_b.status_code])
    assert statuses == [201, 409], f"Expected [201, 409] got {statuses}"


async def test_concurrent_different_seats(db_session: AsyncSession):
    """Two concurrent bookings for different seats both succeed."""
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(16).limit(1)
    )
    schedule = result.scalar_one()

    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(41)
        .limit(2)
    )
    seats = result.scalars().all()
    assert len(seats) == 2

    client_a = await _make_client()
    client_b = await _make_client()
    headers_a = await _register_user(client_a, "c")
    headers_b = await _register_user(client_b, "d")

    async def book(client, headers, seat):
        return await client.post(
            "/bookings",
            json={
                "schedule_id": str(schedule.id),
                "seat_id": str(seat.id),
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=headers,
        )

    result_a, result_b = await asyncio.gather(
        book(client_a, headers_a, seats[0]), book(client_b, headers_b, seats[1])
    )
    await client_a.aclose()
    await client_b.aclose()

    assert result_a.status_code == 201
    assert result_b.status_code == 201


async def test_idempotent_booking(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Same idempotency key twice -> only one booking created."""
    result = await db_session.execute(
        select(Schedule).order_by(Schedule.departure_time).offset(17).limit(1)
    )
    schedule = result.scalar_one()
    result = await db_session.execute(
        select(Seat)
        .join(Compartment, Seat.compartment_id == Compartment.id)
        .where(Compartment.train_id == schedule.train_id)
        .offset(42)
        .limit(1)
    )
    seat = result.scalar_one()

    key = str(uuid.uuid4())
    payload = {
        "schedule_id": str(schedule.id),
        "seat_id": str(seat.id),
        "idempotency_key": key,
    }

    resp1 = await client.post("/bookings", json=payload, headers=auth_headers)
    resp2 = await client.post("/bookings", json=payload, headers=auth_headers)

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["id"] == resp2.json()["id"]
