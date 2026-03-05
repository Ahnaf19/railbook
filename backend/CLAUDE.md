# Backend

## Structure
```
app/
  main.py          # FastAPI app + lifespan
  config.py        # Pydantic Settings
  database.py      # AsyncEngine + session
  models.py        # All SQLAlchemy models
  seed.py          # Seed data
  auth/            # JWT auth (register, login, refresh)
  trains/          # Train listing, schedules, seat availability
  bookings/        # Booking engine (core concurrency logic)
  payments/        # Mock payment gateway
  audit/           # Audit trail service
  ratelimit/       # Redis sliding window rate limiter
  demo/            # Race condition demo endpoints
  admin/           # Admin stats endpoints
```

## Running
```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest -v
uv run ruff check . --fix && uv run ruff format .
```

## Testing
- Test DB: `railbook_test` (auto-created by conftest.py)
- Each test runs in a rolled-back transaction
- Concurrency tests use real asyncio.gather against actual DB
