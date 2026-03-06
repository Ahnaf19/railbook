Diagnose and fix a failing test. Argument: $ARGUMENTS (test name or file, or empty for all)

Steps:
1. Run the specified test (or all tests if none specified):
   - Specific: `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run pytest $ARGUMENTS -v --tb=long -s`
   - All: `cd /Users/ahnaftanjid/Documents/railbook/backend && uv run pytest -v --tb=long -s`
2. For each failing test:
   a. Read the test file to understand what it expects
   b. Read the relevant source code (service, router, model) to understand actual behavior
   c. Determine if the bug is in the test or the source code
   d. Fix the bug
3. Re-run the failing test(s) to confirm the fix
4. Run the full test suite to confirm no regressions
5. Run lint: `uv run ruff check . --fix && uv run ruff format .`
