# RailBook Load Testing Guide

This guide explains how to run load tests against the RailBook application using Locust, and how to verify database integrity after a test run.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Configuration](#configuration)
3. [Running Locust](#running-locust)
4. [Test Personas](#test-personas)
5. [Post-Test Integrity Verification](#post-test-integrity-verification)
6. [Interpreting Results](#interpreting-results)

---

## Prerequisites

### Python Dependencies

Install the required packages in the `loadtest/` directory:

```bash
pip install locust psycopg2-binary requests
```

- **locust** -- The load testing framework that simulates concurrent users
- **psycopg2-binary** -- PostgreSQL driver used by the integrity verification script
- **requests** -- HTTP client used by helper functions to register test users

### Running Application

The RailBook backend must be running and accessible before starting load tests. By default, the tests target `http://localhost:8000`. The database must be seeded with train, schedule, and seat data (this happens automatically on first startup).

### Database Access

The integrity verification script connects directly to PostgreSQL. Ensure the database is reachable from the machine running the tests.

---

## Configuration

All configuration lives in `/Users/ahnaftanjid/Documents/railbook/loadtest/config.py` and is controlled via environment variables:

### Environment Variables

| Variable       | Default                                             | Description                                   |
|----------------|-----------------------------------------------------|-----------------------------------------------|
| `TARGET_URL`   | `http://localhost:8000`                              | Base URL of the RailBook backend API          |
| `DATABASE_URL` | `postgresql://railbook:railbook@localhost:5432/railbook` | PostgreSQL connection string for integrity checks |

### Performance Thresholds

The config file also defines pass/fail thresholds used when evaluating results:

| Threshold        | Value  | Meaning                                             |
|------------------|--------|-----------------------------------------------------|
| `MAX_P95_MS`     | 2000   | 95th percentile response time must stay below 2000ms |
| `MAX_ERROR_RATE` | 0.05   | Error rate must stay below 5%                        |

Set environment variables before running tests:

```bash
export TARGET_URL=http://localhost:8000
export DATABASE_URL=postgresql://railbook:railbook@localhost:5432/railbook
```

---

## Running Locust

### From the Command Line (Headless Mode)

Navigate to the `loadtest/` directory and run Locust in headless mode for automated/CI scenarios:

```bash
cd /Users/ahnaftanjid/Documents/railbook/loadtest

# Example: 50 users, ramp up 10 users/second, run for 2 minutes
locust -f locustfile.py --headless -u 50 -r 10 -t 2m --host http://localhost:8000
```

Key flags:
- `-f locustfile.py` -- Path to the Locust test file
- `--headless` -- Run without the web UI (useful for CI pipelines)
- `-u 50` -- Total number of simulated users
- `-r 10` -- Users spawned per second during ramp-up
- `-t 2m` -- Total test duration (supports `s`, `m`, `h` suffixes)
- `--host` -- Target URL (overrides `TARGET_URL` from config)

### With the Web UI

For interactive testing with real-time charts:

```bash
cd /Users/ahnaftanjid/Documents/railbook/loadtest
locust -f locustfile.py --host http://localhost:8000
```

Then open your browser at:

```
http://localhost:8089
```

The Locust web interface lets you:

1. Set the **Number of users** (peak concurrency)
2. Set the **Ramp up** (users spawned per second)
3. Click **Start** to begin the test
4. Monitor real-time graphs for requests per second, response times, and failure rates
5. View per-endpoint statistics in a table
6. Stop the test at any time and download results as CSV

---

## Test Personas

The load test defines three user personas with different behaviors and weights. Locust distributes simulated users across these personas according to their weights.

### TicketBuyer (weight: 8)

**Simulates a typical user browsing and occasionally purchasing tickets.**

- **Wait time**: 1 to 3 seconds between tasks (realistic browsing pace)
- **Startup**: Registers a unique user account and obtains a JWT token

| Task           | Weight | Behavior                                                                         |
|----------------|--------|----------------------------------------------------------------------------------|
| `browse_trains`| 5      | Calls `GET /trains` to list all trains. Stores the result for subsequent tasks.  |
| `view_seats`   | 3      | Fetches schedules for the first train, then loads the seat map for the first schedule. |
| `book_and_pay` | 1      | Finds an available seat, creates a booking with a unique idempotency key, then immediately pays for it. Handles 409 (conflict) gracefully. |

The task weights mean that for every 9 actions, a TicketBuyer browses trains ~5 times, views seats ~3 times, and books ~1 time. This reflects realistic read-heavy traffic patterns.

With a persona weight of 8, approximately **80%** of all simulated users will be TicketBuyers.

### SeatSniper (weight: 1)

**Simulates an aggressive user attempting to grab seats as fast as possible.**

- **Wait time**: 0 seconds (constant, no delay between requests)
- **Startup**: Registers a user, fetches trains and schedules, and locks onto the first available schedule as a target

| Task         | Weight | Behavior                                                                         |
|--------------|--------|----------------------------------------------------------------------------------|
| `snipe_seat` | 1      | Repeatedly finds an available seat on the target schedule and immediately attempts to book it. Fires as fast as the server can respond. |

This persona stress-tests the booking concurrency controls. Multiple SeatSnipers competing for seats on the same schedule will trigger frequent `SELECT FOR UPDATE` lock contention, validating that the system prevents double bookings under extreme load.

With a persona weight of 1, approximately **10%** of simulated users will be SeatSnipers.

### MixedLoad (weight: 1)

**Simulates background traffic hitting various endpoints.**

- **Wait time**: 0.5 to 1 second between tasks

| Task           | Weight | Behavior                           |
|----------------|--------|------------------------------------|
| `browse`       | 3      | Calls `GET /trains`                |
| `health`       | 2      | Calls `GET /health`                |
| `my_bookings`  | 1      | Calls `GET /bookings` (user's list)|
| `demo_config`  | 1      | Calls `GET /demo/config`           |

This persona generates diverse read traffic to test overall system responsiveness while the other personas are booking and sniping.

With a persona weight of 1, approximately **10%** of simulated users will be MixedLoad.

### How User Registration Works During Load Tests

Each simulated user registers a unique account on startup using a randomly generated email (`loadtest-<random8hex>@test.com`) with the password `loadtest123`. If registration returns a conflict (user already exists), the helper falls back to logging in with the same credentials. This ensures load tests are self-contained and do not depend on pre-existing accounts.

---

## Post-Test Integrity Verification

After a load test completes, run the integrity verification script to confirm the database is in a consistent state:

```bash
cd /Users/ahnaftanjid/Documents/railbook/loadtest
python verify_integrity.py
```

The script connects directly to PostgreSQL using the `DATABASE_URL` environment variable (or its default) and runs four checks.

### Exit Codes

| Exit Code | Meaning             |
|-----------|----------------------|
| 0         | All checks passed    |
| 1         | One or more checks failed |

### The 4 Integrity Checks

#### 1. No Double Bookings

```
PASS: No double bookings
```

Queries the `bookings` table for any schedule+seat combination that has more than one active booking (status `reserved` or `confirmed`). If any duplicates exist, the check fails and lists each offending schedule/seat pair with the count. This is the most critical check -- it validates the core concurrency guarantee of the system.

#### 2. Audit Trail Completeness

```
PASS: All bookings have audit trail
```

Performs a `LEFT JOIN` between `bookings` and `audit_trail` to find any booking without at least one corresponding audit entry. Every booking should have an audit record from the moment it is created (the "reserved" event). A failure here indicates that a booking was created without its audit log, which could mean a transaction boundary issue.

#### 3. No Stale Reservations

```
PASS: No stale reservations
```

Checks for bookings that are still in `reserved` status but whose `expires_at` timestamp is more than 2 minutes in the past. The background cleanup task runs every 60 seconds to cancel expired reservations, so a 2-minute grace period accounts for one missed cycle. Stale reservations indicate the cleanup process is not running or is falling behind under load.

#### 4. Payment Consistency

```
PASS: Payment consistency verified
```

Joins `bookings` with `payments` to find any booking in `confirmed` status that does not have a corresponding payment record with status `success`. A confirmed booking without a successful payment represents a critical inconsistency -- the user's booking was marked as paid without actual payment processing.

### Example Output

A successful verification run looks like this:

```
Connecting to postgresql://railbook:railbook@localhost:5432/railbook...
PASS: No double bookings
PASS: All bookings have audit trail
PASS: No stale reservations
PASS: Payment consistency verified

All integrity checks PASSED
```

A failed run reports which checks failed:

```
Connecting to postgresql://railbook:railbook@localhost:5432/railbook...
FAIL: 2 double bookings found!
  schedule=abc123 seat=def456 count=2
  schedule=abc123 seat=ghi789 count=2
PASS: All bookings have audit trail
PASS: No stale reservations
PASS: Payment consistency verified

1/4 checks FAILED
```

---

## Interpreting Results

### Key Metrics to Watch

| Metric                     | Where to Find It          | What It Tells You                                  |
|----------------------------|---------------------------|----------------------------------------------------|
| Requests per second (RPS)  | Locust stats table / chart| Overall throughput of the system                   |
| Median response time       | Locust stats table        | Typical user experience                             |
| 95th percentile (P95)      | Locust stats table        | Tail latency -- how slow is it for the worst 5%?   |
| Error rate                 | Locust stats table        | Percentage of requests returning non-2xx status     |
| `/bookings` POST failures  | Per-endpoint stats        | Expected 409s from contention are normal; 500s are not |

### Passing Thresholds

Based on the configured thresholds in `config.py`:

- **P95 response time** should stay below **2000ms** (`MAX_P95_MS`). If the 95th percentile exceeds this, the system is too slow under the given load.
- **Error rate** should stay below **5%** (`MAX_ERROR_RATE`). Note that 409 Conflict responses from concurrent booking attempts are expected behavior, not errors. Focus on 500-level errors which indicate server-side bugs.

### Expected Behavior Under Load

- **409 Conflict on `/bookings` POST**: This is normal and expected. It means two users tried to book the same seat, and the loser received a proper rejection. The system is working correctly.
- **400 Bad Request on `/bookings/{id}/pay`**: Can occur if a reservation expired between booking and payment. Also normal.
- **Increasing P95 as users scale**: Some increase is expected. The key question is whether it stays below the 2000ms threshold.
- **SeatSniper high failure rate**: Since snipers fire with zero delay and compete for the same seats, a high 409 rate among snipers is expected and healthy.

### Recommended Test Scenarios

| Scenario         | Users | Ramp Rate | Duration | Purpose                                    |
|------------------|-------|-----------|----------|--------------------------------------------|
| Smoke test       | 10    | 5/s       | 1m       | Verify the test setup works                |
| Baseline         | 50    | 10/s      | 5m       | Establish normal performance metrics       |
| Stress test      | 200   | 20/s      | 10m      | Find the breaking point                    |
| Soak test        | 50    | 10/s      | 30m      | Check for memory leaks or degradation      |

### Full Test Workflow

1. Ensure the RailBook backend is running and the database is seeded
2. Run the load test:
   ```bash
   cd /Users/ahnaftanjid/Documents/railbook/loadtest
   locust -f locustfile.py --headless -u 50 -r 10 -t 5m --host http://localhost:8000
   ```
3. Review the Locust output for RPS, response times, and error rates
4. Run the integrity check:
   ```bash
   python verify_integrity.py
   ```
5. Confirm all 4 checks pass
6. If any check fails, investigate the specific failure before increasing load
