# Backend — FastAPI + SQLAlchemy 2.0 async

## Module Map

| Module | Router prefix | Rate limited | Auth required | Key file |
|--------|--------------|-------------|---------------|----------|
| auth | `/auth` | `rate_limit_auth` (10/5min per IP) | No (except `/me`) | `auth/service.py` — JWT create/verify, bcrypt |
| trains | `/trains` | No | No | `trains/service.py` — queries + Redis seat cache |
| bookings | `/bookings` | `rate_limit_booking` (5/min), `rate_limit_payment` (3/min) | Yes | `bookings/service.py` — **core concurrency logic** |
| payments | (internal) | — | — | `payments/gateway.py` — MockPaymentGateway singleton |
| audit | (internal) | — | — | `audit/service.py` — `log_audit()` (call inside txn) |
| ratelimit | (internal) | — | — | `ratelimit/limiter.py` + `dependencies.py` |
| demo | `/demo` | No | No | `demo/service.py` — `run_race()` via asyncio.gather |
| admin | `/admin` | No | Admin only (`require_admin`) | `admin/service.py` — stats/occupancy queries |

## File Roles

- `main.py` — App creation, lifespan (DB check → seed → start cleanup task), CORS, router mounts
- `config.py` — `Settings(BaseSettings)` — all env vars with defaults, loaded from `.env`
- `database.py` — `engine` (pool_size=10, max_overflow=20), `async_session` factory, `get_db` dependency
- `models.py` — All 8 ORM models in one file. Changing models → create Alembic migration
- `seed.py` — `seed_database(session)` — idempotent, checks if trains table empty before seeding
- `redis.py` — `get_redis()` returns connection, `close_redis_pool()` for shutdown

## How to Add a New Endpoint

1. Pick or create a module under `app/`
2. Add schema in `{module}/schemas.py` (Pydantic model, `model_config = {"from_attributes": True}`)
3. Add logic in `{module}/service.py` (takes `AsyncSession`, raises `HTTPException`)
4. Add route in `{module}/router.py` (inject `Depends(get_db)`, `Depends(get_current_user)` as needed)
5. If new module: register router in `main.py` via `app.include_router()`
6. If rate limited: add `dependencies=[Depends(rate_limit_*)]` to route AND add override in `tests/conftest.py:client()`
7. Add test in `tests/test_{module}.py`
8. Run: `uv run pytest -v && uv run ruff check . --fix && uv run ruff format .`

## How to Add a New Model

1. Add class in `models.py` (follow existing pattern: UUID PK, mapped_column, relationships)
2. Run: `uv run alembic revision --autogenerate -m "add {table_name} table"`
3. Review generated migration in `migrations/versions/`
4. Apply: `uv run alembic upgrade head`
5. If seed data needed: update `seed.py`

## Booking Service — The Core (bookings/service.py)

The most critical file. Functions and their transaction patterns:

### `create_booking(session, user_id, schedule_id, seat_id, idempotency_key, ip_address)`
1. Idempotency check → return existing if found
2. `SELECT ... WHERE (schedule_id, seat_id) FOR UPDATE` → 409 if active booking exists
3. Journey overlap check (same user, overlapping times) → 409 if overlap
4. Calculate price (AC=1500, Non-AC=800 from compartment type)
5. Delete old cancelled/refunded booking if exists (for UNIQUE constraint)
6. Insert booking (status=reserved, expires_at=now+5min)
7. `log_audit()` — same session
8. `session.commit()` — atomic
9. Invalidate Redis seat cache

### `pay_booking(session, booking_id, user_id, idempotency_key, ip_address)`
1. `SELECT booking FOR UPDATE` → validate ownership, status=reserved, not expired
2. Payment idempotency check → return existing if found
3. `log_audit("payment_attempted")` + flush
4. Call `payment_gateway.charge(amount, key)`
5. On success: status=confirmed, create Payment(success), `log_audit("confirmed")`
6. On failure: status=cancelled, create Payment(failed), `log_audit("payment_failed")`
7. `session.commit()` — booking + payment + audit atomic
8. Invalidate Redis seat cache

### `refund_booking(session, booking_id, user_id, ip_address)`
1. `SELECT booking FOR UPDATE` → validate confirmed, departure >1hr away
2. Call `payment_gateway.refund(gateway_ref)`
3. status=refunded, `log_audit("refunded")`
4. `session.commit()`
5. Invalidate Redis seat cache

## Testing Patterns

```python
# Standard test with auth
async def test_something(client, auth_headers):
    resp = await client.get("/bookings", headers=auth_headers)
    assert resp.status_code == 200

# Get a bookable seat (common setup pattern)
trains = (await client.get("/trains")).json()
schedules = (await client.get(f"/trains/{trains[0]['id']}/schedules")).json()
seats_resp = (await client.get(f"/trains/schedules/{schedules[0]['id']}/seats")).json()
available = [s for s in seats_resp["seats"] if not s["booking_status"]]

# Concurrency test pattern
results = await asyncio.gather(
    client1.post("/bookings", json=data1, headers=headers1),
    client2.post("/bookings", json=data2, headers=headers2),
)

# Admin test pattern
login = await client.post("/auth/login", json={"email": "admin@railbook.com", "password": "admin123"})
admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
```

## Common Debugging

- **Tests hang**: PostgreSQL `railbook_test` DB doesn't exist → `docker exec -it <container> psql -U railbook -c "CREATE DATABASE railbook_test;"`
- **Import errors after model changes**: Need `uv run alembic upgrade head` after migration
- **Rate limit 429 in tests**: Missing override in conftest.py `client()` fixture
- **Redis connection errors**: Redis not running → `docker-compose up -d redis`
- **Seat cache stale**: Delete key `seats:{schedule_id}` from Redis, or restart Redis
