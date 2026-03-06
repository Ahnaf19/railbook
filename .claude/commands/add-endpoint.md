Guide for adding a new API endpoint. Argument: $ARGUMENTS (describe the endpoint)

Steps:
1. Parse the endpoint description from: $ARGUMENTS
2. Determine which module it belongs to (auth, trains, bookings, admin, demo, or new module)
3. Create or update the schema in `{module}/schemas.py`
4. Implement the service function in `{module}/service.py` (take AsyncSession, raise HTTPException)
5. Add the route in `{module}/router.py` with appropriate dependencies (auth, rate limiting)
6. If new module: register router in `app/main.py`
7. If rate limited: add dependency override in `tests/conftest.py:client()` fixture
8. Write a test in `tests/test_{module}.py`
9. Run: `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run pytest -v --tb=short && uv run ruff check . --fix && uv run ruff format .`
10. Update docs: `docs/api/API_REFERENCE.md`, `README.md` API table, Postman collection
