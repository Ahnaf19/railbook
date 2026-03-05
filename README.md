# RailBook

**A railway ticket booking system built to break — and then fix — every concurrency bug in the book.**

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-dc382d?style=flat-square&logo=redis&logoColor=white)
![Tests](https://img.shields.io/badge/tests-34%20passing-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

[Features](#features) · [Quick Start](#quick-start) · [Architecture](#architecture) · [Concurrency Deep Dive](#concurrency-deep-dive) · [API](#api-endpoints) · [Docs](#documentation) · [Contributing](#contributing)

---

## Why RailBook?

Booking systems fail in subtle ways. Two users click "Book" on the same seat at the same millisecond — who wins? A payment succeeds but the server crashes before recording it — is the user charged with no ticket? A user reserves a seat and walks away — is it locked forever?

RailBook is a full-stack ticket booking system that deliberately confronts these problems and solves them with PostgreSQL row-level locking, atomic transactions, idempotent operations, and background cleanup. Every solution is tested with real concurrent database operations — not mocks.

---

## Features

- **Race-condition-proof booking** — `SELECT FOR UPDATE` ensures exactly one winner when two users grab the same seat
- **5-minute reservation window** — unpaid bookings auto-expire via background cleanup with `SKIP LOCKED`
- **Idempotent everything** — unique keys on bookings and payments make retries safe, not dangerous
- **Atomic audit trail** — every state change (reserve, pay, cancel, refund, expire) logged in the same transaction
- **Sliding window rate limiting** — Redis sorted sets enforce per-user throttling with graceful degradation
- **Split-screen concurrency demo** — watch two users race for the same seat in real time
- **Visual seat map** — color-coded grid across 5 compartments (AC/Non-AC), 250 seats per train

---

## Quick Start

### Option A: Docker Compose (everything in one command)

```bash
docker-compose up --build
```

| Service  | URL                    |
|----------|------------------------|
| Frontend | http://localhost:3000   |
| API      | http://localhost:8000   |
| API Docs | http://localhost:8000/docs |

### Option B: Local development

<details>
<summary><strong>Step-by-step setup</strong></summary>

**Prerequisites:** Docker 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 18+

**1. Start PostgreSQL and Redis**

```bash
docker-compose up -d postgres redis
```

**2. Backend**

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # → http://localhost:8000
```

**3. Frontend**

```bash
cd frontend
npm install
npm run dev                             # → http://localhost:5173
```

**4. Verify**

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

</details>

### Demo accounts

| Email | Password | Role |
|-------|----------|------|
| `admin@railbook.com` | `admin123` | Admin |
| `alice@example.com` | `password123` | User |
| `bob@example.com` | `password123` | User |

---

## Architecture

```mermaid
graph TB
    subgraph Client
        UI["React 18 + Vite<br/><i>Seat grid, booking flow, demo page</i>"]
    end

    subgraph Backend["FastAPI (async)"]
        AUTH[Auth<br/>JWT + bcrypt]
        TRAINS[Trains<br/>Schedules, seats]
        BOOK[Booking Engine<br/>SELECT FOR UPDATE]
        PAY[Payment Gateway<br/>Mock, configurable]
        AUDIT[Audit Trail<br/>Atomic logging]
        RL[Rate Limiter<br/>Sliding window]
        DEMO[Demo<br/>Race condition]
        ADMIN[Admin<br/>Stats, occupancy]
        CLEANUP[Cleanup Task<br/>SKIP LOCKED]
    end

    subgraph Data
        PG[("PostgreSQL 16<br/>8 tables, row-level locks")]
        RD[("Redis 7<br/>Rate limits + seat cache")]
    end

    UI -->|HTTP + JWT| AUTH
    UI -->|REST| TRAINS
    UI -->|REST| BOOK
    UI -->|REST| DEMO
    UI -->|REST| ADMIN

    AUTH --> PG
    TRAINS --> PG
    TRAINS --> RD
    BOOK --> PG
    BOOK --> PAY
    BOOK --> AUDIT
    RL --> RD
    CLEANUP --> PG
    CLEANUP --> AUDIT
    ADMIN --> PG
```

### Booking state machine

```
                  ┌──────────┐
                  │ reserved │  (5-min TTL)
                  └────┬─────┘
                       │
            ┌──────────┼──────────┐
            │                     │
     pay succeeds          expires / pay fails
            │                     │
    ┌───────▼───────┐    ┌───────▼────────┐
    │   confirmed   │    │   cancelled    │
    └───────┬───────┘    └────────────────┘
            │
      refund (>1hr before departure)
            │
    ┌───────▼───────┐
    │   refunded    │
    └───────────────┘
```

Every arrow is a single database transaction that atomically updates `bookings.status` and inserts an `audit_trail` entry.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI + Uvicorn | Async HTTP with dependency injection |
| ORM | SQLAlchemy 2.0 async | Declarative models, `with_for_update()` |
| Database | PostgreSQL 16 + asyncpg | Row-level locks, ACID transactions |
| Cache | Redis 7 | Seat availability cache (5s TTL), rate limiting |
| Frontend | React 18 + Vite | SPA with seat grid and race demo |
| Auth | PyJWT + bcrypt | JWT access/refresh tokens |
| Testing | pytest-asyncio + httpx | 34 async tests with real DB concurrency |
| Load testing | Locust | 3 personas, post-test integrity verification |

---

## Concurrency Deep Dive

This is the core of the project. Five real concurrency problems, five tested solutions.

| # | Problem | What goes wrong | Solution | PostgreSQL mechanism |
|---|---------|----------------|----------|---------------------|
| 1 | **Double booking** | Two users book the same seat simultaneously — both succeed | `SELECT FOR UPDATE` acquires row lock; second transaction blocks until first commits, then sees conflict | Row-level exclusive lock |
| 2 | **Journey overlap** | User books two trains with overlapping departure/arrival times | Time range overlap query runs inside the same transaction as the seat lock | SQL predicate: `d1 < a2 AND a1 > d2` |
| 3 | **Duplicate operations** | Network timeout → client retries → user charged twice | Unique `idempotency_key` on bookings and payments; retry returns original result | UNIQUE constraint + early return |
| 4 | **Stale reservations** | User reserves seat, never pays — seat locked forever | 5-minute TTL + background cleanup task using `SKIP LOCKED` to avoid blocking active payments | Advisory skip with `FOR UPDATE SKIP LOCKED` |
| 5 | **Payment atomicity** | Payment succeeds at gateway but app crashes before DB write | Booking status + Payment record + Audit entry written in a single `session.commit()` | ACID transaction (all-or-nothing) |

Every solution has a corresponding test that uses `asyncio.gather` against the real database — not mocked:

```python
# Two concurrent booking attempts for the same seat
results = await asyncio.gather(
    client.post("/bookings", json=booking_a, headers=headers_a),
    client.post("/bookings", json=booking_b, headers=headers_b),
)
statuses = sorted([r.status_code for r in results])
assert statuses == [201, 409]  # Exactly one wins
```

Read the full analysis: [Concurrency Handling →](docs/architecture/CONCURRENCY.md)

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/health` | — | Health check |
| `POST` | `/auth/register` | — | Create account |
| `POST` | `/auth/login` | — | Get JWT tokens |
| `POST` | `/auth/refresh` | — | Refresh access token |
| `GET` | `/auth/me` | Bearer | Current user profile |
| `GET` | `/trains` | — | List all trains |
| `GET` | `/trains/{id}/schedules` | — | Schedules for a train |
| `GET` | `/trains/schedules/{id}/seats` | — | Seat availability (Redis-cached) |
| `POST` | `/bookings` | Bearer | Reserve a seat (5-min hold) |
| `POST` | `/bookings/{id}/pay` | Bearer | Pay and confirm booking |
| `POST` | `/bookings/{id}/refund` | Bearer | Refund confirmed booking |
| `GET` | `/bookings` | Bearer | List my bookings |
| `GET` | `/bookings/{id}` | Bearer | Booking detail |
| `POST` | `/demo/race-condition` | — | Trigger concurrent booking race |
| `GET` | `/demo/config` | — | View payment gateway config |
| `PUT` | `/demo/config` | — | Adjust failure rate / latency |
| `GET` | `/admin/stats` | Admin | Booking statistics |
| `GET` | `/admin/bookings` | Admin | All bookings (paginated) |
| `GET` | `/admin/occupancy` | Admin | Per-schedule occupancy rates |
| `GET` | `/admin/audit` | Admin | Full audit trail |

Interactive docs available at `/docs` (Swagger UI) when the server is running.

Full reference: [API Reference →](docs/api/API_REFERENCE.md)

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://railbook:railbook_secret@localhost:5432/railbook` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `JWT_SECRET` | `change-me-in-production-...` | JWT signing key |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `APP_ENV` | `development` | Environment name |

---

## Testing

```bash
cd backend
uv run pytest -v             # 34 tests, ~11s
uv run ruff check . --fix    # Lint
uv run ruff format .         # Format
```

Tests run against a real PostgreSQL database (`railbook_test`) with real concurrent operations. No mocks for database or concurrency logic.

| Test file | Tests | What's covered |
|-----------|-------|----------------|
| `test_auth.py` | 7 | Register, login, JWT, duplicates, refresh |
| `test_bookings.py` | 4 | Reserve → pay → confirm lifecycle |
| `test_concurrency.py` | 4 | Double booking, expired reservation, idempotency |
| `test_journey_overlap.py` | 1 | Overlapping journey detection |
| `test_payments.py` | 3 | Success, failure, idempotency |
| `test_refund.py` | 2 | Successful refund, invalid state refund |
| `test_rate_limit.py` | 7 | Thresholds, headers, per-user, graceful degradation |
| `test_trains.py` | 4 | Listing, schedules, availability, booking reflection |
| **Total** | **34** | |

### Load testing

```bash
cd loadtest
pip install -r requirements.txt
locust -f locustfile.py --host http://localhost:8000    # Web UI at :8089
python verify_integrity.py                               # Post-test DB integrity check
```

Three Locust personas simulate realistic traffic: casual browsers, rapid seat snipers, and mixed load. The integrity verifier checks for zero double bookings, complete audit trails, no stale reservations, and payment consistency.

Read more: [Load Testing Guide →](docs/guides/LOAD_TESTING_GUIDE.md)

---

## Project Structure

```
railbook/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, router registration
│   │   ├── config.py            # Environment configuration
│   │   ├── database.py          # Async engine + session factory
│   │   ├── models.py            # 8 SQLAlchemy ORM models
│   │   ├── seed.py              # Seed data (3 trains, 750 seats, demo users)
│   │   ├── auth/                # JWT authentication (register, login, refresh)
│   │   ├── trains/              # Train listing, schedules, seat availability
│   │   ├── bookings/            # Core booking engine + cleanup task
│   │   ├── payments/            # Mock payment gateway (configurable)
│   │   ├── audit/               # Atomic audit trail service
│   │   ├── ratelimit/           # Redis sliding window rate limiter
│   │   ├── demo/                # Race condition demo endpoints
│   │   └── admin/               # Admin stats, occupancy, audit viewer
│   ├── migrations/              # Alembic async migrations
│   └── tests/                   # 34 async tests
├── frontend/
│   └── src/
│       ├── pages/               # 7 route pages (trains, seats, booking, demo...)
│       ├── components/          # SeatGrid, StatusBadge, Layout, ErrorAlert
│       └── context/             # Auth state management
├── loadtest/                    # Locust load tests + integrity verifier
└── docs/                        # Architecture, API, guides, Postman collection
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture/ARCHITECTURE.md) | System design, component interactions, why PostgreSQL over message queues |
| [Concurrency Handling](docs/architecture/CONCURRENCY.md) | Deep dive into 5 concurrency problems with code-level explanations |
| [Database Schema](docs/architecture/DATABASE.md) | All 8 tables: columns, constraints, indexes, relationships |
| [API Reference](docs/api/API_REFERENCE.md) | Every endpoint with request/response schemas and curl examples |
| [Error Codes](docs/api/ERROR_CODES.md) | All error responses with HTTP status codes and troubleshooting |
| [Developer Guide](docs/guides/DEVELOPER_GUIDE.md) | Local setup, project structure, async patterns, testing |
| [User Guide](docs/guides/USER_GUIDE.md) | End-user walkthrough of the application |
| [Deployment Guide](docs/guides/DEPLOYMENT_GUIDE.md) | Docker deployment, env vars, production hardening |
| [Load Testing Guide](docs/guides/LOAD_TESTING_GUIDE.md) | Locust personas, integrity verification, interpreting results |
| [Postman Collection](docs/postman/) | Importable collection with auto-token management |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, coding standards, and pull request process.

**Quick version:**

```bash
# Fork and clone
cd backend
uv sync
uv run ruff check . --fix && uv run ruff format .
uv run pytest -v
# All green? Open a PR.
```

---

## License

[MIT](LICENSE) — use it however you want.
