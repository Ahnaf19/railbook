# RailBook

A railway ticket booking system that deliberately showcases concurrency handling — race conditions, row-level locking, atomic transactions, idempotent payments, and a split-screen demo.

## Quick Start

```bash
# Start PostgreSQL + Redis
docker-compose up -d postgres redis

# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload  # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev  # http://localhost:5173
```

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────┐
│   React UI  │─────▸│  FastAPI      │─────▸│ PostgreSQL │
│  (Vite)     │      │  (async)      │      │  (16)      │
└─────────────┘      │               │─────▸│            │
                     │  SELECT FOR   │      └────────────┘
                     │  UPDATE       │
                     │               │─────▸┌────────────┐
                     │  Rate Limit   │      │   Redis    │
                     └──────────────┘      │   (7)      │
                                            └────────────┘
```

## Tech Stack

| Layer    | Technology                      |
|----------|---------------------------------|
| Backend  | FastAPI, SQLAlchemy 2.0 async   |
| Database | PostgreSQL 16 + asyncpg         |
| Cache    | Redis 7 (seat cache, rate limit)|
| Frontend | React 18, Vite, React Router    |
| Auth     | JWT (PyJWT) + bcrypt            |
| Testing  | pytest-asyncio, httpx           |
| Load     | Locust                          |

## Concurrency Problems Solved

| Problem | Solution | Test |
|---------|----------|------|
| Double booking | `SELECT FOR UPDATE` row-level lock | `test_double_booking_prevented` |
| Journey overlap | Time range check in same transaction | `test_overlapping_journey_blocked` |
| Idempotency | Unique key per booking/payment | `test_idempotent_booking` |
| Reservation expiry | Background cleanup with `skip_locked` | `test_expired_reservation_released` |
| Payment atomicity | Booking + audit in single commit | `test_payment_success_creates_entries` |

## Features

- **Seat Selection**: Visual seat grid with real-time availability (Redis-cached)
- **5-Minute Reservations**: Auto-expire with background cleanup
- **Idempotent Payments**: Mock gateway with configurable failure rate
- **Audit Trail**: Every state change logged atomically with the booking
- **Rate Limiting**: Redis sliding window (5 bookings/min, 3 payments/min)
- **Concurrency Demo**: Split-screen race between two users for the same seat
- **Admin Dashboard**: Booking stats, occupancy rates, audit trail viewer

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/register` | Register user |
| POST | `/auth/login` | Login |
| GET | `/trains` | List trains |
| GET | `/trains/{id}/schedules` | Train schedules |
| GET | `/trains/schedules/{id}/seats` | Seat availability |
| POST | `/bookings` | Create booking (reserve) |
| POST | `/bookings/{id}/pay` | Pay for booking |
| POST | `/bookings/{id}/refund` | Refund booking |
| GET | `/bookings` | My bookings |
| POST | `/demo/race-condition` | Race condition demo |
| GET | `/admin/stats` | Admin statistics |

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Concurrency Handling](docs/architecture/CONCURRENCY.md)
- [Database Schema](docs/architecture/DATABASE.md)
- [API Reference](docs/api/API_REFERENCE.md)
- [Error Codes](docs/api/ERROR_CODES.md)
- [Developer Guide](docs/guides/DEVELOPER_GUIDE.md)
- [Deployment Guide](docs/guides/DEPLOYMENT_GUIDE.md)

## Testing

```bash
cd backend
uv run pytest -v            # 34 tests
uv run ruff check . --fix   # Linting
```

## Load Testing

```bash
cd loadtest
pip install -r requirements.txt
locust -f locustfile.py --host http://localhost:8000
python verify_integrity.py  # Post-test DB integrity check
```

## Project Structure

```
railbook/
├── backend/
│   ├── app/
│   │   ├── auth/        # JWT authentication
│   │   ├── trains/      # Train & schedule listing
│   │   ├── bookings/    # Core booking engine
│   │   ├── payments/    # Mock payment gateway
│   │   ├── audit/       # Audit trail service
│   │   ├── ratelimit/   # Redis rate limiter
│   │   ├── demo/        # Race condition demo
│   │   └── admin/       # Admin endpoints
│   ├── migrations/      # Alembic migrations
│   └── tests/           # 34 async tests
├── frontend/
│   └── src/
│       ├── pages/       # Route pages
│       ├── components/  # Reusable UI
│       └── context/     # Auth state
├── loadtest/            # Locust load tests
└── docs/                # Documentation
```
