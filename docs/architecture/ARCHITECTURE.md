# RailBook System Architecture

## Overview

RailBook is a railway ticket booking system built to demonstrate correct handling of concurrency, data integrity, and real-time seat availability in a multi-user environment. The system allows users to browse trains and schedules, reserve seats with a 5-minute hold window, pay to confirm, and request refunds -- all while preventing double bookings and overlapping journeys at the database level.

---

## Tech Stack

| Layer           | Technology                        | Role                                              |
|-----------------|-----------------------------------|---------------------------------------------------|
| API Framework   | FastAPI 0.100+                    | Async HTTP API with OpenAPI docs                  |
| ORM             | SQLAlchemy 2.0 (async)            | Models, relationships, row-level locking          |
| Database        | PostgreSQL                        | ACID transactions, `SELECT FOR UPDATE`            |
| Cache / Limiter | Redis                             | Seat availability cache, sliding window rate limit|
| Auth            | PyJWT + bcrypt                    | HS256 JWT access/refresh tokens                   |
| Frontend        | React + Vite                      | SPA served on port 5173                           |
| Migrations      | Alembic                           | Schema versioning via SQLAlchemy metadata         |
| Driver          | asyncpg (via SQLAlchemy)          | Async PostgreSQL wire protocol                    |
| Config          | pydantic-settings                 | Typed env-based configuration                     |
| Logging         | Loguru                            | Structured logging throughout                     |

### Why SQLAlchemy 2.0 over raw asyncpg

The project uses SQLAlchemy's async ORM (`sqlalchemy.ext.asyncio`) on top of the asyncpg driver rather than writing raw asyncpg queries. The reasons:

1. **Transactional composition.** Booking requires multiple reads and writes (lock seat, check overlap, create booking, write audit) inside a single database transaction. SQLAlchemy's `AsyncSession` makes it natural to pass a session through service functions and call `session.commit()` once at the end, ensuring atomicity without manual `BEGIN`/`COMMIT` wiring.

2. **Alembic integration.** SQLAlchemy's `DeclarativeBase` models serve double duty -- they define the runtime ORM and the migration source of truth. Alembic's `--autogenerate` reads the same model metadata to produce migration scripts. With raw asyncpg, you would need to maintain SQL migration files separately from application models.

3. **Relationship loading.** Models like `Booking` reference `User`, `Schedule`, `Seat`, `Payment`, and `AuditTrail` through `relationship()` declarations. SQLAlchemy handles lazy/eager loading, which would require manual JOIN construction with raw asyncpg.

4. **Row-level locking DSL.** The `.with_for_update()` and `.with_for_update(skip_locked=True)` query modifiers translate directly to PostgreSQL's `SELECT ... FOR UPDATE [SKIP LOCKED]`. This is a single method call in SQLAlchemy versus string-interpolated SQL with asyncpg.

5. **Type safety.** SQLAlchemy 2.0's `Mapped[]` annotations provide static type information for model columns, giving IDE support and catching errors at development time.

The trade-off is a small overhead per query (SQLAlchemy's statement compilation). For a booking system where correctness matters more than microsecond latency, this is the right trade.

---

## Request Flow

```
                    +------------------+
                    |  React Frontend  |
                    |  (Vite :5173)    |
                    +--------+---------+
                             |
                        HTTP | (JSON)
                             |
                    +--------v---------+
                    |   FastAPI App    |
                    |   (:8000)        |
                    +--+-----+-----+--+
                       |     |     |
          +------------+     |     +------------+
          |                  |                  |
   +------v------+   +------v------+   +-------v------+
   | Auth Router  |   |Train Router |   |Booking Router|
   | /auth/*      |   |/trains/*    |   |/bookings/*   |
   +--------------+   +------+------+   +------+-------+
                             |                 |
                             |    +------------+----------+
                             |    |            |          |
                       +-----v----v-+   +------v---+ +---v--------+
                       | PostgreSQL  |   |  Redis   | | Payment    |
                       | (SQLAlchemy |   |  Cache & | | Gateway    |
                       |  async)     |   |  Rate    | | (mock)     |
                       +-------------+   |  Limiter | +------------+
                                         +----------+
```

### Detailed request lifecycle for `POST /bookings`

```
Client
  |
  |  POST /bookings {schedule_id, seat_id, idempotency_key}
  |  Authorization: Bearer <access_token>
  v
FastAPI Dependency Injection
  |
  +---> get_current_user()       # Decode JWT, load User from DB
  +---> rate_limit_booking()     # Redis sorted-set sliding window (5 req/60s)
  +---> get_db()                 # Yield AsyncSession from connection pool
  |
  v
bookings.service.create_booking(session, ...)
  |
  |  1. SELECT ... WHERE idempotency_key = ?        (idempotency check)
  |  2. SELECT ... WHERE schedule_id = ? AND seat_id = ?
  |     FOR UPDATE                                   (row-level lock)
  |  3. SELECT ... JOIN schedules WHERE user_id = ?
  |     AND time ranges overlap                      (journey overlap)
  |  4. Calculate price from compartment type
  |  5. INSERT INTO bookings (status='reserved', expires_at=now+5min)
  |  6. INSERT INTO audit_trail (action='reserved')
  |  7. COMMIT
  |  8. DELETE Redis key "seats:{schedule_id}"       (cache invalidation)
  |
  v
Response: 201 { booking object }
```

Steps 1 through 7 execute inside a single PostgreSQL transaction. If any step fails, the entire transaction rolls back. Step 8 is best-effort -- if Redis is down, the response still succeeds and the cache expires naturally via its 5-second TTL.

---

## Key Design Decisions

### 1. Row-Level Locking (`SELECT FOR UPDATE`)

Every mutation on a booking (create, pay, refund) acquires a row-level lock before modifying state. This is PostgreSQL's `FOR UPDATE` clause, exposed in SQLAlchemy as `.with_for_update()`.

**Why not application-level locking?** Distributed locks (Redis SETNX, advisory locks) add failure modes -- what if Redis is down, or the lock holder crashes? PostgreSQL row locks are tied to the transaction lifetime: if the process dies, PostgreSQL automatically releases the lock when the connection drops. This makes the system self-healing.

**Why not SERIALIZABLE isolation?** SERIALIZABLE causes retries on any detected conflict, even read-only overlaps. `SELECT FOR UPDATE` under READ COMMITTED is more surgical: it only blocks when two transactions try to lock the same row, which is exactly the conflict we care about (two users booking the same seat).

### 2. Sliding Window Rate Limiting

The rate limiter uses a Redis sorted set per user/endpoint combination. Each request adds a member scored by the current Unix timestamp. Before counting, it removes members older than the window. This is the "sliding window log" algorithm.

```
Key:    rl:booking:{user_id}
Score:  Unix timestamp of each request
Member: String representation of the timestamp
```

The implementation runs all four operations (ZREMRANGEBYSCORE, ZADD, ZCARD, EXPIRE) in a single Redis pipeline to minimize round trips. If Redis is unavailable, the limiter degrades gracefully by allowing the request -- the system prioritizes availability over strict rate enforcement.

Three rate limit tiers are configured:
- **Booking creation**: 5 requests per 60 seconds per user
- **Payment/refund**: 3 requests per 60 seconds per user
- **Authentication**: 10 requests per 5 minutes per IP address

### 3. Audit Trail Pattern

Every booking state change is recorded in the `audit_trail` table within the same database transaction as the state change itself. The `log_audit()` function takes the active `AsyncSession` and calls `session.add()` without committing -- the caller commits both the booking mutation and the audit entry atomically.

This guarantees that:
- Every booking state transition has a corresponding audit record.
- If the transaction rolls back (e.g., a constraint violation), no orphaned audit entries exist.
- The audit trail records the previous status, new status, action name, user ID, IP address, and arbitrary JSON metadata (e.g., gateway reference for payments, failure reasons).

The `audit_trail` table uses a `BigInteger` auto-incrementing primary key instead of UUID. This is deliberate: audit entries are append-only and queried in chronological order. A sequential integer ensures index locality and efficient range scans, unlike random UUIDs which fragment B-tree indexes.

### 4. Reservation Expiry with Background Cleanup

Bookings start in `reserved` status with `expires_at` set to 5 minutes in the future. A background `asyncio.Task` runs every 60 seconds, querying for expired reservations using `SELECT FOR UPDATE SKIP LOCKED`. The `SKIP LOCKED` clause ensures that if another transaction is already processing a booking (e.g., the user is paying right now), the cleanup task skips it rather than blocking.

Expired bookings are transitioned to `cancelled` status with a system-user audit entry. This approach avoids the need for a separate job scheduler (Celery, APScheduler) and keeps the cleanup logic inside the same process, sharing the same database session factory.

### 5. Redis as Optional Infrastructure

Redis is used for two purposes: seat availability caching (5-second TTL) and rate limiting. Both are wrapped in try/except blocks that log a warning and continue if Redis is unavailable. The system functions correctly without Redis -- queries hit PostgreSQL directly, and rate limits are not enforced. This means Redis is a performance optimization, not a correctness requirement.

### 6. Connection Pool Configuration

The SQLAlchemy async engine is configured with:
- `pool_size=10`: 10 persistent connections
- `max_overflow=20`: up to 20 additional connections under load (30 total)
- `pool_pre_ping=True`: validate connections before checkout (detects stale TCP)
- `pool_recycle=300`: recycle connections every 5 minutes (prevents idle timeouts)

Redis uses a shared `ConnectionPool` with `max_connections=20` and `decode_responses=True`.

### 7. Mock Payment Gateway

The payment gateway is a module-level singleton (`MockPaymentGateway`) with configurable failure rate and latency. It maintains its own idempotency map (`_processed` dict keyed by idempotency key) to simulate real gateway behavior. The `/demo/config` endpoints allow adjusting failure rate and latency at runtime for testing.

---

## Module Map

```
backend/app/
  main.py              FastAPI app factory, lifespan (startup/shutdown), CORS
  config.py            Pydantic Settings (DATABASE_URL, REDIS_URL, JWT_*)
  database.py          AsyncEngine, async_sessionmaker, get_db dependency
  models.py            8 SQLAlchemy models (User through AuditTrail)
  redis.py             Redis connection pool, get_redis(), close_redis_pool()
  seed.py              Idempotent seed: 3 trains, 2 compartments each, 25 seats each, 7 days of schedules

  auth/
    router.py          POST /auth/register, /login, /refresh, GET /auth/me
    service.py         register_user, authenticate_user, JWT creation/decoding
    dependencies.py    get_current_user (Bearer token extraction)
    schemas.py         Request/response Pydantic models

  trains/
    router.py          GET /trains, /{id}/schedules, /schedules/{id}/seats
    service.py         list_trains, list_schedules, get_seat_availability (with Redis cache)
    schemas.py         Response models

  bookings/
    router.py          POST /bookings, /{id}/pay, /{id}/refund, GET /bookings
    service.py         create_booking, pay_booking, refund_booking (core concurrency logic)
    cleanup.py         Background task: expire stale reservations with SKIP LOCKED
    schemas.py         Request/response models

  payments/
    gateway.py         MockPaymentGateway with configurable failure rate

  audit/
    service.py         log_audit() -- append-only, called within booking transactions

  ratelimit/
    limiter.py         RateLimiter class (Redis sorted-set sliding window)
    dependencies.py    FastAPI dependencies: rate_limit_booking, rate_limit_payment, rate_limit_auth

  demo/
    router.py          POST /demo/race-condition, GET/PUT /demo/config
    service.py         run_race() -- two concurrent booking attempts for demos

  admin/
    router.py          Admin statistics endpoints
```

---

## API Routes Summary

| Method | Path                              | Auth     | Rate Limit      | Description                    |
|--------|-----------------------------------|----------|-----------------|--------------------------------|
| POST   | `/auth/register`                  | No       | 10/5min per IP  | Create account, return tokens  |
| POST   | `/auth/login`                     | No       | 10/5min per IP  | Authenticate, return tokens    |
| POST   | `/auth/refresh`                   | No       | 10/5min per IP  | Refresh access token           |
| GET    | `/auth/me`                        | Bearer   | --              | Current user profile           |
| GET    | `/trains`                         | No       | --              | List all trains                |
| GET    | `/trains/{id}/schedules`          | No       | --              | Upcoming schedules for a train |
| GET    | `/trains/schedules/{id}/seats`    | No       | --              | Seat map with availability     |
| POST   | `/bookings`                       | Bearer   | 5/60s per user  | Reserve a seat                 |
| GET    | `/bookings`                       | Bearer   | --              | List user's bookings           |
| GET    | `/bookings/{id}`                  | Bearer   | --              | Single booking detail          |
| POST   | `/bookings/{id}/pay`              | Bearer   | 3/60s per user  | Pay for reservation            |
| POST   | `/bookings/{id}/refund`           | Bearer   | 3/60s per user  | Refund confirmed booking       |
| POST   | `/demo/race-condition`            | No       | --              | Trigger concurrent booking demo|
| GET    | `/demo/config`                    | No       | --              | Read gateway config            |
| PUT    | `/demo/config`                    | No       | --              | Update gateway config          |
| GET    | `/health`                         | No       | --              | Health check                   |
