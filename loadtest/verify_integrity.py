#!/usr/bin/env python3
"""Post-load-test database integrity checker.

Verifies critical invariants after a load test run.
Exit code 0 = all checks pass, 1 = failures found.
"""

import sys

import psycopg2

from config import DB_URL


def check_no_double_bookings(cur):
    """No two active bookings for the same schedule+seat."""
    cur.execute("""
        SELECT schedule_id, seat_id, COUNT(*)
        FROM bookings
        WHERE status IN ('reserved', 'confirmed')
        GROUP BY schedule_id, seat_id
        HAVING COUNT(*) > 1
    """)
    rows = cur.fetchall()
    if rows:
        print(f"FAIL: {len(rows)} double bookings found!")
        for r in rows:
            print(f"  schedule={r[0]} seat={r[1]} count={r[2]}")
        return False
    print("PASS: No double bookings")
    return True


def check_audit_trail_completeness(cur):
    """Every booking should have at least one audit entry."""
    cur.execute("""
        SELECT b.id
        FROM bookings b
        LEFT JOIN audit_trail a ON a.booking_id = b.id
        WHERE a.id IS NULL
    """)
    rows = cur.fetchall()
    if rows:
        print(f"FAIL: {len(rows)} bookings without audit entries")
        return False
    print("PASS: All bookings have audit trail")
    return True


def check_no_stale_reservations(cur):
    """No expired reservations still in 'reserved' status."""
    cur.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE status = 'reserved'
          AND expires_at < NOW() - INTERVAL '2 minutes'
    """)
    count = cur.fetchone()[0]
    if count > 0:
        print(f"FAIL: {count} stale reservations found (expired >2min ago)")
        return False
    print("PASS: No stale reservations")
    return True


def check_payment_consistency(cur):
    """Confirmed bookings should have a successful payment."""
    cur.execute("""
        SELECT b.id
        FROM bookings b
        LEFT JOIN payments p ON p.booking_id = b.id AND p.status = 'success'
        WHERE b.status = 'confirmed' AND p.id IS NULL
    """)
    rows = cur.fetchall()
    if rows:
        print(f"FAIL: {len(rows)} confirmed bookings without successful payment")
        return False
    print("PASS: Payment consistency verified")
    return True


def main():
    print(f"Connecting to {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    checks = [
        check_no_double_bookings,
        check_audit_trail_completeness,
        check_no_stale_reservations,
        check_payment_consistency,
    ]

    results = [check(cur) for check in checks]
    cur.close()
    conn.close()

    if all(results):
        print("\nAll integrity checks PASSED")
        sys.exit(0)
    else:
        failed = sum(1 for r in results if not r)
        print(f"\n{failed}/{len(results)} checks FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
