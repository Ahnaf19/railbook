# Load Testing — Locust

## Files

- `locustfile.py` — 3 Locust personas (TicketBuyer weight=8, SeatSniper weight=1, MixedLoad weight=1)
- `verify_integrity.py` — Post-test DB integrity checker (4 SQL checks, exit 0/1)
- `helpers.py` — User registration, token management for Locust users
- `config.py` — TARGET_URL, DATABASE_URL, thresholds (MAX_P95_MS, MAX_ERROR_RATE)
- `requirements.txt` — locust, psycopg2-binary, requests

## Running

```bash
pip install -r requirements.txt

# Web UI mode
locust -f locustfile.py --host http://localhost:8000    # Open :8089

# Headless mode
locust -f locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 --run-time 60s

# Post-test verification
python verify_integrity.py
```

## Integrity Checks (verify_integrity.py)

1. No double bookings — `SELECT schedule_id, seat_id, COUNT(*)` where status in (reserved, confirmed) having count > 1
2. Audit trail completeness — every booking has at least one audit_trail entry
3. No stale reservations — expired reserved bookings should be cancelled (2-min grace window)
4. Payment consistency — every confirmed booking has a payment with status=success

## When Modifying

- New endpoint: add task method to appropriate persona in `locustfile.py`
- New DB constraint: add integrity check in `verify_integrity.py`
- Config: update `config.py` defaults and env var names
