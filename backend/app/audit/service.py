import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditTrail


async def log_audit(
    session: AsyncSession,
    booking_id: uuid.UUID,
    user_id: uuid.UUID,
    action: str,
    previous_status: str | None,
    new_status: str,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Append-only audit entry. MUST be called inside the booking transaction."""
    entry = AuditTrail(
        booking_id=booking_id,
        user_id=user_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        metadata_=metadata or {},
        ip_address=ip_address,
    )
    session.add(entry)
