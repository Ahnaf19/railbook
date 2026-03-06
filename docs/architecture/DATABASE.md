# Database Schema Documentation

RailBook uses PostgreSQL with 8 tables. All tables use UUIDs as primary keys except `audit_trail`, which uses a sequential `BigInteger`. The schema is defined in SQLAlchemy 2.0 declarative models at `backend/app/models.py` and managed through Alembic migrations.

---

## Entity-Relationship Diagram

```
  users
    |
    +---< bookings >---+--- schedules --- trains
    |        |         |                    |
    |        |         +--- seats -------- compartments
    |        |
    |        +---< payments
    |        |
    +---< audit_trail
```

`---<` denotes a one-to-many relationship. `---` denotes a many-to-one foreign key.

---

## Table Definitions

### 1. `users`

Stores registered accounts including a system user for automated tasks.

| Column          | Type                   | Constraints                 | Description                        |
|-----------------|------------------------|-----------------------------|------------------------------------|
| `id`            | `UUID`                 | PK, default `uuid4()`      | User identifier                    |
| `email`         | `VARCHAR(255)`         | UNIQUE, NOT NULL            | Login email                        |
| `password_hash` | `VARCHAR(255)`         | NOT NULL                    | bcrypt hash                        |
| `full_name`     | `VARCHAR(255)`         | NOT NULL                    | Display name                       |
| `phone`         | `VARCHAR(20)`          | nullable                    | Contact number                     |
| `role`          | `VARCHAR(20)`          | default `'user'`            | `'user'` or `'admin'`             |
| `created_at`    | `TIMESTAMPTZ`          | server_default `now()`      | Registration timestamp             |

**Indexes:**
- PK index on `id`
- Unique index on `email` (enforced by the UNIQUE constraint)

**Notes:** The system user (`id = 00000000-0000-0000-0000-000000000000`) is created during seeding with `password_hash='nologin'` and `role='admin'`. It is used as the `user_id` for automated actions like reservation cleanup.

---

### 2. `trains`

Static reference data for train routes.

| Column         | Type            | Constraints              | Description                    |
|----------------|-----------------|--------------------------|--------------------------------|
| `id`           | `UUID`          | PK, default `uuid4()`   | Train identifier               |
| `name`         | `VARCHAR(255)`  | NOT NULL                 | Human name (e.g., "Subarna Express") |
| `train_number` | `VARCHAR(50)`   | UNIQUE, NOT NULL         | Code (e.g., "SE-701")         |
| `origin`       | `VARCHAR(255)`  | NOT NULL                 | Departure city                 |
| `destination`  | `VARCHAR(255)`  | NOT NULL                 | Arrival city                   |

**Indexes:**
- PK index on `id`
- Unique index on `train_number`

**Relationships:**
- `trains.id` --> `schedules.train_id` (one train has many schedules)
- `trains.id` --> `compartments.train_id` (one train has many compartments)

---

### 3. `schedules`

A specific departure of a train on a specific date and time.

| Column           | Type            | Constraints                                  | Description                |
|------------------|-----------------|----------------------------------------------|----------------------------|
| `id`             | `UUID`          | PK, default `uuid4()`                       | Schedule identifier        |
| `train_id`       | `UUID`          | FK -> `trains.id`, NOT NULL                  | Which train                |
| `departure_time` | `TIMESTAMPTZ`   | NOT NULL                                     | Scheduled departure        |
| `arrival_time`   | `TIMESTAMPTZ`   | NOT NULL                                     | Scheduled arrival          |
| `status`         | `VARCHAR(20)`   | default `'scheduled'`                        | `'scheduled'`, `'cancelled'`, etc. |

**Constraints:**
- `UNIQUE(train_id, departure_time)` -- a train cannot depart twice at the same time. This prevents accidental duplicate schedule creation.

**Indexes:**
- PK index on `id`
- Unique composite index on `(train_id, departure_time)`

**Notes:** The seed data creates 7 days of schedules for each of 3 trains (21 schedules total). Schedules are filtered by `departure_time > now()` when querying upcoming departures.

---

### 4. `compartments`

Physical sections of a train. Each compartment has a type (AC or non-AC) that determines ticket pricing.

| Column      | Type           | Constraints                     | Description                    |
|-------------|----------------|---------------------------------|--------------------------------|
| `id`        | `UUID`         | PK, default `uuid4()`          | Compartment identifier         |
| `train_id`  | `UUID`         | FK -> `trains.id`, NOT NULL     | Parent train                   |
| `name`      | `VARCHAR(10)`  | NOT NULL                        | Label (e.g., "A", "B", "C")  |
| `comp_type` | `VARCHAR(20)`  | NOT NULL                        | `'ac'` or `'non_ac'`          |
| `capacity`  | `INTEGER`      | default `25`                    | Number of seats                |

**Indexes:**
- PK index on `id`

**Notes:** Pricing is derived from `comp_type`: AC compartments are 1500.00 BDT, non-AC are 800.00 BDT. The seed data creates 2 compartments per train (A = AC; B = non-AC), each with 25 seats.

---

### 5. `seats`

Individual seats within a compartment.

| Column           | Type           | Constraints                              | Description                    |
|------------------|----------------|------------------------------------------|--------------------------------|
| `id`             | `UUID`         | PK, default `uuid4()`                   | Seat identifier                |
| `compartment_id` | `UUID`         | FK -> `compartments.id`, NOT NULL        | Parent compartment             |
| `seat_number`    | `INTEGER`      | NOT NULL                                 | Number within compartment (1-25) |
| `position`       | `VARCHAR(20)`  | NOT NULL                                 | `'window'` or `'corridor'`    |

**Constraints:**
- `UNIQUE(compartment_id, seat_number)` -- no duplicate seat numbers within a compartment.

**Indexes:**
- PK index on `id`
- Unique composite index on `(compartment_id, seat_number)`

**Notes:** Seat position is determined by the last digit of the seat number: digits 1, 4, 5, 8 are window seats; all others are corridor. The seed creates 150 seats total (3 trains x 2 compartments x 25 seats).

---

### 6. `bookings`

The central table. Represents a user's reservation or confirmed ticket for a specific seat on a specific schedule.

| Column           | Type            | Constraints                                     | Description                      |
|------------------|-----------------|-------------------------------------------------|----------------------------------|
| `id`             | `UUID`          | PK, default `uuid4()`                          | Booking identifier               |
| `user_id`        | `UUID`          | FK -> `users.id`, NOT NULL                      | Who made the booking             |
| `schedule_id`    | `UUID`          | FK -> `schedules.id`, NOT NULL                  | Which schedule                   |
| `seat_id`        | `UUID`          | FK -> `seats.id`, NOT NULL                      | Which seat                       |
| `status`         | `VARCHAR(20)`   | default `'reserved'`                            | See state machine below          |
| `idempotency_key`| `UUID`          | UNIQUE, NOT NULL                                | Client-provided dedup key        |
| `reserved_at`    | `TIMESTAMPTZ`   | server_default `now()`                          | When reservation was created     |
| `expires_at`     | `TIMESTAMPTZ`   | nullable                                        | When reservation expires (5 min) |
| `confirmed_at`   | `TIMESTAMPTZ`   | nullable                                        | When payment confirmed           |
| `cancelled_at`   | `TIMESTAMPTZ`   | nullable                                        | When cancelled/refunded/expired  |
| `total_amount`   | `NUMERIC(10,2)` | NOT NULL                                        | Ticket price                     |

**Constraints:**
- `uq_booking_schedule_seat`: `UNIQUE(schedule_id, seat_id)` -- **the most critical constraint in the system**. Guarantees at the database level that no two active bookings can exist for the same seat on the same schedule. This is the last line of defense behind the `SELECT FOR UPDATE` application logic.
- `UNIQUE(idempotency_key)` -- prevents duplicate bookings from retried requests.

**Indexes:**

| Index Name                   | Columns                  | Type     | Purpose                                                 |
|------------------------------|--------------------------|----------|----------------------------------------------------------|
| PK index                     | `id`                     | Unique   | Primary key lookups                                      |
| `uq_booking_schedule_seat`   | `schedule_id, seat_id`   | Unique   | Double-booking prevention at constraint level            |
| `ix_bookings_schedule_seat`  | `schedule_id, seat_id`   | B-tree   | Fast lookup for seat availability queries and `FOR UPDATE` locking |
| `ix_bookings_user_id`        | `user_id`                | B-tree   | List a user's bookings, journey overlap check            |
| `ix_bookings_status`         | `status`                 | B-tree   | Cleanup task filters on `status='reserved'`              |
| `idempotency_key` unique     | `idempotency_key`        | Unique   | Idempotency check on booking creation                    |

**Why both a UNIQUE constraint and a regular index on `(schedule_id, seat_id)`?** The UNIQUE constraint (`uq_booking_schedule_seat`) creates an implicit unique index, so the explicit index `ix_bookings_schedule_seat` is technically redundant. However, it makes the intent clear in the codebase: the UNIQUE constraint exists for correctness (preventing duplicates), while the named index documents the access pattern (the `SELECT FOR UPDATE` query in `create_booking` uses this pair as its filter). In practice, PostgreSQL uses the unique index for both purposes.

**Booking status values:**
- `reserved` -- seat held, awaiting payment (5-minute TTL)
- `confirmed` -- payment successful
- `cancelled` -- payment failed, expired, or user cancelled
- `refunded` -- confirmed booking refunded by user

---

### 7. `payments`

Financial records for each payment attempt against a booking.

| Column           | Type            | Constraints                     | Description                          |
|------------------|-----------------|---------------------------------|--------------------------------------|
| `id`             | `UUID`          | PK, default `uuid4()`          | Payment identifier                   |
| `booking_id`     | `UUID`          | FK -> `bookings.id`, NOT NULL   | Associated booking                   |
| `idempotency_key`| `UUID`          | UNIQUE, NOT NULL                | Client-provided dedup key for payment|
| `amount`         | `NUMERIC(10,2)` | NOT NULL                        | Charged amount                       |
| `status`         | `VARCHAR(20)`   | default `'pending'`             | `'pending'`, `'success'`, `'failed'` |
| `gateway_ref`    | `VARCHAR(100)`  | nullable                        | External reference from gateway      |
| `attempted_at`   | `TIMESTAMPTZ`   | server_default `now()`          | When charge was initiated            |
| `completed_at`   | `TIMESTAMPTZ`   | nullable                        | When charge completed (success/fail) |
| `failure_reason` | `VARCHAR(500)`  | nullable                        | Human-readable failure description   |

**Indexes:**
- PK index on `id`
- Unique index on `idempotency_key`

**Notes:** A booking can have multiple payment records (e.g., a failed attempt followed by a successful retry with a new idempotency key). The `gateway_ref` stores the mock gateway's reference ID (format: `MOCK-{hex}`), which is used for refund lookups.

---

### 8. `audit_trail`

Append-only log of every booking state change. Never updated or deleted.

| Column            | Type           | Constraints                     | Description                          |
|-------------------|----------------|---------------------------------|--------------------------------------|
| `id`              | `BIGINT`       | PK, auto-increment              | Sequential audit entry ID            |
| `booking_id`      | `UUID`         | FK -> `bookings.id`, NOT NULL   | Which booking changed                |
| `user_id`         | `UUID`         | FK -> `users.id`, NOT NULL      | Who triggered the change             |
| `action`          | `VARCHAR(50)`  | NOT NULL                        | Action name (see below)              |
| `previous_status` | `VARCHAR(20)`  | nullable                        | Status before the change             |
| `new_status`      | `VARCHAR(20)`  | NOT NULL                        | Status after the change              |
| `metadata`        | `JSON`         | nullable                        | Arbitrary context data               |
| `ip_address`      | `VARCHAR(45)`  | nullable                        | Client IP (supports IPv6)            |
| `created_at`      | `TIMESTAMPTZ`  | server_default `now()`          | When the entry was recorded          |

**Indexes:**

| Index Name                     | Columns                    | Purpose                                              |
|--------------------------------|----------------------------|------------------------------------------------------|
| PK index                       | `id`                       | Primary key                                          |
| `ix_audit_booking_created`     | `booking_id, created_at`   | Fetch full audit history for a booking in chronological order |

**Why `BIGINT` instead of `UUID`?** Audit entries are append-only and always queried in chronological order (by `booking_id` + `created_at`). A sequential integer primary key keeps the B-tree index physically ordered, giving O(1) appends and sequential scan performance for range queries. Random UUIDs would scatter inserts across the index, causing page splits and write amplification.

**Action values used in the codebase:**
- `reserved` -- initial booking creation
- `payment_attempted` -- payment charge initiated
- `confirmed` -- payment succeeded
- `payment_failed` -- gateway returned failure
- `expired_cleanup` -- background task cancelled expired reservation
- `refunded` -- user-initiated refund

**Metadata examples:**
- On reservation: `{"schedule_id": "...", "seat_id": "..."}`
- On confirmation: `{"gateway_ref": "MOCK-a1b2c3d4"}`
- On failure: `{"failure_reason": "Card declined (simulated)"}`
- On cleanup: `{"expired_at": "2026-03-06T12:05:00+00:00", "ttl_seconds": 300}`

---

## Foreign Key Relationships

```
users.id
  |---> bookings.user_id
  |---> audit_trail.user_id

trains.id
  |---> schedules.train_id
  |---> compartments.train_id

schedules.id
  |---> bookings.schedule_id

compartments.id
  |---> seats.compartment_id

seats.id
  |---> bookings.seat_id

bookings.id
  |---> payments.booking_id
  |---> audit_trail.booking_id
```

All foreign keys use PostgreSQL's default `RESTRICT` behavior for `ON DELETE`. Deleting a user with existing bookings, or a schedule with existing bookings, will raise a foreign key violation. This is intentional -- the system should never orphan booking or audit data.

---

## Index Design Rationale

### Booking lookup patterns and their indexes

| Query Pattern                                            | Index Used                      | Called From                     |
|----------------------------------------------------------|---------------------------------|---------------------------------|
| Find booking by `(schedule_id, seat_id)` with lock       | `ix_bookings_schedule_seat`     | `create_booking` (FOR UPDATE)  |
| Find all bookings for a user                             | `ix_bookings_user_id`           | `list_user_bookings`, overlap check |
| Find all reserved bookings that have expired             | `ix_bookings_status`            | `cleanup_expired_reservations` |
| Find booking by `idempotency_key`                        | Unique index on idempotency_key | `create_booking` (idempotency) |
| Find audit trail for a booking in order                  | `ix_audit_booking_created`      | Admin/debugging queries        |

### Why `ix_bookings_status` is a standalone index

The cleanup task runs `WHERE status = 'reserved' AND expires_at < now()`. A composite index on `(status, expires_at)` would be more selective, but the standalone `status` index is sufficient because:

1. The `reserved` status is a small fraction of total bookings (most are confirmed or cancelled).
2. The cleanup runs once per minute and processes a small batch -- it does not need to be sub-millisecond.
3. Adding `expires_at` to the index would slow down writes on every booking creation for marginal read benefit.

### Seat availability query

The seat availability endpoint (`GET /trains/schedules/{id}/seats`) performs an outer join between `seats` and `bookings`:

```sql
SELECT seats.id, seats.seat_number, seats.position,
       compartments.name, compartments.comp_type,
       bookings.status
FROM seats
LEFT OUTER JOIN bookings
  ON bookings.seat_id = seats.id
  AND bookings.schedule_id = :schedule_id
  AND bookings.status IN ('reserved', 'confirmed')
JOIN compartments ON seats.compartment_id = compartments.id
WHERE compartments.train_id = :train_id
ORDER BY compartments.name, seats.seat_number
```

This query benefits from `ix_bookings_schedule_seat` for the join condition and the unique index on `(compartment_id, seat_number)` for ordering. The result is cached in Redis with a 5-second TTL, keyed as `seats:{schedule_id}`. The cache is invalidated after every booking mutation.

---

## Seed Data Summary

The `seed_database()` function populates the database on first startup:

| Entity       | Count  | Details                                              |
|--------------|--------|------------------------------------------------------|
| Users        | 4      | 1 admin, 2 demo users (Alice, Bob), 1 system user   |
| Trains       | 3      | Subarna Express, Ekota Express, Mohanagar Provati    |
| Compartments | 6      | 2 per train (A = AC; B = non-AC)                     |
| Seats        | 150    | 25 per compartment                                   |
| Schedules    | 21     | 7 days x 3 trains                                    |

Total rows at startup: ~184. The seed is idempotent -- it checks for existing data and skips if any train rows exist.
