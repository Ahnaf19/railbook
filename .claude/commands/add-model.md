Guide for adding a new database model. Argument: $ARGUMENTS (describe the model)

Steps:
1. Parse the model description from: $ARGUMENTS
2. Add the SQLAlchemy model class to `backend/app/models.py` following existing patterns:
   - UUID primary key with `default=uuid.uuid4`
   - `mapped_column` with proper types
   - Relationships if needed
   - Relevant indexes and constraints
3. Generate migration: `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run alembic revision --autogenerate -m "add {table_name} table"`
4. Review the generated migration file in `migrations/versions/` — verify it looks correct
5. Apply: `uv run alembic upgrade head`
6. If seed data needed: update `app/seed.py`
7. Run tests: `uv run pytest -v --tb=short`
8. Update `docs/architecture/DATABASE.md` with the new table documentation
