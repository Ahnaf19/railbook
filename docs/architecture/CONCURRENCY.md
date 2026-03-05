# Concurrency Problems and Solutions

This document describes the five concurrency problems that arise in a multi-user ticket booking system and how RailBook solves each one at the database level.

---

## Problem 1: Double Booking

**Scenario.** Two users (Alice and Bob) simultaneously try to book the same seat on the same schedule. Without protection, both `INSERT INTO bookings` statements succeed, and the seat is assigned to two passengers.

**Solution: `SELECT FOR UPDATE` row-level locking.**

Before creating a booking, the service acquires an exclusive lock on any existing booking row for the (schedule_id, seat_id) pair:

```python
locked = await session.execute(
    select(Booking)
    .where(Booking.schedule_id == schedule_id, Booking.seat_id == seat_id)
    .with_for_update()
)
existing_booking = locked.scalar_one_or_none()
if existing_booking and existing_booking.status in ("reserved", "confirmed"):
    raise HTTPException(status_code=409, detail="Seat already booked for this schedule")
```

**How it works at the PostgreSQL level:**

1. Alice's transaction issues `SELECT ... FOR UPDATE`. PostgreSQL finds no existing row, so no lock is acquired, but the transaction proceeds.
2. Bob's transaction issues the same `SELECT ... FOR UPDATE`. If Alice has not yet committed, Bob's query **blocks** until Alice's transaction completes.
3. Alice inserts the booking and commits. The lock is released.
4. Bob's `SELECT FOR UPDATE` now executes. It finds Alice's newly committed booking row with `status='reserved'`. The service raises a 409 Conflict.

The `bookings` table also has a `UNIQUE` constraint on `(schedule_id, seat_id)` (named `uq_booking_schedule_seat`). This is the last line of defense: even if the application logic had a bug, PostgreSQL would reject a duplicate insert at the constraint level. However, the `SELECT FOR UPDATE` approach provides a clean error message and avoids relying on constraint violation exceptions for control flow.

**Edge case: re-booking a cancelled seat.** If the existing booking has `status` in (`cancelled`, `refunded`), the old row is deleted and a new one is inserted in the same transaction:

```python
if existing_booking:
    await session.delete(existing_booking)
    await session.flush()
```

This maintains the UNIQUE constraint while allowing seats to be re-used after cancellation.

**Demo endpoint.** The `/demo/race-condition` endpoint spawns two concurrent booking attempts (via `asyncio.gather`) against the same seat to demonstrate this behavior. One succeeds with 201, the other fails with 409.

---

## Problem 2: Journey Overlap

**Scenario.** A user books Dhaka-Chittagong departing at 07:00 arriving at 12:00, then tries to book Dhaka-Rajshahi departing at 10:30 arriving at 16:30. The second journey overlaps with the first -- the user physically cannot be on two trains at the same time.

**Solution: Time range overlap check within the same transaction.**

After locking the seat, the service queries the user's existing active bookings and joins to their schedules to check for time overlaps:

```python
overlap = await session.execute(
    select(Booking)
    .join(Schedule, Booking.schedule_id == Schedule.id)
    .where(
        Booking.user_id == user_id,
        Booking.status.in_(["reserved", "confirmed"]),
        Schedule.departure_time < schedule.arrival_time,
        Schedule.arrival_time > schedule.departure_time,
    )
)
if overlap.scalar_one_or_none():
    raise HTTPException(status_code=409, detail="You have an overlapping journey")
```

**Why this works.** Two time intervals `[d1, a1)` and `[d2, a2)` overlap if and only if `d1 < a2 AND a1 > d2`. The query encodes this condition directly. By running this check inside the same transaction as the seat lock and booking insert, there is no window where a concurrent request could create a conflicting booking between the check and the insert.

**Why it must be in the same transaction.** If the overlap check and the insert were in separate transactions, the following race could occur:

1. Request A checks overlap -- no conflict found.
2. Request B checks overlap -- no conflict found.
3. Request A inserts booking for 07:00-12:00.
4. Request B inserts booking for 10:30-16:30.

Both succeed, but the user now has overlapping journeys. By keeping the check and insert in one transaction (with the seat locked via `FOR UPDATE` earlier), step 2 would block until step 3 commits, and then step 2's overlap check would find the conflict.

---

## Problem 3: Idempotent Booking and Payment

**Scenario.** A user clicks "Book" and the request times out at the network level. The client retries with the same parameters. Without idempotency, the user ends up with two bookings for two different seats, or is charged twice.

**Solution: Unique `idempotency_key` per booking and per payment.**

Both the `bookings` and `payments` tables have a `idempotency_key` column with a `UNIQUE` constraint. The client generates a UUID v4 before each logical operation and includes it in the request.

For booking creation:

```python
existing = await session.execute(
    select(Booking).where(Booking.idempotency_key == idempotency_key)
)
if found := existing.scalar_one_or_none():
    return found  # Return the already-created booking
```

For payment:

```python
existing_payment = await session.execute(
    select(Payment).where(Payment.idempotency_key == idempotency_key)
)
if existing_payment.scalar_one_or_none():
    return booking  # Payment already processed
```

**How it prevents duplicates:**

1. First request arrives with `idempotency_key = abc-123`. No existing row found. Booking is created.
2. Retry arrives with `idempotency_key = abc-123`. The `SELECT` finds the existing booking. The service returns it directly without creating a new one.

If two requests with the same idempotency key arrive truly simultaneously and both pass the initial check (because neither has committed yet), the `UNIQUE` constraint on `idempotency_key` causes the second `INSERT` to fail with a constraint violation, which rolls back that transaction. The first transaction's booking is the one that persists.

**The mock payment gateway also implements idempotency** at its own level. The `MockPaymentGateway` maintains a `_processed` dictionary keyed by idempotency key string. If the same key is submitted twice, it returns the original result without re-processing. This mirrors the behavior of real payment gateways (Stripe, for example, supports idempotency keys natively).

---

## Problem 4: Reservation Expiry

**Scenario.** A user reserves a seat but never pays. The seat is held indefinitely, preventing other users from booking it. In a real system with thousands of users, unpaid reservations could exhaust available inventory.

**Solution: 5-minute TTL on reservations + background cleanup with `SKIP LOCKED`.**

When a booking is created, it is given a 5-minute expiration window:

```python
booking = Booking(
    ...
    status="reserved",
    expires_at=datetime.now(UTC) + timedelta(minutes=5),
)
```

A background asyncio task runs every 60 seconds and cancels expired reservations:

```python
async def cleanup_expired_reservations(session_factory: async_sessionmaker) -> None:
    while True:
        try:
            async with session_factory() as session, session.begin():
                result = await session.execute(
                    select(Booking)
                    .where(Booking.status == "reserved", Booking.expires_at < func.now())
                    .with_for_update(skip_locked=True)
                )
                expired = result.scalars().all()
                for booking in expired:
                    booking.status = "cancelled"
                    booking.cancelled_at = func.now()
                    await log_audit(session, booking.id, SYSTEM_USER_ID, "expired_cleanup", ...)
        except Exception:
            logger.exception("Error in reservation cleanup")
        await asyncio.sleep(60)
```

**Why `SKIP LOCKED` is critical.** Consider this scenario without `SKIP LOCKED`:

1. User is in the middle of paying for booking X. The `pay_booking` function has acquired a `FOR UPDATE` lock on booking X.
2. The cleanup task runs and issues `SELECT ... FOR UPDATE` on all expired bookings.
3. If booking X happens to have just expired (the user is paying at second 4:59 and the cleanup runs at 5:01), the cleanup task **blocks** waiting for the payment transaction to release its lock.
4. The cleanup task is now stuck, unable to process any other expired bookings.

With `SKIP LOCKED`, the cleanup task skips booking X (because it is locked by the payment transaction) and processes all other expired bookings without blocking. If the payment succeeds, booking X transitions to `confirmed` and is no longer eligible for cleanup. If the payment fails, booking X will be picked up in the next cleanup cycle.

**Audit trail for cleanup.** Expired bookings are cancelled under the `SYSTEM_USER_ID` (`00000000-0000-0000-0000-000000000000`), a dedicated system user created during database seeding. The audit entry includes `action="expired_cleanup"` and metadata recording the original `expires_at` timestamp and TTL.

---

## Problem 5: Payment Atomicity

**Scenario.** A payment charge succeeds at the gateway, but the application crashes before updating the booking status to `confirmed`. The user has been charged but the booking still shows `reserved`. Or: the booking status is updated but the `Payment` record is not created, losing the financial record.

**Solution: Booking status update + Payment record + Audit entry in a single database transaction.**

The `pay_booking` function performs all three writes before calling `session.commit()`:

```python
if charge_result.status == "success":
    # 1. Update booking status
    booking.status = "confirmed"
    booking.confirmed_at = datetime.now(UTC)

    # 2. Create payment record
    payment = Payment(
        booking_id=booking.id,
        idempotency_key=idempotency_key,
        amount=booking.total_amount,
        status="success",
        gateway_ref=charge_result.gateway_ref,
        completed_at=datetime.now(UTC),
    )
    session.add(payment)

    # 3. Audit entry
    await log_audit(session, booking.id, user_id, "confirmed", "reserved", "confirmed",
                    metadata={"gateway_ref": charge_result.gateway_ref})

await session.commit()  # All three or nothing
```

**If the commit fails** (database down, constraint violation, network error), all three changes are rolled back atomically. The booking remains `reserved`, no payment record exists, and no audit entry is created. The user can retry with the same idempotency key.

**If the gateway charge succeeded but the commit fails**, the system is in a state where the customer was charged but the booking was not confirmed. This is handled by:

1. **Payment idempotency**: When the user retries, the gateway returns the same successful result for the same idempotency key (the mock gateway caches results in its `_processed` dict; real gateways like Stripe do the same).
2. **Payment idempotency check**: The `pay_booking` function checks for an existing `Payment` row with the same idempotency key before charging. If the row exists, it means a previous attempt already persisted everything successfully. If the row does not exist (because the commit failed), the gateway is called again, returns the cached success, and the booking is confirmed.

**The same pattern applies to payment failure.** If the charge fails, the booking is moved to `cancelled`, a `Payment` record with `status="failed"` and `failure_reason` is created, and an audit entry records the failure -- all in one commit.

**Pre-payment validation** also happens under the lock:

```python
result = await session.execute(
    select(Booking).where(Booking.id == booking_id).with_for_update()
)
booking = result.scalar_one_or_none()
```

This lock prevents a race where the cleanup task cancels an expired booking at the same moment the user is trying to pay. The `FOR UPDATE` lock on the booking row ensures only one of these transactions proceeds. Combined with the explicit expiry check (`if booking.expires_at < datetime.now(UTC)`), this prevents payment on already-expired reservations.

---

## Summary Table

| # | Problem              | Root Cause                         | Solution                                                 | Mechanism                          |
|---|----------------------|------------------------------------|----------------------------------------------------------|------------------------------------|
| 1 | Double booking       | Two concurrent INSERTs for same seat | `SELECT FOR UPDATE` + UNIQUE constraint on (schedule, seat) | PostgreSQL row-level lock          |
| 2 | Journey overlap      | Time range conflict across bookings | Overlap query in same transaction as seat lock            | SQL time range predicate           |
| 3 | Duplicate operations | Network retries / double clicks    | Unique `idempotency_key` on bookings and payments        | UNIQUE constraint + early return   |
| 4 | Stale reservations   | Users abandon without paying       | 5-min TTL + background cleanup with `SKIP LOCKED`        | asyncio task + PostgreSQL advisory |
| 5 | Payment atomicity    | Crash between gateway and DB write | Single transaction for booking + payment + audit          | PostgreSQL ACID commit             |

---

## Booking State Machine

```
                    +----------+
                    | reserved |  (created with 5-min TTL)
                    +----+-----+
                         |
              +----------+----------+
              |                     |
       pay succeeds           expires / pay fails
              |                     |
      +-------v-------+    +-------v--------+
      |   confirmed   |    |   cancelled    |
      +-------+-------+    +----------------+
              |
         refund requested
         (>1hr before departure)
              |
      +-------v-------+
      |   refunded    |
      +---------------+
```

Each arrow in this diagram corresponds to a database transaction that atomically updates `bookings.status` and inserts an `audit_trail` entry.
