from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import get_occupancy, get_stats
from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import AuditTrail, Booking

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_db)):
    return await get_stats(session)


@router.get("/bookings")
async def list_all_bookings(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    query = select(Booking).order_by(Booking.reserved_at.desc())
    if status:
        query = query.where(Booking.status == status)
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    bookings = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "user_id": str(b.user_id),
            "schedule_id": str(b.schedule_id),
            "seat_id": str(b.seat_id),
            "status": b.status,
            "total_amount": float(b.total_amount),
            "reserved_at": b.reserved_at.isoformat() if b.reserved_at else None,
            "confirmed_at": b.confirmed_at.isoformat() if b.confirmed_at else None,
        }
        for b in bookings
    ]


@router.get("/occupancy")
async def occupancy(session: AsyncSession = Depends(get_db)):
    return await get_occupancy(session)


@router.get("/audit")
async def audit_trail(
    booking_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_db),
):
    query = select(AuditTrail).order_by(AuditTrail.created_at.desc())
    if booking_id:
        query = query.where(AuditTrail.booking_id == booking_id)
    query = query.limit(limit)
    result = await session.execute(query)
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "booking_id": str(e.booking_id),
            "user_id": str(e.user_id),
            "action": e.action,
            "previous_status": e.previous_status,
            "new_status": e.new_status,
            "metadata": e.metadata_,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]
