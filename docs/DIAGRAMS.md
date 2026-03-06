# RailBook Mermaid Diagrams

Paste each diagram into [excalidraw.com](https://excalidraw.com) via the Mermaid-to-Excalidraw feature,
or into any Mermaid renderer (GitHub renders these natively in markdown).

---

## 1. System Architecture (full)

```mermaid
graph TB
    subgraph Client["Frontend — React 18 + Vite"]
        UI_TRAINS["Train Browser<br/>schedules, seat grid"]
        UI_BOOK["Booking Flow<br/>reserve → pay → ticket"]
        UI_DEMO["Concurrency Demo<br/>Alice vs Bob split-screen"]
        UI_ADMIN["Admin Dashboard<br/>stats, occupancy, audit"]
    end

    subgraph API["Backend — FastAPI (fully async)"]
        AUTH["Auth Module<br/>register, login, refresh, me<br/><i>JWT + bcrypt</i>"]
        TRAINS["Trains Module<br/>list trains, schedules<br/>seat availability"]
        BOOKING["Booking Engine<br/>reserve, pay, refund<br/><i>SELECT FOR UPDATE</i>"]
        PAYMENT["Payment Gateway<br/>mock, configurable<br/><i>idempotent charges</i>"]
        AUDIT["Audit Service<br/>atomic in-transaction<br/><i>append-only log</i>"]
        RATELIMIT["Rate Limiter<br/>sliding window<br/><i>sorted sets</i>"]
        DEMO["Demo Service<br/>asyncio.gather race"]
        ADMIN["Admin Service<br/>stats, occupancy"]
        CLEANUP["Cleanup Task<br/>60s interval<br/><i>SKIP LOCKED</i>"]
    end

    subgraph Data["Data Layer"]
        PG[("PostgreSQL 16<br/>8 tables<br/>row-level locks<br/>ACID transactions")]
        REDIS[("Redis 7<br/>seat cache (5s TTL)<br/>rate limit counters")]
    end

    UI_TRAINS -->|"GET /trains/**"| TRAINS
    UI_BOOK -->|"POST /bookings/**"| BOOKING
    UI_DEMO -->|"POST /demo/race-condition"| DEMO
    UI_ADMIN -->|"GET /admin/**"| ADMIN
    Client -->|"POST /auth/**"| AUTH

    AUTH --> PG
    TRAINS --> PG
    TRAINS -.->|"cache read/write"| REDIS
    BOOKING --> PG
    BOOKING --> PAYMENT
    BOOKING --> AUDIT
    RATELIMIT -.->|"sorted set ops"| REDIS
    CLEANUP --> PG
    CLEANUP --> AUDIT
    DEMO --> BOOKING
    ADMIN --> PG

    style PG fill:#336791,color:#fff,stroke:#1e3a5f
    style REDIS fill:#dc382d,color:#fff,stroke:#a12a23
    style BOOKING fill:#2b6cb0,color:#fff,stroke:#1e4e8c
    style CLEANUP fill:#744210,color:#fff,stroke:#5a3510
    style AUDIT fill:#276749,color:#fff,stroke:#1a4731
```

---

## 2. Booking State Machine

```mermaid
stateDiagram-v2
    [*] --> reserved : POST /bookings

    reserved --> confirmed : Payment succeeds
    reserved --> cancelled : Payment fails
    reserved --> cancelled : Reservation expires (5min)

    confirmed --> refunded : Refund requested

    note right of reserved
        5-minute TTL (expires_at = now + 5min)
        Seat locked via UNIQUE(schedule_id, seat_id)
        SELECT FOR UPDATE prevents double booking
    end note

    note right of confirmed
        Payment record with gateway_ref
        Booking + Payment + Audit in one commit
    end note

    note left of cancelled
        Seat released for rebooking
        Cleanup uses SKIP LOCKED
    end note

    note right of refunded
        Only if departure > 1hr away
        gateway.refund() called
    end note
```

**Transition details:**

| Transition | Trigger | Atomic commit includes |
|---|---|---|
| `[*]` → `reserved` | `POST /bookings` | Booking row + audit entry |
| `reserved` → `confirmed` | `POST /bookings/:id/pay` (charge succeeds) | Booking status + Payment(success) + audit |
| `reserved` → `cancelled` | `POST /bookings/:id/pay` (charge fails) | Booking status + Payment(failed) + audit |
| `reserved` → `cancelled` | Cleanup task (expires_at < now) | Booking status + audit (SYSTEM_USER_ID) |
| `confirmed` → `refunded` | `POST /bookings/:id/refund` | Booking status + gateway.refund() + audit |

---

## 3. Database Schema (ER Diagram)

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        string phone
        string role "user | admin"
        timestamp created_at
    }

    trains {
        uuid id PK
        string name
        string train_number UK
        string origin
        string destination
    }

    schedules {
        uuid id PK
        uuid train_id FK
        timestamp departure_time
        timestamp arrival_time
        string status
    }

    compartments {
        uuid id PK
        uuid train_id FK
        string name "A-E"
        string comp_type "ac | non_ac"
        int capacity "50"
    }

    seats {
        uuid id PK
        uuid compartment_id FK
        int seat_number
        string position "window | corridor"
    }

    bookings {
        uuid id PK
        uuid user_id FK
        uuid schedule_id FK
        uuid seat_id FK
        string status "reserved | confirmed | cancelled | refunded"
        uuid idempotency_key UK
        timestamp reserved_at
        timestamp expires_at "now + 5min"
        timestamp confirmed_at
        timestamp cancelled_at
        decimal total_amount "1500 AC / 800 Non-AC"
    }

    payments {
        uuid id PK
        uuid booking_id FK
        uuid idempotency_key UK
        decimal amount
        string status "pending | success | failed"
        string gateway_ref
        timestamp attempted_at
        timestamp completed_at
        string failure_reason
    }

    audit_trail {
        bigint id PK "autoincrement"
        uuid booking_id FK
        uuid user_id FK
        string action
        string previous_status
        string new_status
        json metadata
        string ip_address
        timestamp created_at
    }

    users ||--o{ bookings : "has"
    trains ||--o{ schedules : "runs"
    trains ||--o{ compartments : "contains"
    compartments ||--o{ seats : "has"
    schedules ||--o{ bookings : "for"
    seats ||--o{ bookings : "reserved by"
    bookings ||--o{ payments : "paid via"
    bookings ||--o{ audit_trail : "tracked by"
    users ||--o{ audit_trail : "performed by"
```

---

## 4. Booking Transaction Flow (Sequence)

```mermaid
sequenceDiagram
    actor Alice
    actor Bob
    participant API as FastAPI
    participant DB as PostgreSQL

    Note over Alice, Bob: Both click "Book" on seat A3 at the same time

    Alice->>API: POST /bookings {seat: A3, key: uuid-1}
    Bob->>API: POST /bookings {seat: A3, key: uuid-2}

    API->>DB: BEGIN (Alice's txn)
    API->>DB: BEGIN (Bob's txn)

    API->>DB: SELECT ... WHERE seat=A3 FOR UPDATE (Alice)
    Note over DB: Alice acquires row lock

    API->>DB: SELECT ... WHERE seat=A3 FOR UPDATE (Bob)
    Note over DB: Bob BLOCKS — waiting for Alice's lock

    API->>DB: INSERT booking (Alice)
    API->>DB: INSERT audit_trail (Alice)
    API->>DB: COMMIT (Alice)
    Note over DB: Lock released

    API-->>Alice: 201 Created ✓

    Note over DB: Bob's SELECT unblocks<br/>Finds Alice's committed booking
    API-->>Bob: 409 Conflict ✗

    API->>DB: ROLLBACK (Bob)
```

---

## 5. Payment Flow (Sequence)

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant DB as PostgreSQL
    participant GW as Payment Gateway

    User->>API: POST /bookings/:id/pay {key: uuid-3}

    API->>DB: SELECT booking FOR UPDATE
    Note over DB: Lock acquired<br/>Validates: status=reserved, not expired, belongs to user

    API->>DB: Check payment idempotency_key
    Note over DB: No existing payment → proceed

    API->>DB: INSERT audit (payment_attempted)
    API->>DB: FLUSH

    API->>GW: charge(amount, idempotency_key)
    Note over GW: 500ms latency (configurable)

    alt Charge succeeds
        GW-->>API: {status: success, gateway_ref: MOCK-abc123}
        API->>DB: UPDATE booking SET status=confirmed
        API->>DB: INSERT payment (status=success)
        API->>DB: INSERT audit (confirmed)
        API->>DB: COMMIT
        Note over DB: All 3 writes atomic
        API-->>User: 200 {status: confirmed}
    else Charge fails
        GW-->>API: {status: failed, reason: Card declined}
        API->>DB: UPDATE booking SET status=cancelled
        API->>DB: INSERT payment (status=failed)
        API->>DB: INSERT audit (payment_failed)
        API->>DB: COMMIT
        Note over DB: Failure also recorded atomically
        API-->>User: 200 {status: cancelled}
    end
```

---

## 6. Rate Limiting (Sliding Window)

```mermaid
flowchart LR
    subgraph Request["Incoming Request"]
        REQ["POST /bookings"]
    end

    subgraph Redis["Redis Sorted Set — rl:booking:user-123"]
        direction TB
        OP1["ZREMRANGEBYSCORE<br/>remove entries older than 60s"]
        OP2["ZADD {now: now}<br/>add current request"]
        OP3["ZCARD<br/>count entries in window"]
        OP4["EXPIRE key 60s<br/>auto-cleanup"]
        OP1 --> OP2 --> OP3 --> OP4
    end

    subgraph Decision
        CHECK{"count > 5?"}
        ALLOW["✓ Allow<br/>remaining: 5 - count"]
        DENY["✗ 429 Too Many Requests<br/>Retry-After: 60"]
    end

    REQ --> OP1
    OP4 --> CHECK
    CHECK -->|No| ALLOW
    CHECK -->|Yes| DENY

    style DENY fill:#ef4444,color:#fff
    style ALLOW fill:#22c55e,color:#fff
```

---

## 7. Reservation Cleanup (SKIP LOCKED)

```mermaid
flowchart TB
    START["Cleanup Task<br/>runs every 60s"] --> QUERY

    QUERY["SELECT expired bookings<br/>WHERE status=reserved<br/>AND expires_at < now()<br/>FOR UPDATE SKIP LOCKED"]

    QUERY --> CHECK{"Any found?"}

    CHECK -->|No| SLEEP["asyncio.sleep(60)"]
    SLEEP --> QUERY

    CHECK -->|Yes| PROCESS

    subgraph PROCESS["For each expired booking"]
        CANCEL["SET status = cancelled"]
        AUDIT["INSERT audit_trail<br/>action: expired_cleanup<br/>user: SYSTEM_USER_ID"]
        CANCEL --> AUDIT
    end

    PROCESS --> COMMIT["COMMIT<br/>(all cancellations atomic)"]
    COMMIT --> SLEEP

    LOCKED["Booking being paid<br/>(locked by pay_booking)"]
    LOCKED -.->|"SKIP LOCKED<br/>silently skipped"| QUERY

    style LOCKED fill:#eab308,color:#1e1e1e
    style COMMIT fill:#22c55e,color:#fff
```

---

## 8. Test Coverage Map

> **Legend:** Each color = one test category. Number in parentheses = test count.
> All tests are async, run against real PostgreSQL (`railbook_test`), no mocks for DB or concurrency.

```mermaid
flowchart LR
    ROOT((("34 Tests")))

    subgraph AUTH_G["Auth (7)"]
        A1["Register"]
        A2["Login"]
        A3["JWT validation"]
        A4["Duplicate email 409"]
        A5["Expired token"]
        A6["Refresh token"]
        A7["GET /auth/me"]
    end

    subgraph BOOK_G["Bookings (4)"]
        B1["Reserve pay confirm"]
        B2["List user bookings"]
        B3["Get booking detail"]
        B4["Booking lifecycle"]
    end

    subgraph CONC_G["Concurrency (4)"]
        C1["Double booking prevented\nasyncio.gather, real DB"]
        C2["Concurrent different seats"]
        C3["Idempotent booking"]
        C4["Expired reservation released"]
    end

    subgraph PAY_G["Payments (3)"]
        P1["Success flow"]
        P2["Failure flow"]
        P3["Payment idempotency"]
    end

    subgraph AUD_G["Audit Trail (5)"]
        D1["Reserve creates entry"]
        D2["Pay success 3 entries"]
        D3["Pay failure 3 entries"]
        D4["Refund creates entry"]
        D5["Chronological order"]
    end

    subgraph RL_G["Rate Limiting (7)"]
        R1["Blocks after threshold"]
        R2["429 headers"]
        R3["Per-user isolation"]
        R4["Auth by IP"]
        R5["Graceful degradation"]
        R6["Payment stricter"]
        R7["Auth blocking"]
    end

    subgraph OTHER_G["Trains + Overlap (4)"]
        O1["Journey overlap"]
        O2["List trains"]
        O3["Future schedules"]
        O4["Seat availability"]
    end

    ROOT --- AUTH_G
    ROOT --- BOOK_G
    ROOT --- CONC_G
    ROOT --- PAY_G
    ROOT --- AUD_G
    ROOT --- RL_G
    ROOT --- OTHER_G

    style ROOT fill:#1e1e1e,color:#fff,stroke:#fff,stroke-width:2px
    style AUTH_G fill:#1e3a5f,color:#fff,stroke:#4a90d9
    style BOOK_G fill:#1a4731,color:#fff,stroke:#38a169
    style CONC_G fill:#7c2d12,color:#fff,stroke:#f97316
    style PAY_G fill:#4c1d95,color:#fff,stroke:#a78bfa
    style AUD_G fill:#713f12,color:#fff,stroke:#eab308
    style RL_G fill:#831843,color:#fff,stroke:#ec4899
    style OTHER_G fill:#134e4a,color:#fff,stroke:#2dd4bf

    style A1 fill:#2563eb,color:#fff,stroke:none
    style A2 fill:#2563eb,color:#fff,stroke:none
    style A3 fill:#2563eb,color:#fff,stroke:none
    style A4 fill:#2563eb,color:#fff,stroke:none
    style A5 fill:#2563eb,color:#fff,stroke:none
    style A6 fill:#2563eb,color:#fff,stroke:none
    style A7 fill:#2563eb,color:#fff,stroke:none

    style B1 fill:#16a34a,color:#fff,stroke:none
    style B2 fill:#16a34a,color:#fff,stroke:none
    style B3 fill:#16a34a,color:#fff,stroke:none
    style B4 fill:#16a34a,color:#fff,stroke:none

    style C1 fill:#ea580c,color:#fff,stroke:none
    style C2 fill:#ea580c,color:#fff,stroke:none
    style C3 fill:#ea580c,color:#fff,stroke:none
    style C4 fill:#ea580c,color:#fff,stroke:none

    style P1 fill:#7c3aed,color:#fff,stroke:none
    style P2 fill:#7c3aed,color:#fff,stroke:none
    style P3 fill:#7c3aed,color:#fff,stroke:none

    style D1 fill:#ca8a04,color:#fff,stroke:none
    style D2 fill:#ca8a04,color:#fff,stroke:none
    style D3 fill:#ca8a04,color:#fff,stroke:none
    style D4 fill:#ca8a04,color:#fff,stroke:none
    style D5 fill:#ca8a04,color:#fff,stroke:none

    style R1 fill:#db2777,color:#fff,stroke:none
    style R2 fill:#db2777,color:#fff,stroke:none
    style R3 fill:#db2777,color:#fff,stroke:none
    style R4 fill:#db2777,color:#fff,stroke:none
    style R5 fill:#db2777,color:#fff,stroke:none
    style R6 fill:#db2777,color:#fff,stroke:none
    style R7 fill:#db2777,color:#fff,stroke:none

    style O1 fill:#0d9488,color:#fff,stroke:none
    style O2 fill:#0d9488,color:#fff,stroke:none
    style O3 fill:#0d9488,color:#fff,stroke:none
    style O4 fill:#0d9488,color:#fff,stroke:none
```

---

## Usage Notes

**To use in Excalidraw:**
1. Go to [excalidraw.com](https://excalidraw.com)
2. Open the Mermaid-to-Excalidraw tool (via library or paste)
3. Paste any diagram above
4. It auto-layouts as editable Excalidraw elements
5. Arrange multiple diagrams on one canvas

**To render on GitHub:**
These render natively in any `.md` file on GitHub — just commit this file (or copy diagrams into README).

**For presentations:**
The sequence diagrams (#4, #5) are the best for explaining the concurrency logic step-by-step.
The state machine (#2) is perfect for "walk me through the booking lifecycle."
The ER diagram (#3) shows you understand relational modeling.
