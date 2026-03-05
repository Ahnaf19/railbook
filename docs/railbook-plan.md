# RailBook — Railway Ticket Booking System with Concurrency Showcase

## Idea

Ticket booking systems are deceptively simple on the surface but hide some of the hardest problems in backend engineering: race conditions when two users grab the same seat, payment failures mid-transaction leaving ghost bookings, journey overlap detection across time ranges, and maintaining consistency under concurrent load. Most portfolio projects show a CRUD booking app. This one deliberately exposes, demonstrates, and solves these concurrency problems — with a split-screen UI that lets you race two booking sessions against each other in real time.

## Goal

Build a railway ticket booking backend (FastAPI + PostgreSQL) with a miniature frontend that:

1. Handles the full ticket lifecycle: browse trains → select seat → pay (mock) → ticket issued → refund
2. Prevents double-booking via PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) and atomic transactions
3. Detects journey time clashes — if a user already holds a ticket for an overlapping time window, block the new booking
4. Includes a **Concurrency Demo Mode** — a split-screen UI that simulates two users (or the same user in two tabs) trying to book the same seat at the same time, visually showing how the system resolves the conflict
5. Analyzes and documents common real-world failure modes and how each is handled

## What This Demonstrates

- **Concurrency & locking**: SELECT FOR UPDATE, advisory locks, atomic transactions, optimistic vs pessimistic locking tradeoffs
- **Database design**: normalized schema, constraints as business logic (UNIQUE on seat+schedule, EXCLUDE for time overlaps), proper indexing
- **Transaction management**: multi-step flows (reserve → pay → confirm) with rollback on failure at any step
- **API design**: RESTful FastAPI with proper status codes, error responses, idempotency keys
- **Auth**: JWT-based authentication, role-based access (user vs admin)
- **Payment patterns**: mock payment gateway with simulated failures, retry logic, idempotent charge operations
- **Real-world failure analysis**: documented race conditions, phantom reads, lost updates, and how each is mitigated

---

## Real-World Concurrency Problems (Analysis & Solutions)

This section is a core part of the project — it should live in the README and be demonstrable.

### Problem 1: Double Booking (Lost Update)

**Scenario**: User A and User B both see seat 14A as available. Both click "Book." Without protection, both transactions read the seat as free, both write a booking → two tickets for one seat.

**Solution**: Pessimistic locking. When a booking attempt starts, `SELECT ... FOR UPDATE` locks the seat row. The second transaction blocks until the first commits or rolls back. If the seat is now taken, the second transaction gets a clear "seat unavailable" error.

**Demo**: Split-screen UI fires two simultaneous booking requests for the same seat. One succeeds (green), one fails with 409 Conflict (red). The sequence is logged with timestamps showing the lock wait.

### Problem 2: Payment Failure Mid-Transaction

**Scenario**: Seat is reserved (locked), payment gateway is called, payment fails (timeout, declined, network error). If we don't roll back, the seat stays locked forever (ghost reservation).

**Solution**: Two-phase booking with TTL. Step 1: reserve seat (status = `reserved`, `expires_at` = now + 5 min). Step 2: process payment. Step 3: on success → status = `confirmed`; on failure → status = `cancelled`, seat released. A background cleanup job releases expired reservations.

**Demo**: Trigger a mock payment failure. Show the reservation created, payment failing, seat released back to available.

### Problem 3: Journey Time Overlap

**Scenario**: User already has a ticket for Train A departing at 10:00 AM arriving at 2:00 PM. They try to book Train B departing at 12:00 PM. The journeys overlap — should be blocked.

**Solution**: At booking time, query user's active tickets and check for time range overlap using `tstzrange` overlap operator (`&&`) in PostgreSQL. Reject with a clear error if overlap exists.

### Problem 4: Phantom Reads Under Concurrent Seat Queries

**Scenario**: User queries available seats, gets a list, picks one, but by the time they submit — another user has taken it between the read and the write.

**Solution**: Don't trust the availability query. The actual booking operation uses `SELECT FOR UPDATE` regardless of what the frontend thinks is available. The availability endpoint is informational, not authoritative — the lock at booking time is the single source of truth.

### Problem 5: Idempotent Payments

**Scenario**: User clicks "Pay" twice (network lag, impatience). Without protection, they get charged twice.

**Solution**: Every booking gets an `idempotency_key` (UUID generated client-side). The payment endpoint checks if a payment with that key already exists — if yes, returns the existing result without re-charging.

---

## Data Model

### Tables

**users**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
email           TEXT UNIQUE NOT NULL
password_hash   TEXT NOT NULL
full_name       TEXT NOT NULL
phone           TEXT
role            TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin'))
created_at      TIMESTAMPTZ DEFAULT now()
```

**trains**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
name            TEXT NOT NULL              -- e.g. "Subarna Express"
train_number    TEXT UNIQUE NOT NULL       -- e.g. "SE-701"
origin          TEXT NOT NULL              -- e.g. "Dhaka"
destination     TEXT NOT NULL              -- e.g. "Chittagong"
```

**schedules** (a train can run on multiple days/times)

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
train_id        UUID REFERENCES trains(id)
departure_time  TIMESTAMPTZ NOT NULL
arrival_time    TIMESTAMPTZ NOT NULL
status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'cancelled'))
UNIQUE(train_id, departure_time)
```

**compartments**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
train_id        UUID REFERENCES trains(id)
name            TEXT NOT NULL              -- e.g. "A", "B", "C", "D", "E"
comp_type       TEXT NOT NULL CHECK (comp_type IN ('ac', 'non_ac'))
capacity        INTEGER DEFAULT 50
```

**seats**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
compartment_id  UUID REFERENCES compartments(id)
seat_number     INTEGER NOT NULL          -- 1-50
position        TEXT NOT NULL CHECK (position IN ('window', 'corridor'))
UNIQUE(compartment_id, seat_number)
```

**bookings**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id         UUID REFERENCES users(id)
schedule_id     UUID REFERENCES schedules(id)
seat_id         UUID REFERENCES seats(id)
status          TEXT DEFAULT 'reserved' CHECK (status IN ('reserved', 'confirmed', 'cancelled', 'refunded'))
idempotency_key UUID UNIQUE               -- prevents duplicate bookings
reserved_at     TIMESTAMPTZ DEFAULT now()
expires_at      TIMESTAMPTZ               -- reservation TTL (5 min)
confirmed_at    TIMESTAMPTZ
cancelled_at    TIMESTAMPTZ
total_amount    NUMERIC(10,2) NOT NULL
UNIQUE(schedule_id, seat_id)              -- ONE booking per seat per schedule (the critical constraint)
```

**payments**

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
booking_id      UUID REFERENCES bookings(id)
idempotency_key UUID UNIQUE NOT NULL
amount          NUMERIC(10,2) NOT NULL
status          TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed'))
gateway_ref     TEXT                       -- mock gateway reference ID
attempted_at    TIMESTAMPTZ DEFAULT now()
completed_at    TIMESTAMPTZ
failure_reason  TEXT
```

**audit_trail** (append-only, no UPDATE/DELETE ever)

```sql
id              BIGSERIAL PRIMARY KEY      -- BIGSERIAL for high-volume sequential writes
booking_id      UUID NOT NULL REFERENCES bookings(id)
user_id         UUID NOT NULL REFERENCES users(id)
action          TEXT NOT NULL              -- e.g. 'reserved', 'payment_attempted', 'payment_succeeded', 'payment_failed', 'confirmed', 'cancelled', 'refunded', 'expired_cleanup'
previous_status TEXT                       -- null for first event
new_status      TEXT NOT NULL
metadata        JSONB DEFAULT '{}'         -- flexible payload: payment_ref, failure_reason, ip_address, idempotency_key, etc.
ip_address      INET
created_at      TIMESTAMPTZ DEFAULT now() NOT NULL
```

**Index**: `CREATE INDEX idx_audit_booking ON audit_trail(booking_id, created_at);`

**Protection**: In production, use `REVOKE UPDATE, DELETE ON audit_trail FROM app_user;` to make it truly immutable. For this project, enforce immutability at the application layer — the service never issues UPDATE or DELETE on this table.

### Audit Trail Design Principles

- **Every booking state transition** gets an audit entry — no exceptions. This includes automated transitions (cleanup job expiring reservations).
- **Written in the same transaction** as the booking state change. If the booking update commits, the audit entry commits. If either fails, both roll back. This is why we don't use a message queue for this — atomicity matters more than decoupling.
- **metadata JSONB** carries context-specific data without schema changes:
  - For `payment_attempted`: `{"amount": "1500.00", "idempotency_key": "...", "gateway": "mock"}`
  - For `payment_failed`: `{"failure_reason": "Card declined", "idempotency_key": "..."}`
  - For `expired_cleanup`: `{"expired_at": "...", "reserved_at": "...", "ttl_seconds": 300}`
  - For all: `{"ip_address": "..."}` when available
- **Queryable**: admin can filter by booking_id, user_id, action, time range

### Key Constraints That Enforce Business Logic

- `UNIQUE(schedule_id, seat_id)` on bookings — database-level guarantee against double booking
- `UNIQUE(idempotency_key)` on bookings and payments — prevents duplicate submissions
- Journey overlap check is done in application code using:
  ```sql
  SELECT 1 FROM bookings b
  JOIN schedules s ON b.schedule_id = s.id
  WHERE b.user_id = $1
    AND b.status IN ('reserved', 'confirmed')
    AND tstzrange(s.departure_time, s.arrival_time) &&
        tstzrange($2, $3)  -- proposed journey time range
  LIMIT 1;
  ```

---

## Infrastructure Stack

| Component                | Technology                         | Purpose                                                                                                                           |
| ------------------------ | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Primary DB**           | PostgreSQL 16                      | Core data, row-level locking, audit trail (append-only table), constraints as business logic                                      |
| **Cache / Rate Limiter** | Redis 7 (Alpine)                   | Sliding window rate limiting on booking endpoints, short-TTL seat availability cache (5s) to reduce DB load on seat map refreshes |
| **Backend**              | FastAPI + asyncpg/SQLAlchemy async | Async API, WebSocket support if needed for demo                                                                                   |
| **Migrations**           | Alembic (async)                    | Schema versioning                                                                                                                 |
| **Auth**                 | JWT (PyJWT / python-jose) + bcrypt | Stateless auth, no external dependency                                                                                            |
| **Frontend**             | React (Vite) or plain HTML+JS      | Demo vehicle, not a production SPA                                                                                                |
| **Load Testing**         | Locust                             | Python-native, scriptable, has web UI for watching results                                                                        |
| **Containerization**     | Docker Compose                     | PostgreSQL + Redis + backend + frontend in one command                                                                            |

### Why NOT Kafka / MongoDB

**Kafka**: The audit trail writes happen inside the same DB transaction as the booking state change — they must be atomic. Decoupling via Kafka would mean audit records could be lost on consumer failure, defeating the "immutable compliance log" purpose. At this scale (single service, single DB), Kafka adds operational complexity without benefit. If this were a multi-service system with event sourcing, Kafka would be justified — but that's a different architecture.

**MongoDB**: All data is relational with strong consistency requirements. Bookings reference seats reference compartments reference trains. The UNIQUE constraint on `(schedule_id, seat_id)` is the core safety net — this is a relational problem.

## Architecture

```
┌─────────────────────────────────────────────┐
│            Frontend (React/HTML)             │
│                                             │
│  ┌─────────────┐     ┌─────────────┐       │
│  │  Session A   │     │  Session B   │       │
│  │  (Left Tab)  │     │  (Right Tab) │       │
│  └──────┬───────┘     └──────┬──────┘       │
│         │  Split-Screen Demo  │              │
└─────────┼─────────────────────┼──────────────┘
          │                     │
          ▼                     ▼
┌─────────────────────────────────────────────┐
│              FastAPI Backend                 │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Auth API │ │ Train API│ │ Booking API │ │
│  │ (JWT)    │ │          │ │ (+ locking) │ │
│  └──────────┘ └──────────┘ └──────┬──────┘ │
│                                    │        │
│  ┌───────────────┐      ┌─────────▼──────┐ │
│  │ Rate Limiter  │      │ Payment Service│ │
│  │ (Redis)       │      │ (Mock Gateway) │ │
│  └───────────────┘      └────────────────┘ │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ Background: Reservation Cleanup Job  │   │
│  │ (expires stale reservations)         │   │
│  └──────────────────────────────────────┘   │
└────────┬──────────────────┬─────────────────┘
         │                  │
         ▼                  ▼
┌────────────────┐  ┌──────────────┐
│   PostgreSQL   │  │    Redis     │
│ (locking,      │  │ (rate limit, │
│  audit trail)  │  │  seat cache) │
└────────────────┘  └──────────────┘
```

---

## API Endpoints

### Auth

- `POST /auth/register` — create user account
- `POST /auth/login` — returns JWT access token + refresh token
- `POST /auth/refresh` — refresh JWT
- `GET /auth/me` — current user profile

### Trains

- `GET /trains` — list all trains
- `GET /trains/{id}/schedules` — list upcoming schedules for a train
- `GET /schedules/{id}/seats` — list all seats with availability status for a specific schedule

### Bookings

- `POST /bookings` — body: `{schedule_id, seat_id, idempotency_key}` → reserve seat, return booking with payment URL
  - Acquires row lock on (schedule_id, seat_id)
  - Checks journey overlap for user
  - Creates booking with status=reserved, expires_at=now+5min
  - Returns booking_id + expected amount
- `POST /bookings/{id}/pay` — body: `{idempotency_key}` → process mock payment → confirm booking
  - Checks idempotency_key for duplicate
  - Calls mock payment gateway
  - On success: booking.status = confirmed
  - On failure: booking.status = cancelled, seat released
- `GET /bookings` — user's booking history (with status filter)
- `GET /bookings/{id}` — booking detail
- `POST /bookings/{id}/refund` — cancel confirmed booking, trigger mock refund
  - Only allowed for bookings where schedule departure > now + 1 hour
  - Sets status = refunded, releases seat

### Admin

- `GET /admin/bookings` — all bookings (admin only)
- `GET /admin/stats` — booking counts, revenue, occupancy rates

### Demo

- `POST /demo/race-condition` — server-side endpoint that spawns two concurrent booking attempts for the same seat, returns the result of both with timestamps and lock wait duration
- `GET /demo/config` — returns demo train/schedule/seat info for the frontend

---

## Mock Payment Gateway

A simple internal service (can be a module, not a separate service) that simulates payment processing:

```python
class MockPaymentGateway:
    """Simulates a payment gateway with configurable failure modes."""

    def __init__(self, failure_rate: float = 0.0, latency_ms: int = 500):
        self.failure_rate = failure_rate  # 0.0 to 1.0
        self.latency_ms = latency_ms

    async def charge(self, amount: Decimal, idempotency_key: str) -> PaymentResult:
        """
        Simulates a charge. Respects idempotency_key.
        Returns PaymentResult with gateway_ref on success, failure_reason on failure.
        """
        await asyncio.sleep(self.latency_ms / 1000)

        # Check idempotency — if same key was already charged, return same result
        if self._already_processed(idempotency_key):
            return self._get_previous_result(idempotency_key)

        # Simulate random failure
        if random.random() < self.failure_rate:
            return PaymentResult(status="failed", failure_reason="Card declined (simulated)")

        return PaymentResult(status="success", gateway_ref=f"MOCK-{uuid4().hex[:8]}")

    async def refund(self, gateway_ref: str) -> RefundResult:
        """Simulates a refund."""
        await asyncio.sleep(self.latency_ms / 1000)
        return RefundResult(status="success", refund_ref=f"REFUND-{uuid4().hex[:8]}")
```

The demo mode can set `failure_rate=0.3` to show payment failure handling.

---

## Docker Compose

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: railbook
      POSTGRES_USER: railbook
      POSTGRES_PASSWORD: railbook
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgresql+asyncpg://railbook:railbook@postgres:5432/railbook
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: change-me-in-production
      MOCK_PAYMENT_FAILURE_RATE: "0.0"

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  pgdata:
```

---

## Frontend (Miniature — Demo-Focused)

A single-page app with these views:

### 1. Login / Register

Simple form. Stores JWT in memory (not localStorage for the artifact, but fine for standalone deployment).

### 2. Train Browser

List trains → pick schedule → see seat map (grid of 5 compartments × 50 seats, color-coded: green=available, red=booked, yellow=reserved). Click a seat to start booking.

### 3. Booking Flow

Select seat → confirm → mock payment → ticket issued. Shows clear status transitions.

### 4. My Tickets

Purchase history with status badges. Refund button on eligible tickets.

### 5. Concurrency Demo (the star feature)

**Split-screen view**: two booking panels side by side, both logged in (can be same user or different users). Both panels show the same seat map for the same schedule.

Flow:

1. Select the same seat in both panels
2. Click "Book Simultaneously" button
3. Both panels fire `POST /bookings` at the exact same time (using `Promise.all` or similar)
4. Watch the result: one panel turns green (success), the other turns red (409 Conflict)
5. A timeline below shows what happened: which request acquired the lock first, how long the second waited, and the final outcome
6. Option to run the demo with mock payment failures enabled

---

## Rate Limiting (Redis Sliding Window)

### Why

Without rate limiting, a bot can spam `POST /bookings` and reserve every seat on a schedule within seconds — locking out real users for the 5-minute reservation TTL. Even with the cleanup job, this creates a denial-of-service window.

### Strategy

**Sliding window counter** in Redis, keyed per user per endpoint category.

| Endpoint Category | Limit        | Window    | Key Pattern            |
| ----------------- | ------------ | --------- | ---------------------- |
| Booking creation  | 5 requests   | 1 minute  | `rl:booking:{user_id}` |
| Payment attempts  | 3 requests   | 1 minute  | `rl:payment:{user_id}` |
| Auth (login)      | 10 requests  | 5 minutes | `rl:auth:{ip_address}` |
| General API       | 100 requests | 1 minute  | `rl:api:{user_id}`     |

### Implementation

```python
class RateLimiter:
    """Redis sliding window rate limiter."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """
        Returns RateLimitResult(allowed=True/False, remaining=N, retry_after=seconds).
        Uses Redis MULTI/EXEC for atomic increment + expire.
        """
        now = time.time()
        window_start = now - window_seconds
        pipe = self.redis.pipeline()
        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Count requests in window
        pipe.zcard(key)
        # Set TTL on key
        pipe.expire(key, window_seconds)
        _, _, count, _ = await pipe.execute()

        if count > limit:
            return RateLimitResult(allowed=False, remaining=0, retry_after=window_seconds)
        return RateLimitResult(allowed=True, remaining=limit - count)
```

### FastAPI Integration

A dependency that injects rate limiting:

```python
async def rate_limit_booking(
    request: Request,
    user: User = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    result = await limiter.check(f"rl:booking:{user.id}", limit=5, window_seconds=60)
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many booking attempts",
            headers={"Retry-After": str(result.retry_after)},
        )
```

Response headers on every rate-limited endpoint:

- `X-RateLimit-Limit`: max requests
- `X-RateLimit-Remaining`: requests left
- `X-RateLimit-Reset`: seconds until window resets

---

## Seat Availability Cache (Redis)

To avoid hammering PostgreSQL every time someone loads a seat map:

- **Cache key**: `seats:{schedule_id}` → JSON of seat availability
- **TTL**: 5 seconds (short enough to stay near-real-time, long enough to absorb bursts)
- **Invalidation**: on any booking state change (reserve, confirm, cancel, refund, cleanup), delete the cache key for that schedule_id
- **Fallback**: if Redis is down, query PostgreSQL directly (cache is an optimization, not a requirement)

---

## Load Testing (Locust)

### Purpose

Prove the locking actually works under real concurrent load — not just two requests, but hundreds. Also measures throughput, latency percentiles, and identifies bottlenecks.

### Test Scenarios

```python
# loadtest/locustfile.py

class TicketBuyer(HttpUser):
    """Simulates a normal user browsing and booking."""
    wait_time = between(1, 3)

    def on_start(self):
        # Register + login, store JWT
        ...

    @task(5)
    def browse_trains(self):
        self.client.get("/trains")

    @task(3)
    def view_seat_map(self):
        self.client.get(f"/schedules/{random_schedule_id}/seats")

    @task(1)
    def book_and_pay(self):
        # Pick a random available seat, attempt to book + pay
        ...


class SeatSniper(HttpUser):
    """Simulates a scalping bot targeting a specific popular seat."""
    wait_time = constant(0)  # no wait — max aggression

    @task
    def snipe_seat(self):
        # Always targets the same seat — tests locking under contention
        self.client.post("/bookings", json={
            "schedule_id": TARGET_SCHEDULE,
            "seat_id": TARGET_SEAT,
            "idempotency_key": str(uuid4()),
        })


class StressTest(HttpUser):
    """Mixed load: 80% browsers, 15% bookers, 5% snipers."""
    ...
```

### What We Measure

- **Correctness**: after the load test, assert zero double-bookings exist (`SELECT schedule_id, seat_id, COUNT(*) FROM bookings WHERE status IN ('reserved','confirmed') GROUP BY 1,2 HAVING COUNT(*) > 1` returns 0 rows)
- **Throughput**: requests/second for each endpoint
- **Latency**: p50, p95, p99 response times
- **Lock contention**: how long blocked transactions wait (logged by the booking service)
- **Rate limiting**: verify snipers get 429s after exceeding limit
- **Error rate**: percentage of 5xx errors (should be ~0%)

### Directory

```
loadtest/
├── locustfile.py         # main test scenarios
├── config.py             # target URLs, user counts, spawn rates
├── verify_integrity.py   # post-test DB integrity check script
└── README.md             # how to run, what to expect
```

### How to Run

```bash
# Start the full stack
docker-compose up -d

# Run Locust (web UI on :8089)
cd loadtest && locust -f locustfile.py --host=http://localhost:8000

# Or headless for CI
locust -f locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 --run-time 60s

# After test — verify no double bookings
python verify_integrity.py
```

---

## Reservation Cleanup Background Job

```python
async def cleanup_expired_reservations():
    """Runs every 60 seconds. Releases seats from expired reservations."""
    while True:
        async with db.transaction():
            result = await db.execute("""
                UPDATE bookings
                SET status = 'cancelled', cancelled_at = now()
                WHERE status = 'reserved'
                  AND expires_at < now()
                RETURNING id, seat_id, schedule_id
            """)
            if result:
                logger.info(f"Cleaned up {len(result)} expired reservations")
        await asyncio.sleep(60)
```

---

## Seed Data

Pre-populated on first run:

### Trains (3)

| Name              | Number | Origin | Destination |
| ----------------- | ------ | ------ | ----------- |
| Subarna Express   | SE-701 | Dhaka  | Chittagong  |
| Ekota Express     | EE-501 | Dhaka  | Rajshahi    |
| Mohanagar Provati | MP-301 | Dhaka  | Sylhet      |

### Compartments (5 per train = 15 total)

| Compartment | Type   | Seats |
| ----------- | ------ | ----- |
| A           | AC     | 50    |
| B           | AC     | 50    |
| C           | Non-AC | 50    |
| D           | Non-AC | 50    |
| E           | Non-AC | 50    |

### Seats (50 per compartment = 250 per train = 750 total)

- Seats 1-50 per compartment
- Position: seats ending in 1,4,5,8 = window; others = corridor (mimics real 2+2 layout)

### Schedules (2 per train = 6 total)

Generate schedules for the next 7 days with realistic departure/arrival times.

---

## Documentation Structure

Documentation is separated by audience and purpose:

```
docs/
├── architecture/
│   ├── ARCHITECTURE.md        # system design, infra decisions, data flow
│   ├── CONCURRENCY.md         # deep dive on all 5 concurrency problems + solutions
│   └── DATABASE.md            # schema design rationale, indexes, constraints
├── api/
│   ├── API_REFERENCE.md       # full endpoint reference with request/response examples
│   └── ERROR_CODES.md         # all error codes, meanings, and client handling guidance
├── guides/
│   ├── USER_GUIDE.md          # end-user walkthrough: register → book → refund (with screenshots placeholders)
│   ├── DEVELOPER_GUIDE.md     # local setup, project structure, how to add features, coding conventions
│   ├── DEPLOYMENT_GUIDE.md    # docker-compose, env vars, production considerations
│   └── LOAD_TESTING_GUIDE.md  # how to run Locust, interpret results, verify integrity
├── postman/
│   ├── railbook.postman_collection.json   # full API collection organized by folder
│   ├── railbook.local.postman_environment.json  # local dev env vars
│   └── README.md              # how to import and use the collection
└── diagrams/
    └── railbook.excalidraw    # architecture diagram (Excalidraw source)
```

### Postman Collection Structure

The collection is organized into folders matching API modules:

```
RailBook API/
├── Auth/
│   ├── Register
│   ├── Login
│   ├── Refresh Token
│   └── Get Current User
├── Trains/
│   ├── List Trains
│   ├── Get Train Schedules
│   └── Get Seat Availability
├── Bookings/
│   ├── Create Booking (Reserve)
│   ├── Pay for Booking
│   ├── Get Booking Details
│   ├── List My Bookings
│   └── Refund Booking
├── Admin/
│   ├── List All Bookings
│   ├── Get Stats
│   ├── Query Audit Trail
│   └── Get Booking Audit History
└── Demo/
    ├── Race Condition Test
    └── Get Demo Config
```

**Environment variables** (`railbook.local.postman_environment.json`):

```json
{
  "base_url": "http://localhost:8000",
  "access_token": "",
  "refresh_token": "",
  "user_id": "",
  "admin_token": "",
  "demo_schedule_id": "",
  "demo_seat_id": ""
}
```

**Collection-level scripts**:

- Pre-request: auto-inject `Authorization: Bearer {{access_token}}` on authenticated endpoints
- Login request: auto-extract and save `access_token` and `refresh_token` to environment
- Demo config request: auto-save `demo_schedule_id` and `demo_seat_id` for use in race condition test

---

### Per-Directory READMEs

Every significant directory gets its own README explaining what lives there and how to work with it:

| File                           | Purpose                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `README.md`                    | Top-level project overview, quick start, architecture summary                |
| `backend/README.md`            | Backend setup, dependencies, how to run locally, migration workflow, testing |
| `backend/migrations/README.md` | How Alembic is configured, how to create/apply/rollback migrations           |
| `backend/tests/README.md`      | Test structure, how to run, what each test file covers, how to add tests     |
| `frontend/README.md`           | Frontend setup, dev server, build, environment variables                     |
| `loadtest/README.md`           | How to run Locust, test personas explained, integrity verification           |
| `docs/README.md`               | Documentation index — links to all guides and references                     |
| `docs/postman/README.md`       | How to import collection, workflow walkthrough using Postman                 |

---

### Alembic Migration Workflow

```
backend/
├── alembic.ini                  # points to migrations/, uses DATABASE_URL from env
├── migrations/
│   ├── env.py                   # async migration runner (uses asyncpg)
│   ├── script.py.mako           # migration template
│   └── versions/
│       ├── 001_initial_schema.py  # all tables: users, trains, compartments, seats, schedules, bookings, payments, audit_trail
│       └── 002_seed_data.py       # optional: seed data as a migration (alternative to seed.py)
```

**Commands** (documented in `backend/migrations/README.md`):

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply all pending migrations
uv run alembic upgrade head

# Rollback last migration
uv run alembic downgrade -1

# Show current migration state
uv run alembic current

# Show migration history
uv run alembic history
```

**Conventions**:

- Migration filenames are prefixed with sequential numbers (001*, 002*) for readability
- Each migration has both `upgrade()` and `downgrade()` — every migration must be reversible
- Schema changes go in migrations, never in application startup code
- Seed data can optionally be a migration OR a standalone `seed.py` — the implementation can decide which is cleaner

---

## Directory Structure

```
railbook/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app + lifespan
│   │   ├── config.py            # settings (DB URL, JWT secret, etc.)
│   │   ├── database.py          # async PostgreSQL connection (asyncpg or SQLAlchemy async)
│   │   ├── auth/
│   │   │   ├── router.py        # auth endpoints
│   │   │   ├── service.py       # JWT creation/validation, password hashing
│   │   │   ├── dependencies.py  # get_current_user dependency
│   │   │   └── schemas.py
│   │   ├── trains/
│   │   │   ├── router.py        # train + schedule + seat endpoints
│   │   │   ├── service.py       # query logic
│   │   │   └── schemas.py
│   │   ├── bookings/
│   │   │   ├── router.py        # booking + payment + refund endpoints
│   │   │   ├── service.py       # booking logic WITH locking
│   │   │   ├── schemas.py
│   │   │   └── cleanup.py       # expired reservation cleanup job
│   │   ├── payments/
│   │   │   ├── gateway.py       # MockPaymentGateway
│   │   │   └── schemas.py
│   │   ├── demo/
│   │   │   ├── router.py        # demo endpoints (race condition trigger)
│   │   │   └── service.py
│   │   ├── admin/
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   └── seed.py              # seed data loader
│   ├── migrations/               # alembic migrations
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_bookings.py
│   │   ├── test_concurrency.py  # THE key test file — race conditions
│   │   ├── test_payments.py
│   │   ├── test_journey_overlap.py
│   │   └── test_refund.py
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                     # minimal React or plain HTML+JS
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Trains.jsx
│   │   │   ├── SeatMap.jsx
│   │   │   ├── Booking.jsx
│   │   │   ├── MyTickets.jsx
│   │   │   └── ConcurrencyDemo.jsx  # split-screen demo
│   │   └── api/
│   │       └── client.js         # API client wrapper
│   └── Dockerfile
├── docker-compose.yml            # PostgreSQL + backend + frontend
├── PLAN.md
├── CLAUDE.md
└── README.md
```

---

## Build Order (7 hours)

| Block | Time      | Deliverable                                                                                                                                                                |
| ----- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | 0:00–0:30 | Project scaffold, Docker setup (PostgreSQL + Redis + FastAPI), database + Redis connections, config, Alembic setup                                                         |
| 2     | 0:30–1:15 | Schema migrations (all tables including audit_trail), seed data, auth module (register, login, JWT, middleware)                                                            |
| 3     | 1:15–2:00 | Trains module (list trains, schedules, seat availability with Redis cache)                                                                                                 |
| 4     | 2:00–3:00 | Booking engine: reserve with SELECT FOR UPDATE, journey overlap check, payment flow, confirm/cancel, idempotency. **Audit trail writes inside every booking transaction.** |
| 5     | 3:00–3:30 | Payment module (MockPaymentGateway), refund flow, reservation cleanup background job                                                                                       |
| 6     | 3:30–4:00 | Rate limiting module (Redis sliding window, FastAPI dependencies, response headers). Audit query endpoints (admin).                                                        |
| 7     | 4:00–4:20 | Concurrency tests, audit trail tests, rate limit tests, demo endpoint                                                                                                      |
| 8     | 4:20–5:00 | Frontend: login, train browser, seat map, booking flow, my tickets                                                                                                         |
| 9     | 5:00–5:30 | Frontend: concurrency demo split-screen                                                                                                                                    |
| 10    | 5:30–6:00 | Load testing: Locust scenarios, integrity verification script                                                                                                              |
| 11    | 6:00–6:30 | Documentation: all docs/ structure, API reference, user guide, developer guide, architecture docs                                                                          |
| 12    | 6:30–7:00 | Postman collection + env, per-directory READMEs, root README, .env.example, Excalidraw diagram, final quality pass                                                         |

---

## Future Scope

- **Real Bangladesh Railway data**: actual train routes, stations, timetables, fare matrices
- **Multi-leg journeys**: book Dhaka → Comilla → Chittagong as a single ticket with intermediate stops
- **Dynamic pricing**: fare varies by demand, time of day, AC vs non-AC, advance booking window
- **Waiting list**: if all seats are booked, join a queue — auto-assign when a cancellation happens
- **Seat preference engine**: ML model that recommends seats based on user history (window lover, always compartment B, etc.)
- **Real payment gateway**: SSLCommerz or bKash integration (popular in Bangladesh)
- **Notification system**: email/SMS confirmation, departure reminders, refund status updates
- **Distributed locking**: if scaled to multiple backend instances, use Redis-based distributed locks (Redlock) instead of PostgreSQL row locks
- **Offline ticket validation**: QR code on ticket, scanned by conductor app
- **Event sourcing**: replace audit trail with full event sourcing via Kafka for multi-service architectures
- **Admin dashboard frontend**: visual analytics, booking heatmaps, revenue charts
