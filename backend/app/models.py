import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class Train(Base):
    __tablename__ = "trains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    train_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="train")
    compartments: Mapped[list["Compartment"]] = relationship(back_populates="train")


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (UniqueConstraint("train_id", "departure_time"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    train_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trains.id"), nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")

    train: Mapped["Train"] = relationship(back_populates="schedules")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="schedule")


class Compartment(Base):
    __tablename__ = "compartments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    train_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trains.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(10), nullable=False)
    comp_type: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(default=50)

    train: Mapped["Train"] = relationship(back_populates="compartments")
    seats: Mapped[list["Seat"]] = relationship(back_populates="compartment")


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("compartment_id", "seat_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compartments.id"), nullable=False)
    seat_number: Mapped[int] = mapped_column(nullable=False)
    position: Mapped[str] = mapped_column(String(20), nullable=False)

    compartment: Mapped["Compartment"] = relationship(back_populates="seats")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="seat")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("schedule_id", "seat_id", name="uq_booking_schedule_seat"),
        Index("ix_bookings_user_id", "user_id"),
        Index("ix_bookings_schedule_seat", "schedule_id", "seat_id"),
        Index("ix_bookings_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schedules.id"), nullable=False)
    seat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seats.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    user: Mapped["User"] = relationship(back_populates="bookings")
    schedule: Mapped["Schedule"] = relationship(back_populates="bookings")
    seat: Mapped["Seat"] = relationship(back_populates="bookings")
    payments: Mapped[list["Payment"]] = relationship(back_populates="booking")
    audit_entries: Mapped[list["AuditTrail"]] = relationship(back_populates="booking")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    gateway_ref: Mapped[str | None] = mapped_column(String(100))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(500))

    booking: Mapped["Booking"] = relationship(back_populates="payments")


class AuditTrail(Base):
    __tablename__ = "audit_trail"
    __table_args__ = (Index("ix_audit_booking_created", "booking_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped["Booking"] = relationship(back_populates="audit_entries")
    user: Mapped["User"] = relationship()
