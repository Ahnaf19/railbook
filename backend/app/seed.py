import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Compartment, Schedule, Seat, Train, User

SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

TRAINS = [
    ("Subarna Express", "SE-701", "Dhaka", "Chittagong"),
    ("Ekota Express", "EE-501", "Dhaka", "Rajshahi"),
    ("Mohanagar Provati", "MP-301", "Dhaka", "Sylhet"),
]

COMPARTMENTS = ["A", "B", "C", "D", "E"]
COMP_TYPES = {"A": "ac", "B": "ac", "C": "non_ac", "D": "non_ac", "E": "non_ac"}

DEPARTURE_HOURS = {
    "SE-701": (7, 0),
    "EE-501": (10, 30),
    "MP-301": (6, 30),
}
JOURNEY_HOURS = {
    "SE-701": 5,
    "EE-501": 6,
    "MP-301": 7,
}

USERS = [
    ("admin@railbook.com", "admin123", "Admin User", "+8801700000000", "admin"),
    ("alice@example.com", "password123", "Alice Rahman", "+8801711111111", "user"),
    ("bob@example.com", "password123", "Bob Hasan", "+8801722222222", "user"),
]


def _seat_position(seat_num: int) -> str:
    last_digit = seat_num % 10
    return "window" if last_digit in (1, 4, 5, 8) else "corridor"


async def seed_database(session: AsyncSession) -> None:
    """Seed the database with initial data. Idempotent: skips if data exists."""
    result = await session.execute(select(Train).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    # Users
    for email, password, name, phone, role in USERS:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(email=email, password_hash=pw_hash, full_name=name, phone=phone, role=role)
        session.add(user)

    # System user for cleanup tasks
    system_user = User(
        id=SYSTEM_USER_ID,
        email="system@railbook.internal",
        password_hash="nologin",
        full_name="System",
        role="admin",
    )
    session.add(system_user)

    now = datetime.now(UTC)

    for train_name, train_number, origin, destination in TRAINS:
        train = Train(
            name=train_name, train_number=train_number, origin=origin, destination=destination
        )
        session.add(train)
        await session.flush()

        # Compartments and seats
        for comp_name in COMPARTMENTS:
            comp = Compartment(
                train_id=train.id,
                name=comp_name,
                comp_type=COMP_TYPES[comp_name],
                capacity=50,
            )
            session.add(comp)
            await session.flush()

            for seat_num in range(1, 51):
                seat = Seat(
                    compartment_id=comp.id,
                    seat_number=seat_num,
                    position=_seat_position(seat_num),
                )
                session.add(seat)

        # Schedules for next 7 days
        dep_h, dep_m = DEPARTURE_HOURS[train_number]
        duration = JOURNEY_HOURS[train_number]

        for day_offset in range(7):
            dep_date = (now + timedelta(days=day_offset + 1)).replace(
                hour=dep_h, minute=dep_m, second=0, microsecond=0
            )
            arr_date = dep_date + timedelta(hours=duration)
            schedule = Schedule(
                train_id=train.id,
                departure_time=dep_date,
                arrival_time=arr_date,
                status="scheduled",
            )
            session.add(schedule)

    await session.commit()
