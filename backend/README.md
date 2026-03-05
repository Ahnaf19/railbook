# RailBook Backend

Railway ticket booking API built with **FastAPI**, **SQLAlchemy 2.0** (async), **PostgreSQL**, and **Redis**. Handles concurrent seat reservations with database-level locking, idempotent payments, JWT authentication, and audit trails.

## Quick Start

```bash
# Install dependencies (requires Python 3.11+)
uv sync

# Run migrations
uv run alembic upgrade head

# Start the dev server (port 8000)
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest -v

# Lint & format
uv run ruff check . --fix && uv run ruff format .
```

The server seeds demo data on startup (3 trains, 21 schedules, demo users).

## Project Structure

```
app/
  main.py             # FastAPI app, lifespan (DB verify, seed, cleanup task)
  config.py           # Pydantic Settings from env vars / .env
  database.py         # AsyncEngine + session factory (pool_size=10)
  models.py           # 8 SQLAlchemy models (User, Train, Schedule, Compartment, Seat, Booking, Payment, AuditTrail)
  seed.py             # Idempotent seed: 3 trains, 5 compartments each, 50 seats per compartment, 7 days of schedules
  redis.py            # Redis connection pool for rate limiting
  auth/               # JWT register/login/refresh, bcrypt passwords, role-based deps
  trains/             # Train listing, schedule filtering (future only), seat availability with booking status
  bookings/           # Core booking engine: reserve with row-level lock, pay, refund, journey overlap check
    cleanup.py        # Background task expiring stale reservations (5-min window)
  payments/           # Mock payment gateway with configurable failure rate and latency
  audit/              # Audit trail service recording every booking state transition
  ratelimit/          # Redis sliding-window rate limiter (per-user for bookings, per-IP for auth)
  demo/               # Race condition demo endpoints for concurrency visualization
  admin/              # Admin-only endpoints: stats dashboard, all bookings, occupancy, audit log
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://railbook:railbook_secret@localhost:5432/railbook` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for rate limiting |
| `JWT_SECRET` | `change-me-in-production...` | HMAC signing key for JWTs |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `APP_ENV` | `development` | Environment name |
| `APP_DEBUG` | `true` | Enables SQLAlchemy echo |

## API Routes

| Prefix | Auth | Description |
|---|---|---|
| `GET /health` | No | Health check |
| `/auth/*` | No | Register, login, refresh, get current user |
| `/trains/*` | No | List trains, schedules, seat maps |
| `/bookings/*` | Yes | Reserve, pay, refund, list user bookings |
| `/demo/*` | No | Race condition demo, config tuning |
| `/admin/*` | Yes (admin) | Stats, all bookings, occupancy, audit trail |

Full API docs available at `http://localhost:8000/docs` (Swagger UI) when the server is running.

## Testing

Tests use a separate `railbook_test` database, created automatically by `conftest.py`. Rate limiting is disabled in tests. Concurrency tests use real `asyncio.gather` against the actual database to verify row-level locking. See `backend/tests/README.md` for details.
