# RailBook

Railway ticket booking system demonstrating concurrency handling with PostgreSQL row-level locking.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 async, asyncpg, PostgreSQL 16, Redis 7
- **Frontend**: React 18, Vite 6, React Router v6, Axios
- **Testing**: pytest-asyncio, httpx (34 async tests against real DB)
- **Linting**: Ruff (line-length=100, target py311)
- **Package mgmt**: uv (backend), npm (frontend)
- **Load testing**: Locust

## Project Layout

```
backend/app/           → FastAPI application
  main.py              → App, lifespan (seed + cleanup task), router registration
  config.py            → Pydantic Settings (env vars)
  database.py          → AsyncEngine, async_sessionmaker, get_db dependency
  models.py            → 8 SQLAlchemy ORM models (User, Train, Schedule, Compartment, Seat, Booking, Payment, AuditTrail)
  seed.py              → Idempotent seed data (3 trains, 150 seats, 3 users)
  auth/                → JWT auth (register, login, refresh, me)
  trains/              → Train listing, schedules, seat availability + Redis cache
  bookings/            → Core booking engine (SELECT FOR UPDATE), cleanup task
  payments/            → MockPaymentGateway (configurable failure/latency)
  audit/               → Atomic audit trail (same transaction as booking changes)
  ratelimit/           → Redis sliding window rate limiter
  demo/                → Race condition demo endpoint
  admin/               → Admin stats, occupancy, audit viewer
  redis.py             → Redis connection pool management
backend/migrations/    → Alembic async migrations
backend/tests/         → 34 async tests (conftest.py has all fixtures)
frontend/src/          → React SPA
  pages/               → 7 route pages
  components/          → SeatGrid, SeatCell, StatusBadge, ErrorAlert, Layout, ProtectedRoute
  context/             → AuthContext (JWT state management)
  api/client.js        → Axios instance with JWT interceptor
loadtest/              → Locust load tests + verify_integrity.py
docs/                  → Architecture, API reference, guides, Postman collection
```

## Commands

```bash
# Infrastructure
docker-compose up -d postgres redis          # Start DB + cache
docker-compose up --build                    # Full stack in Docker

# Backend (run from backend/)
uv sync                                      # Install deps
uv run alembic upgrade head                  # Apply migrations
uv run alembic revision --autogenerate -m "" # Create new migration
uv run uvicorn app.main:app --reload         # Start dev server (:8000)
uv run pytest -v                             # Run all 34 tests
uv run pytest tests/test_bookings.py -v      # Run specific file
uv run pytest -k test_double_booking -v      # Run specific test
uv run ruff check . --fix                    # Lint + autofix
uv run ruff format .                         # Format

# Frontend (run from frontend/)
npm install                                  # Install deps
npm run dev                                  # Dev server (:5173)
npm run build                                # Production build

# Load testing (run from loadtest/)
locust -f locustfile.py --host http://localhost:8000
python verify_integrity.py                   # Post-test integrity check
```

## Critical Patterns (DO NOT break these)

### 1. Atomic booking + audit
Every booking state change MUST call `log_audit()` inside the same `session` before `session.commit()`. The audit entry and the booking update are committed atomically. Never commit a booking status change without an audit entry.

### 2. SELECT FOR UPDATE locking
All booking mutations (create, pay, refund) MUST use `.with_for_update()` when loading the booking/seat row. This prevents double-booking race conditions.

### 3. Idempotency
`create_booking` and `pay_booking` both check for existing idempotency keys BEFORE doing work. If a duplicate key is found, return the existing result — do NOT create a new record.

### 4. Redis graceful degradation
All Redis calls MUST be wrapped in try/except. If Redis is unavailable, the operation proceeds without caching/rate-limiting. See `ratelimit/dependencies.py:_get_limiter()` and `trains/service.py` for the pattern.

### 5. Rate limit test isolation
Tests disable rate limiting by default via `app.dependency_overrides` in `conftest.py:client()`. The `test_rate_limit.py` file has its own `_make_rl_client()` that removes these overrides and patches `_get_limiter` to inject a mock. If you add new rate-limited endpoints, add the override to conftest.

### 6. Cancelled/refunded seat re-booking
When creating a booking, if an existing booking with `status` in `(cancelled, refunded)` exists for the same schedule+seat, it is deleted and a new one inserted in the same transaction. This preserves the UNIQUE constraint on `(schedule_id, seat_id)`.

## Module Pattern (router → service → model)

Each backend module follows: `router.py` (HTTP layer, depends) → `service.py` (business logic, takes session) → `models.py` (ORM). Schemas live in `schemas.py` per module. Services raise `HTTPException` directly. Routers do not contain business logic.

## Database

- **Models**: All in `backend/app/models.py` (single file)
- **Key constraint**: `UNIQUE(schedule_id, seat_id)` on bookings — one active booking per seat per schedule
- **Booking statuses**: reserved → confirmed → refunded, or reserved → cancelled
- **Migrations**: Alembic async, config in `alembic.ini`, env in `migrations/env.py`
- **Test DB**: `railbook_test` (derived from DATABASE_URL by replacing DB name)
- **Seed data**: 3 trains × 2 compartments × 25 seats = 150 seats, schedules for next 7 days, 3 users (admin/alice/bob)

## Environment Variables

See `.env.example` for all vars. Key ones:
- `DATABASE_URL` — PostgreSQL async connection string
- `REDIS_URL` — Redis connection string
- `JWT_SECRET` — MUST change in production

## Git Conventions

- No Claude signature in commits (no "Co-Authored-By", "Generated by Claude", etc.)
- Conventional commit messages: `feat:`, `fix:`, `test:`, `docs:`, `chore:`
- Do not amend published commits — create new ones
- No `--no-verify` or `--force` without explicit user request

## Testing Guidance

- All tests are async (asyncio_mode = "auto") — no `@pytest.mark.asyncio` needed
- Use `client` fixture for HTTP tests, `db_session` for direct DB access
- Use `auth_headers` fixture for authenticated requests (creates a unique user per test)
- Concurrency tests use `asyncio.gather` against separate clients with real DB
- For admin endpoints, login as `admin@railbook.com` / `admin123`
- When adding rate-limited endpoints, add override to `conftest.py:client()`

## Documentation Sync

When changing API endpoints, update these files:
- `docs/api/API_REFERENCE.md` — endpoint documentation
- `docs/api/ERROR_CODES.md` — if new error codes added
- `docs/postman/railbook.postman_collection.json` — Postman collection
- `README.md` — API endpoints table
- Backend module `schemas.py` — Pydantic request/response models

When changing models/schema:
- Create Alembic migration: `uv run alembic revision --autogenerate -m "description"`
- Update `docs/architecture/DATABASE.md`
- Update seed data in `app/seed.py` if new tables need initial data

When changing concurrency logic:
- Update `docs/architecture/CONCURRENCY.md`
- Add/update tests in `tests/test_concurrency.py`
- Verify `loadtest/verify_integrity.py` still covers the new pattern
