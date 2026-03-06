from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Payment, Schedule


async def get_stats(session: AsyncSession) -> dict:
    total_bookings = await session.execute(select(func.count(Booking.id)))
    confirmed_bookings = await session.execute(
        select(func.count(Booking.id)).where(Booking.status == "confirmed")
    )
    revenue = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "success")
    )
    cancelled = await session.execute(
        select(func.count(Booking.id)).where(Booking.status == "cancelled")
    )
    refunded = await session.execute(
        select(func.count(Booking.id)).where(Booking.status == "refunded")
    )

    return {
        "total_bookings": total_bookings.scalar(),
        "confirmed_bookings": confirmed_bookings.scalar(),
        "cancelled_bookings": cancelled.scalar(),
        "refunded_bookings": refunded.scalar(),
        "total_revenue": float(revenue.scalar()),
    }


async def get_occupancy(session: AsyncSession) -> list[dict]:
    """Occupancy rate per schedule."""
    result = await session.execute(
        select(
            Schedule.id,
            Schedule.departure_time,
            Schedule.train_id,
            func.count(Booking.id)
            .filter(Booking.status.in_(["reserved", "confirmed"]))
            .label("booked"),
        )
        .outerjoin(Booking, Booking.schedule_id == Schedule.id)
        .group_by(Schedule.id)
        .order_by(Schedule.departure_time)
    )
    rows = result.all()
    total_seats = 50  # 2 compartments x 25 seats

    return [
        {
            "schedule_id": str(r.id),
            "departure_time": r.departure_time.isoformat(),
            "train_id": str(r.train_id),
            "booked_seats": r.booked,
            "total_seats": total_seats,
            "occupancy_pct": round(r.booked / total_seats * 100, 1),
        }
        for r in rows
    ]
