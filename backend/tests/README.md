# Tests

Async test suite for the RailBook backend using **pytest** + **pytest-asyncio** in `auto` mode. All tests run against a real PostgreSQL database (`railbook_test`).

## Running Tests

```bash
# Run all tests with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_concurrency.py -v

# Run a single test
uv run pytest tests/test_auth.py::test_register_returns_jwt -v
```

## Test Database Setup

The `conftest.py` fixture system works as follows:

1. **`test_engine`** (session-scoped) -- creates an async engine pointing at `railbook_test` (derived from `DATABASE_URL` by replacing the DB name). Drops and recreates all tables, then seeds demo data. Disposes the engine at session teardown.
2. **`session_factory`** (session-scoped) -- wraps the engine in an `async_sessionmaker`.
3. **`db_session`** (function-scoped) -- provides a fresh `AsyncSession` per test.
4. **`client`** (function-scoped) -- an `httpx.AsyncClient` with ASGI transport. Overrides the `get_db` dependency and **disables all rate limiting** so tests are not throttled.
5. **`auth_headers`** (function-scoped) -- registers a unique user and returns `{"Authorization": "Bearer <token>"}`.

## Test Categories

| File | Tests | What it covers |
|---|---|---|
| `test_auth.py` | 7 | Register, login, duplicate email (409), bad credentials (401), expired token, refresh rotation, `/auth/me` |
| `test_bookings.py` | 2 | Happy path (reserve -> pay -> confirm), list user bookings |
| `test_concurrency.py` | 3 | Double-booking prevention, concurrent different-seat success, idempotency key dedup |
| `test_payments.py` | 3 | Successful payment, failed payment, payment idempotency |
| `test_rate_limit.py` | 7 | Threshold blocking, 429 headers, per-user isolation, IP-based auth limits, Redis-down graceful degradation, payment stricter limits, auth rate limit |
| `test_audit.py` | 5 | Reserve creates audit entry, payment success/failure audit, refund audit, chronological ordering |
| `test_trains.py` | 4 | List trains, future-only schedules, seat availability, booked status after booking |
| `test_refund.py` | 2 | Successful refund of confirmed booking, refund of non-confirmed fails |
| `test_journey_overlap.py` | 1 | Overlapping journey on same schedule blocked |

**Total: 34 tests**

## How Concurrency Tests Work

The concurrency tests in `test_concurrency.py` do not mock anything. They use real `asyncio.gather` to fire simultaneous HTTP requests through separate `AsyncClient` instances, each with its own DB session. This exercises the actual PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) and unique constraints that prevent double bookings.

For example, `test_double_booking_prevented` registers two independent users, then fires two booking requests for the **same seat** in parallel. Exactly one gets `201 Created` and the other gets `409 Conflict`.

## Configuration

Pytest is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
testpaths = ["tests"]
```

All test functions are `async def` and run on a shared event loop for the entire session.
