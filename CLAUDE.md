# RailBook

Railway ticket booking system showcasing concurrency handling.

## Tech Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL 16 + Redis 7
- **Frontend**: React 18 + Vite + React Router v6
- **Testing**: pytest + pytest-asyncio + httpx

## Quick Start
```bash
docker-compose up -d postgres redis     # Start DB + Redis
cd backend && uv sync                   # Install Python deps
cd backend && uv run alembic upgrade head  # Run migrations
cd backend && uv run uvicorn app.main:app --reload  # Start backend
cd frontend && npm install && npm run dev  # Start frontend
```

## Conventions
- SQLAlchemy 2.0 async style (`select()`, `session.execute()`)
- All booking state changes + audit trail in a single `session.begin()` transaction
- `SELECT FOR UPDATE` for seat locking
- Pydantic schemas for request/response validation
- Ruff for linting: `uv run ruff check . && uv run ruff format .`
- Tests: `uv run pytest -v`

## Key Patterns
- **Idempotency**: Every booking/payment has a unique idempotency_key
- **Atomic audit**: `log_audit()` is called inside the booking transaction
- **Redis graceful degradation**: All Redis calls wrapped in try/except
- **Rate limiting**: Sliding window via Redis sorted sets
