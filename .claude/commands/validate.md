Run full project validation: lint, tests, and build checks.

Steps:
1. Backend lint: `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run ruff check . && uv run ruff format --check .`
2. Backend tests: `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run pytest -v --tb=short`
3. Frontend build: `cd /Users/ahnaftanjid/Documents/railbook/frontend && npm run build`
4. Report a summary table:
   - Lint: pass/fail (number of issues)
   - Tests: X/Y passed
   - Frontend build: pass/fail
5. If anything failed, diagnose and fix it, then re-run the failing check
