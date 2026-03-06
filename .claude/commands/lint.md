Run lint and format checks on the backend, fix any issues.

Steps:
1. `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run ruff check . --fix && uv run ruff format .`
2. If there were auto-fixed issues, report what changed
3. If there are unfixable issues, read the flagged files and fix them manually
4. Run the check again in strict mode: `uv run ruff check . && uv run ruff format --check .`
5. Report: clean or list remaining issues
