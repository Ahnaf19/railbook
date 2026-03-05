# Load Testing

Load test suite for RailBook using [Locust](https://locust.io/). Simulates realistic traffic patterns including normal browsing, aggressive seat sniping, and mixed API calls. Includes a post-test integrity verification script.

## Setup

```bash
pip install -r requirements.txt
# Requirements: locust>=2.20, psycopg2-binary>=2.9
```

## Running Locust

```bash
# Web UI mode (default: http://localhost:8089)
locust -f locustfile.py

# Headless mode (100 users, ramp up 10/sec, run 5 min)
locust -f locustfile.py --headless -u 100 -r 10 -t 5m --host http://localhost:8000
```

By default, Locust targets `http://localhost:8000`. Override with `TARGET_URL` env var or the `--host` flag.

## User Personas

| Persona | Weight | Wait Time | Behavior |
|---|---|---|---|
| **TicketBuyer** | 8 | 1-3s | Browse trains (5x), view seats (3x), book+pay (1x). Represents normal users. |
| **SeatSniper** | 1 | 0s (constant) | Rapidly grabs available seats on a single schedule. Stress-tests booking concurrency. |
| **MixedLoad** | 1 | 0.5-1s | Hits /trains (3x), /health (2x), /bookings (1x), /demo/config (1x). Background noise. |

Each user registers a fresh account on startup. The 8:1:1 weight ratio means ~80% of spawned users are normal TicketBuyers.

## Configuration

`config.py` defines:

| Variable | Env Var | Default |
|---|---|---|
| `BASE_URL` | `TARGET_URL` | `http://localhost:8000` |
| `DB_URL` | `DATABASE_URL` | `postgresql://railbook:railbook@localhost:5432/railbook` |
| `MAX_P95_MS` | -- | `2000` (pass/fail threshold) |
| `MAX_ERROR_RATE` | -- | `0.05` (5%) |

## Post-Test Integrity Verification

After a load test run, verify that no database invariants were violated:

```bash
python verify_integrity.py
```

This script connects directly to PostgreSQL and runs 4 checks:

1. **No double bookings** -- no two active bookings (reserved/confirmed) for the same schedule+seat
2. **Audit trail completeness** -- every booking has at least one audit entry
3. **No stale reservations** -- no expired reservations still in "reserved" status (>2 min grace)
4. **Payment consistency** -- every confirmed booking has a successful payment record

Exit code 0 means all checks passed; exit code 1 means failures were found.

## Interpreting Results

Key metrics to watch in the Locust dashboard:

- **p95 response time** -- should stay under 2000ms for booking endpoints
- **Error rate** -- `409 Conflict` on bookings is expected (seat contention); true errors (5xx) should be near 0%
- **RPS** -- requests per second across all endpoints
- **Booking success ratio** -- `POST /bookings` returning 201 vs 409 shows how contention scales with user count

## File Layout

```
loadtest/
  locustfile.py          # 3 Locust user classes (TicketBuyer, SeatSniper, MixedLoad)
  helpers.py             # Shared functions: register_user, get_auth_headers, get_available_seat
  config.py              # BASE_URL, DB_URL, thresholds
  requirements.txt       # locust, psycopg2-binary
  verify_integrity.py    # Post-test DB invariant checker (4 SQL queries)
```
