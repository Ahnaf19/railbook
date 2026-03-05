import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import log_audit
from app.models import Booking, Compartment, Payment, Schedule, Seat
from app.payments.gateway import PaymentResult, payment_gateway


async def _invalidate_seat_cache(schedule_id: uuid.UUID) -> None:
    """Best-effort Redis cache invalidation."""
    try:
        from redis.asyncio import Redis

        from app.config import settings

        r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.delete(f"seats:{schedule_id}")
        await r.aclose()
    except Exception:
        logger.warning("Redis unavailable for cache invalidation")


def _calculate_price(comp_type: str) -> Decimal:
    return Decimal("1500.00") if comp_type == "ac" else Decimal("800.00")


async def create_booking(
    session: AsyncSession,
    user_id: uuid.UUID,
    schedule_id: uuid.UUID,
    seat_id: uuid.UUID,
    idempotency_key: uuid.UUID,
    ip_address: str | None = None,
) -> Booking:
    async with session.begin():
        # 1. Idempotency check
        existing = await session.execute(
            select(Booking).where(Booking.idempotency_key == idempotency_key)
        )
        if found := existing.scalar_one_or_none():
            return found

        # 2. Lock the seat for this schedule (SELECT FOR UPDATE)
        locked = await session.execute(
            select(Booking)
            .where(Booking.schedule_id == schedule_id, Booking.seat_id == seat_id)
            .with_for_update()
        )
        existing_booking = locked.scalar_one_or_none()
        if existing_booking and existing_booking.status in ("reserved", "confirmed"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seat already booked for this schedule",
            )

        # 3. Journey overlap check
        schedule = await session.get(Schedule, schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
            )

        overlap = await session.execute(
            select(Booking)
            .join(Schedule, Booking.schedule_id == Schedule.id)
            .where(
                Booking.user_id == user_id,
                Booking.status.in_(["reserved", "confirmed"]),
                Schedule.departure_time < schedule.arrival_time,
                Schedule.arrival_time > schedule.departure_time,
            )
        )
        if overlap.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have an overlapping journey",
            )

        # 4. Calculate price
        seat = await session.get(Seat, seat_id)
        if not seat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Seat not found"
            )
        compartment = await session.get(Compartment, seat.compartment_id)
        price = _calculate_price(compartment.comp_type)

        # 5. Create booking
        # If there was a cancelled/refunded booking for same schedule+seat, remove it first
        if existing_booking:
            await session.delete(existing_booking)
            await session.flush()

        booking = Booking(
            user_id=user_id,
            schedule_id=schedule_id,
            seat_id=seat_id,
            status="reserved",
            idempotency_key=idempotency_key,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            total_amount=price,
        )
        session.add(booking)
        await session.flush()

        # 6. Audit
        await log_audit(
            session,
            booking.id,
            user_id,
            "reserved",
            None,
            "reserved",
            metadata={"schedule_id": str(schedule_id), "seat_id": str(seat_id)},
            ip_address=ip_address,
        )

    await _invalidate_seat_cache(schedule_id)
    return booking


async def pay_booking(
    session: AsyncSession,
    booking_id: uuid.UUID,
    user_id: uuid.UUID,
    idempotency_key: uuid.UUID,
    ip_address: str | None = None,
) -> Booking:
    async with session.begin():
        # Load booking with lock
        result = await session.execute(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
            )
        if booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking"
            )
        if booking.status != "reserved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Booking is {booking.status}, not reserved",
            )
        if booking.expires_at and booking.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Reservation expired"
            )

        # Payment idempotency check
        existing_payment = await session.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing_payment.scalar_one_or_none():
            return booking

        # Audit: payment attempted
        await log_audit(
            session,
            booking.id,
            user_id,
            "payment_attempted",
            "reserved",
            "reserved",
            ip_address=ip_address,
        )
        await session.flush()

        # Charge
        result: PaymentResult = await payment_gateway.charge(
            booking.total_amount, str(idempotency_key)
        )

        if result.status == "success":
            booking.status = "confirmed"
            booking.confirmed_at = datetime.now(UTC)
            payment = Payment(
                booking_id=booking.id,
                idempotency_key=idempotency_key,
                amount=booking.total_amount,
                status="success",
                gateway_ref=result.gateway_ref,
                completed_at=datetime.now(UTC),
            )
            session.add(payment)
            await log_audit(
                session,
                booking.id,
                user_id,
                "confirmed",
                "reserved",
                "confirmed",
                metadata={"gateway_ref": result.gateway_ref},
                ip_address=ip_address,
            )
        else:
            booking.status = "cancelled"
            booking.cancelled_at = datetime.now(UTC)
            payment = Payment(
                booking_id=booking.id,
                idempotency_key=idempotency_key,
                amount=booking.total_amount,
                status="failed",
                failure_reason=result.failure_reason,
                completed_at=datetime.now(UTC),
            )
            session.add(payment)
            await log_audit(
                session,
                booking.id,
                user_id,
                "payment_failed",
                "reserved",
                "cancelled",
                metadata={"failure_reason": result.failure_reason},
                ip_address=ip_address,
            )

    await _invalidate_seat_cache(booking.schedule_id)
    return booking


async def refund_booking(
    session: AsyncSession,
    booking_id: uuid.UUID,
    user_id: uuid.UUID,
    ip_address: str | None = None,
) -> Booking:
    async with session.begin():
        result = await session.execute(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
            )
        if booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking"
            )
        if booking.status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Booking is {booking.status}, not confirmed",
            )

        # Check departure is more than 1 hour away
        schedule = await session.get(Schedule, booking.schedule_id)
        if schedule.departure_time < datetime.now(UTC) + timedelta(hours=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot refund within 1 hour of departure",
            )

        # Find the payment to get gateway_ref
        payment_result = await session.execute(
            select(Payment).where(
                Payment.booking_id == booking.id, Payment.status == "success"
            )
        )
        payment = payment_result.scalar_one_or_none()
        if payment:
            await payment_gateway.refund(payment.gateway_ref)

        booking.status = "refunded"
        booking.cancelled_at = datetime.now(UTC)

        await log_audit(
            session,
            booking.id,
            user_id,
            "refunded",
            "confirmed",
            "refunded",
            ip_address=ip_address,
        )

    await _invalidate_seat_cache(booking.schedule_id)
    return booking


async def list_user_bookings(
    session: AsyncSession, user_id: uuid.UUID, status_filter: str | None = None
) -> list[Booking]:
    query = select(Booking).where(Booking.user_id == user_id)
    if status_filter:
        query = query.where(Booking.status == status_filter)
    query = query.order_by(Booking.reserved_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_booking(session: AsyncSession, booking_id: uuid.UUID) -> Booking | None:
    result = await session.execute(select(Booking).where(Booking.id == booking_id))
    return result.scalar_one_or_none()
