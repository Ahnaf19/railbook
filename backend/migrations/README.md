# Database Migrations

RailBook uses [Alembic](https://alembic.sqlalchemy.org/) to manage PostgreSQL schema migrations. Alembic is configured for **async** operation via `asyncpg`, matching the application's async SQLAlchemy engine.

## How It Works

- `env.py` reads `DATABASE_URL` from the app's `Settings` (Pydantic Settings)
- Migrations target the metadata from `app.models.Base`
- The async engine is created inline in `env.py` using `create_async_engine`
- Both online (live DB) and offline (SQL script) modes are supported

## Current Migrations

| Revision | Description |
|---|---|
| `596377e27b70` | Initial schema -- creates all 8 tables (users, trains, schedules, compartments, seats, bookings, payments, audit_trail) with indexes and constraints |

## Commands

All commands should be run from the `backend/` directory.

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Rollback to the beginning (empty database)
uv run alembic downgrade base

# Check current revision
uv run alembic current

# Show migration history
uv run alembic history --verbose

# Auto-generate a new migration after changing models.py
uv run alembic revision --autogenerate -m "describe your change"

# Create an empty migration (for manual SQL)
uv run alembic revision -m "describe your change"
```

## File Layout

```
migrations/
  env.py              # Async migration runner, reads settings from app.config
  script.py.mako      # Template for new migration files
  versions/
    596377e27b70_initial_schema.py   # Full schema: tables, indexes, unique constraints
```

## Notes

- The `versions/` directory is excluded from Ruff linting (see `pyproject.toml`)
- Migrations are **not** automatically applied on app startup; run `alembic upgrade head` manually or in your deployment pipeline
- The app's `seed.py` runs after migrations during lifespan startup and is idempotent
