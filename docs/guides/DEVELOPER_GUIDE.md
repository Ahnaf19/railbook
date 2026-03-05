# RailBook Developer Guide

RailBook is a railway ticket booking system built to demonstrate concurrency handling, idempotent operations, and transactional integrity. The backend is a FastAPI application with PostgreSQL and Redis. The frontend is a React (Vite) application.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Database](#database)
- [Seed Data](#seed-data)
- [Testing](#testing)
- [Code Conventions](#code-conventions)
- [Key Architectural Patterns](#key-architectural-patterns)

---

## Prerequisites

| Tool         | Version   | Purpose                                |
|--------------|-----------|----------------------------------------|
| Docker       | 20+       | Run PostgreSQL and Redis containers    |
| Docker Compose | v2+     | Orchestrate multi-container setup      |
| Python       | 3.11+     | Backend runtime                        |
| uv           | latest    | Python package manager and task runner |
| Node.js      | 18+       | Frontend runtime                       |
| npm          | 9+        | Frontend package manager               |

Install `uv` if you do not have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Quick Start

### Option 1: Full stack with Docker Compose

This starts PostgreSQL, Redis, the backend, and the frontend in containers:

```bash
cd /Users/ahnaftanjid/Documents/railbook
docker-compose up --build
```

Services will be available at:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Option 2: Local development (recommended for backend work)

**Step 1: Start infrastructure services**

```bash
cd /Users/ahnaftanjid/Documents/railbook
docker-compose up postgres redis -d
```

This starts only PostgreSQL and Redis in the background.

**Step 2: Set up the backend**

```bash
cd /Users/ahnaftanjid/Documents/railbook/backend

# Install Python dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the backend server (auto-reloads on file changes)
uv run uvicorn app.main:app --reload
```

The backend starts on http://localhost:8000. On first startup, the lifespan handler automatically seeds the database with trains, schedules, compartments, seats, and demo users.

**Step 3: Set up the frontend (optional)**

```bash
cd /Users/ahnaftanjid/Documents/railbook/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend dev server starts on http://localhost:5173.

**Step 4: Verify the setup**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}

curl http://localhost:8000/trains
# Expected: JSON array of 3 trains
```

---

## Project Structure

```
railbook/
  docker-compose.yml          # PostgreSQL, Redis, backend, frontend
  backend/
    Dockerfile                # Python 3.11 + uv
    pyproject.toml            # Dependencies and tool configuration
    alembic.ini               # Alembic migration configuration
    migrations/               # Database migration files
    app/
      main.py                 # FastAPI app, lifespan, router registration
      config.py               # Pydantic Settings (env vars)
      database.py             # AsyncEngine, session factory
      models.py               # SQLAlchemy ORM models (User, Train, Schedule, etc.)
      seed.py                 # Seed data (trains, schedules, demo users)
      auth/
        router.py             # /auth/* endpoints (register, login, refresh, me)
        schemas.py            # Pydantic request/response models
        service.py            # User creation, authentication, JWT helpers
        dependencies.py       # get_current_user, require_admin dependencies
      trains/
        router.py             # /trains/* endpoints (list, schedules, seats)
        schemas.py            # TrainResponse, ScheduleResponse, SeatAvailabilityResponse
        service.py            # Train/schedule/seat queries with Redis caching
      bookings/
        router.py             # /bookings/* endpoints (create, pay, refund, list)
        schemas.py            # CreateBookingRequest, PayBookingRequest, BookingResponse
        service.py            # Core booking logic with SELECT FOR UPDATE locking
        cleanup.py            # Background task to expire stale reservations
      payments/
        gateway.py            # MockPaymentGateway with configurable failure/latency
      audit/
        service.py            # Audit trail logging (writes to audit_trail table)
      ratelimit/
        limiter.py            # Redis sliding window rate limiter
        dependencies.py       # FastAPI dependencies for rate limiting
      admin/
        router.py             # /admin/* endpoints (stats, bookings, occupancy, audit)
        service.py            # Admin query logic
      demo/
        router.py             # /demo/* endpoints (race-condition, config)
        service.py            # Race condition simulation logic
      redis.py                # Redis connection pool management
    tests/
      conftest.py             # Test fixtures (test DB, client, auth helpers)
      test_auth.py            # Auth endpoint tests
      test_bookings.py        # Booking flow tests
      test_concurrency.py     # Race condition / concurrency tests
  frontend/
    Dockerfile                # Node 20 build + Nginx
    package.json
    src/
      main.jsx                # Entry point
      App.jsx                 # Router + AuthProvider
      api/client.js           # Axios instance with JWT interceptor
      context/AuthContext.jsx  # Auth state management
      components/             # Reusable UI components
      pages/                  # Route pages
```

---

## Database

### Models

The system uses 7 SQLAlchemy ORM models:

| Model         | Table           | Description                                        |
|---------------|-----------------|----------------------------------------------------|
| `User`        | `users`         | User accounts with email, password hash, role      |
| `Train`       | `trains`        | Train definitions (name, number, origin, dest)     |
| `Schedule`    | `schedules`     | Departure/arrival times per train (unique per train+time) |
| `Compartment` | `compartments`  | Train compartments (A-E, ac or non_ac, 50 seats)  |
| `Seat`        | `seats`         | Individual seats (number, position: window/corridor)|
| `Booking`     | `bookings`      | Seat reservations with status lifecycle            |
| `Payment`     | `payments`      | Payment records linked to bookings                 |
| `AuditTrail`  | `audit_trail`   | Immutable log of all booking state changes         |

### Key constraints

- `bookings` has a unique constraint on `(schedule_id, seat_id)` -- one booking per seat per schedule.
- `bookings.idempotency_key` is unique -- prevents duplicate bookings from retries.
- `payments.idempotency_key` is unique -- prevents duplicate payments from retries.
- `schedules` has a unique constraint on `(train_id, departure_time)`.

### Migrations

Alembic manages schema migrations with async support:

```bash
cd /Users/ahnaftanjid/Documents/railbook/backend

# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration after model changes
uv run alembic revision --autogenerate -m "description of change"

# Downgrade one revision
uv run alembic downgrade -1
```

### Connection pool

The database engine is configured with:
- `pool_size=10` -- base pool connections
- `max_overflow=20` -- additional connections under load
- `pool_pre_ping=True` -- validates connections before use
- `pool_recycle=300` -- recycles connections every 5 minutes

---

## Seed Data

The seed function (`app/seed.py`) runs automatically on application startup and is idempotent (skips if data already exists).

**Seeded trains:**

| Name              | Number | Route              |
|-------------------|--------|--------------------|
| Subarna Express   | SE-701 | Dhaka - Chittagong |
| Ekota Express     | EE-501 | Dhaka - Rajshahi   |
| Mohanagar Provati | MP-301 | Dhaka - Sylhet     |

Each train has 5 compartments (A-E) with 50 seats each (250 seats total). Compartments A and B are AC (1500.00 per seat), C-E are non-AC (800.00 per seat).

Schedules are created for the next 7 days from the current date.

**Seeded users:**

| Email               | Password      | Role  |
|---------------------|---------------|-------|
| admin@railbook.com  | admin123      | admin |
| alice@example.com   | password123   | user  |
| bob@example.com     | password123   | user  |

---

## Testing

### Test database setup

Tests use a separate database named `railbook_test`. The test configuration automatically derives the test database URL from your `DATABASE_URL` by replacing the database name. Ensure the `railbook_test` database exists in your PostgreSQL instance:

```bash
docker exec -it <postgres_container> psql -U railbook -c "CREATE DATABASE railbook_test;"
```

The test fixtures (`conftest.py`) handle:
1. Dropping and recreating all tables at session start
2. Seeding the test database with the same seed data as production
3. Providing a test `AsyncClient` configured with the test database
4. Disabling rate limiting in tests by default
5. Cleaning up tables at session end

### Running tests

```bash
cd /Users/ahnaftanjid/Documents/railbook/backend

# Run all tests
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_bookings.py -v

# Run a specific test
uv run pytest tests/test_bookings.py::test_create_booking -v

# Run with stdout output
uv run pytest -v -s
```

### Test configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
testpaths = ["tests"]
```

All tests are async by default (no need for `@pytest.mark.asyncio`). The event loop is shared across the session for efficiency.

### Test fixtures

Key fixtures provided by `conftest.py`:

| Fixture        | Scope   | Description                                            |
|----------------|---------|--------------------------------------------------------|
| `test_engine`  | session | Creates test DB schema, seeds data, yields engine      |
| `session_factory` | session | Async session factory bound to test engine          |
| `db_session`   | function | Fresh async session per test                          |
| `client`       | function | `httpx.AsyncClient` with test DB and no rate limits   |
| `auth_headers` | function | Registers a unique test user and returns auth headers |

**Using `auth_headers` in tests:**

```python
async def test_something(client, auth_headers):
    resp = await client.get("/bookings", headers=auth_headers)
    assert resp.status_code == 200
```

### Writing concurrency tests

The project includes concurrency tests that use `asyncio.gather` against the actual database to verify that `SELECT FOR UPDATE` locking prevents double-bookings:

```python
import asyncio

async def test_double_booking(client, auth_headers, db_session):
    # Create two concurrent booking attempts for the same seat
    results = await asyncio.gather(
        client.post("/bookings", json=booking_data_1, headers=auth_headers_1),
        client.post("/bookings", json=booking_data_2, headers=auth_headers_2),
    )
    statuses = sorted([r.status_code for r in results])
    assert statuses == [201, 409]  # One succeeds, one conflicts
```

---

## Code Conventions

### Linting and formatting

The project uses [ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
cd /Users/ahnaftanjid/Documents/railbook/backend

# Check for lint errors and auto-fix
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check without fixing (CI mode)
uv run ruff check .
uv run ruff format --check .
```

**Ruff configuration** (from `pyproject.toml`):

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
exclude = ["migrations/versions/"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "SIM", "TCH"]
ignore = ["B008"]  # Allows function calls in default arguments (for Depends())
```

Selected rule sets:
- **E/W**: pycodestyle errors and warnings
- **F**: pyflakes
- **I**: isort (import sorting)
- **N**: pep8-naming
- **UP**: pyupgrade (modern Python syntax)
- **B**: flake8-bugbear (common bugs), with B008 ignored for FastAPI `Depends()`
- **A**: flake8-builtins
- **SIM**: flake8-simplify
- **TCH**: flake8-type-checking

### Async patterns

The entire backend is async. Follow these conventions:

1. **All database operations use `async/await`.** SQLAlchemy 2.0 async sessions are used throughout.

2. **Use `AsyncSession` from dependency injection**, not direct imports:
   ```python
   async def my_endpoint(session: AsyncSession = Depends(get_db)):
       result = await session.execute(select(Model))
   ```

3. **Use `with_for_update()` for row-level locks** when modifying resources that may be contested:
   ```python
   result = await session.execute(
       select(Booking).where(Booking.id == booking_id).with_for_update()
   )
   ```

4. **Flush before commit** when you need generated values (like IDs) within the same transaction:
   ```python
   session.add(new_record)
   await session.flush()  # new_record.id is now available
   # ... use new_record.id ...
   await session.commit()
   ```

5. **Redis connections are short-lived.** Get a connection, use it, close it:
   ```python
   redis = get_redis()
   try:
       result = await redis.get(key)
   finally:
       await redis.aclose()
   ```

### Project conventions

- **Pydantic models** use `model_config = {"from_attributes": True}` for ORM compatibility.
- **UUIDs** are used for all primary keys (generated with `uuid.uuid4`).
- **Idempotency keys** are required for all state-changing operations (bookings, payments).
- **Audit trail** is written within the same transaction as the state change to ensure consistency.
- **Rate limiting** degrades gracefully -- if Redis is unavailable, requests proceed without rate limiting.
- **Error handling** uses FastAPI's `HTTPException` with appropriate status codes. Service functions raise exceptions that routers propagate directly.

---

## Key Architectural Patterns

### Concurrency control

The booking system uses PostgreSQL `SELECT FOR UPDATE` to prevent double-booking. When two concurrent requests try to book the same seat:

1. Both execute `SELECT ... WHERE schedule_id = ? AND seat_id = ? FOR UPDATE`
2. The first to acquire the row lock proceeds; the second blocks
3. After the first commits, the second sees the existing booking and returns 409

### Idempotency

All mutating booking/payment operations require an `idempotency_key` (UUID):
- If the same key is sent again, the original result is returned without side effects
- This makes it safe to retry failed network requests

### Reservation expiry

Unpaid reservations expire after 5 minutes. A background asyncio task (`bookings/cleanup.py`) periodically scans for expired reservations and cancels them, freeing the seat for other users.

### Mock payment gateway

The payment gateway (`payments/gateway.py`) is a configurable mock:
- Default: 0% failure rate, 500ms latency
- Adjustable via `PUT /demo/config`
- Supports idempotent charges (same key returns same result)
- Useful for testing payment failure handling and race conditions
