# Contributing to RailBook

Thank you for your interest in contributing to RailBook. This document covers the development workflow, coding standards, and pull request process.

---

## Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/<your-username>/railbook.git
   cd railbook
   ```

2. **Start infrastructure**

   ```bash
   docker-compose up -d postgres redis
   ```

3. **Backend**

   ```bash
   cd backend
   uv sync                          # Install all dependencies (including dev)
   uv run alembic upgrade head      # Apply migrations
   uv run uvicorn app.main:app --reload
   ```

4. **Frontend**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

See the [Developer Guide](docs/guides/DEVELOPER_GUIDE.md) for a complete walkthrough.

---

## Code Style

### Backend (Python)

- **Formatter/linter:** [Ruff](https://docs.astral.sh/ruff/) — configured in `pyproject.toml`
- **Line length:** 100 characters
- **Target:** Python 3.11+

Run before committing:

```bash
cd backend
uv run ruff check . --fix
uv run ruff format .
```

### Frontend (JavaScript/JSX)

- Standard Vite/React conventions
- No TypeScript (plain JSX)

---

## Testing

All backend tests are async and run against a real PostgreSQL database (`railbook_test`).

```bash
cd backend
uv run pytest -v          # Run all 34 tests
uv run pytest -v -s       # With stdout output
```

**Every pull request must pass the full test suite.** If you add a new feature, add corresponding tests.

### Test categories

| File | What it covers |
|------|----------------|
| `test_auth.py` | Registration, login, JWT, duplicates |
| `test_bookings.py` | Reserve, pay, confirm flow |
| `test_concurrency.py` | Double booking prevention, idempotency |
| `test_journey_overlap.py` | Overlapping journey detection |
| `test_payments.py` | Payment success, failure, idempotency |
| `test_refund.py` | Refund flow and validation |
| `test_rate_limit.py` | Rate limiting behavior |
| `test_trains.py` | Train listing, schedules, seat availability |

---

## Pull Request Process

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes.** Follow the code style above.

3. **Run the checks:**
   ```bash
   cd backend
   uv run ruff check . --fix && uv run ruff format .
   uv run pytest -v
   ```

4. **Commit** with a clear message following [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: add seat class upgrade option
   fix: prevent expired reservation from accepting payment
   docs: update API reference for refund endpoint
   test: add concurrent refund test
   ```

5. **Open a pull request** against `main`. Include:
   - A description of what changed and why
   - How to test the change
   - Any related issue numbers

---

## Reporting Issues

- Use [GitHub Issues](../../issues) to report bugs or request features.
- For bugs, include: steps to reproduce, expected vs actual behavior, and your environment (OS, Python version, Docker version).
- For features, describe the use case and proposed solution.

---

## Project Structure

Refer to the [Developer Guide](docs/guides/DEVELOPER_GUIDE.md) for a complete breakdown of the codebase structure, async patterns, and architectural decisions.
