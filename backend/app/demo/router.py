import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.database import async_session
from app.demo.service import run_race
from app.models import User
from app.payments.gateway import payment_gateway

router = APIRouter(prefix="/demo", tags=["demo"])


class RaceRequest(BaseModel):
    schedule_id: uuid.UUID
    seat_id: uuid.UUID
    user_id_a: uuid.UUID | None = None
    user_id_b: uuid.UUID | None = None


@router.post("/race-condition")
async def race_condition(request: RaceRequest):
    """Spawn two concurrent booking attempts for the same seat."""
    user_a = request.user_id_a
    user_b = request.user_id_b

    # Default to alice and bob if not specified
    if not user_a or not user_b:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.email.in_(["alice@example.com", "bob@example.com"]))
            )
            users = result.scalars().all()
            if len(users) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Demo users not found. Provide user_id_a and user_id_b.",
                )
            user_a = user_a or users[0].id
            user_b = user_b or users[1].id

    result = await run_race(
        async_session,
        request.schedule_id,
        request.seat_id,
        user_a,
        user_b,
    )

    return {
        "attempt_a": {
            "user": result.attempt_a.user_label,
            "status_code": result.attempt_a.status_code,
            "detail": result.attempt_a.detail,
            "elapsed_ms": result.attempt_a.elapsed_ms,
        },
        "attempt_b": {
            "user": result.attempt_b.user_label,
            "status_code": result.attempt_b.status_code,
            "detail": result.attempt_b.detail,
            "elapsed_ms": result.attempt_b.elapsed_ms,
        },
        "winner": result.winner,
    }


@router.get("/config")
async def get_config():
    """Return current demo configuration."""
    return {
        "payment_gateway": {
            "failure_rate": payment_gateway.failure_rate,
            "latency_ms": payment_gateway.latency_ms,
        },
    }


class ConfigUpdate(BaseModel):
    failure_rate: float | None = None
    latency_ms: int | None = None


@router.put("/config")
async def update_config(config: ConfigUpdate):
    """Update demo configuration (payment gateway settings)."""
    if config.failure_rate is not None:
        payment_gateway.failure_rate = max(0.0, min(1.0, config.failure_rate))
    if config.latency_ms is not None:
        payment_gateway.latency_ms = max(0, config.latency_ms)
    return {
        "payment_gateway": {
            "failure_rate": payment_gateway.failure_rate,
            "latency_ms": payment_gateway.latency_ms,
        },
    }
