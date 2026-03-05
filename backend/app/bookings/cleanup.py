import asyncio

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.audit.service import log_audit
from app.models import Booking
from app.seed import SYSTEM_USER_ID


async def cleanup_expired_reservations(session_factory: async_sessionmaker) -> None:
    """Runs every 60 seconds. Releases expired reservations with audit trail."""
    while True:
        try:
            async with session_factory() as session, session.begin():
                result = await session.execute(
                    select(Booking)
                    .where(Booking.status == "reserved", Booking.expires_at < func.now())
                    .with_for_update(skip_locked=True)
                )
                expired = result.scalars().all()
                for booking in expired:
                    booking.status = "cancelled"
                    booking.cancelled_at = func.now()
                    await log_audit(
                        session,
                        booking.id,
                        SYSTEM_USER_ID,
                        "expired_cleanup",
                        "reserved",
                        "cancelled",
                        metadata={
                            "expired_at": str(booking.expires_at),
                            "ttl_seconds": 300,
                        },
                    )
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired reservations")
        except Exception:
            logger.exception("Error in reservation cleanup")
        await asyncio.sleep(60)
