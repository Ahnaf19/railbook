import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.bookings.schemas import (
    BookingResponse,
    CreateBookingRequest,
    PayBookingRequest,
)
from app.bookings.service import (
    create_booking,
    enrich_booking,
    get_booking,
    list_user_bookings,
    pay_booking,
    refund_booking,
)
from app.database import get_db
from app.models import User
from app.ratelimit.dependencies import rate_limit_booking, rate_limit_payment

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post(
    "", response_model=BookingResponse, status_code=201, dependencies=[Depends(rate_limit_booking)]
)
async def create(
    request: CreateBookingRequest,
    raw_request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = await create_booking(
        session,
        user.id,
        request.schedule_id,
        request.seat_id,
        request.idempotency_key,
        ip_address=raw_request.client.host if raw_request.client else None,
    )
    return await enrich_booking(session, booking)


@router.post(
    "/{booking_id}/pay", response_model=BookingResponse, dependencies=[Depends(rate_limit_payment)]
)
async def pay(
    booking_id: uuid.UUID,
    request: PayBookingRequest,
    raw_request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = await pay_booking(
        session,
        booking_id,
        user.id,
        request.idempotency_key,
        ip_address=raw_request.client.host if raw_request.client else None,
    )
    return await enrich_booking(session, booking)


@router.get("", response_model=list[BookingResponse])
async def list_bookings(
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bookings = await list_user_bookings(session, user.id, status)
    return [await enrich_booking(session, b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingResponse)
async def get(
    booking_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = await get_booking(session, booking_id)
    return await enrich_booking(session, booking)


@router.post(
    "/{booking_id}/refund",
    response_model=BookingResponse,
    dependencies=[Depends(rate_limit_payment)],
)
async def refund(
    booking_id: uuid.UUID,
    raw_request: Request,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = await refund_booking(
        session,
        booking_id,
        user.id,
        ip_address=raw_request.client.host if raw_request.client else None,
    )
    return await enrich_booking(session, booking)
