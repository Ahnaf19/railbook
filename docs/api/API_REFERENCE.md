# RailBook API Reference

Base URL: `http://localhost:8000`

All request and response bodies use JSON. UUIDs are formatted as standard hyphenated strings (e.g., `550e8400-e29b-41d4-a716-446655440000`). Timestamps use ISO 8601 with timezone.

---

## Table of Contents

- [Authentication](#authentication)
- [Health](#health)
- [Auth Endpoints](#auth-endpoints)
- [Train Endpoints](#train-endpoints)
- [Booking Endpoints](#booking-endpoints)
- [Admin Endpoints](#admin-endpoints)
- [Demo Endpoints](#demo-endpoints)
- [Rate Limiting](#rate-limiting)

---

## Authentication

Endpoints that require authentication expect a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens are JWTs signed with HS256. Access tokens expire after 15 minutes. Refresh tokens expire after 7 days. Token type is embedded in the payload (`"type": "access"` or `"type": "refresh"`).

Admin endpoints additionally require the authenticated user to have `role: "admin"`.

---

## Health

### `GET /health`

Returns the API health status. No authentication required.

**Response: `200 OK`**

```json
{
  "status": "ok"
}
```

**curl:**

```bash
curl http://localhost:8000/health
```

---

## Auth Endpoints

All auth endpoints are rate-limited to **10 requests per 5 minutes per IP** (when Redis is available).

### `POST /auth/register`

Register a new user account. Returns access and refresh tokens on success.

**Auth required:** No

**Request body:**

| Field      | Type            | Required | Description                |
|------------|-----------------|----------|----------------------------|
| `email`    | string          | Yes      | User email address         |
| `password` | string          | Yes      | User password              |
| `full_name`| string          | Yes      | Full name                  |
| `phone`    | string or null  | No       | Phone number               |

**curl:**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123",
    "full_name": "Jane Doe",
    "phone": "+8801700000001"
  }'
```

**Response: `201 Created`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Error responses:**

| Status | Detail                     | Cause                          |
|--------|----------------------------|--------------------------------|
| 409    | `Email already registered` | Email is already in use        |
| 429    | `Too many auth requests`   | Rate limit exceeded            |

---

### `POST /auth/login`

Authenticate with email and password.

**Auth required:** No

**Request body:**

| Field      | Type   | Required | Description        |
|------------|--------|----------|--------------------|
| `email`    | string | Yes      | User email address |
| `password` | string | Yes      | User password      |

**curl:**

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "password123"
  }'
```

**Response: `200 OK`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Error responses:**

| Status | Detail                | Cause                      |
|--------|-----------------------|----------------------------|
| 401    | `Invalid credentials` | Wrong email or password    |
| 429    | `Too many auth requests` | Rate limit exceeded     |

---

### `POST /auth/refresh`

Exchange a valid refresh token for a new token pair.

**Auth required:** No (uses refresh token in body)

**Request body:**

| Field           | Type   | Required | Description         |
|-----------------|--------|----------|---------------------|
| `refresh_token` | string | Yes      | A valid refresh JWT |

**curl:**

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
  }'
```

**Response: `200 OK`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Error responses:**

| Status | Detail                               | Cause                                  |
|--------|--------------------------------------|----------------------------------------|
| 401    | `Invalid token type`                 | Token is not a refresh token           |
| 401    | `Invalid or expired refresh token`   | Token is malformed or expired          |
| 401    | `User not found`                     | User account no longer exists          |

---

### `GET /auth/me`

Return the authenticated user's profile.

**Auth required:** Yes (Bearer token)

**curl:**

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

**Response: `200 OK`**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "alice@example.com",
  "full_name": "Alice Rahman",
  "phone": "+8801711111111",
  "role": "user",
  "created_at": "2025-01-15T10:30:00+00:00"
}
```

**Error responses:**

| Status | Detail                       | Cause                    |
|--------|------------------------------|--------------------------|
| 401    | `Invalid or expired token`   | Token is invalid/expired |
| 401    | `User not found`             | User no longer exists    |

---

## Train Endpoints

These endpoints are public and do not require authentication.

### `GET /trains`

List all available trains.

**Auth required:** No

**curl:**

```bash
curl http://localhost:8000/trains
```

**Response: `200 OK`**

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Subarna Express",
    "train_number": "SE-701",
    "origin": "Dhaka",
    "destination": "Chittagong"
  },
  {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "name": "Ekota Express",
    "train_number": "EE-501",
    "origin": "Dhaka",
    "destination": "Rajshahi"
  },
  {
    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "name": "Mohanagar Provati",
    "train_number": "MP-301",
    "origin": "Dhaka",
    "destination": "Sylhet"
  }
]
```

---

### `GET /trains/{train_id}/schedules`

List all schedules for a specific train. The seed data creates schedules for the next 7 days.

**Auth required:** No

**Path parameters:**

| Parameter  | Type | Description       |
|------------|------|-------------------|
| `train_id` | UUID | ID of the train   |

**curl:**

```bash
curl http://localhost:8000/trains/a1b2c3d4-e5f6-7890-abcd-ef1234567890/schedules
```

**Response: `200 OK`**

```json
[
  {
    "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "train_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "departure_time": "2025-01-16T07:00:00+00:00",
    "arrival_time": "2025-01-16T12:00:00+00:00",
    "status": "scheduled"
  }
]
```

---

### `GET /trains/schedules/{schedule_id}/seats`

Get seat availability for a specific schedule. Returns all seats grouped by compartment with their booking status. Results are cached in Redis when available.

**Auth required:** No

**Path parameters:**

| Parameter     | Type | Description          |
|---------------|------|----------------------|
| `schedule_id` | UUID | ID of the schedule   |

**curl:**

```bash
curl http://localhost:8000/trains/schedules/d4e5f6a7-b8c9-0123-defa-234567890123/seats
```

**Response: `200 OK`**

```json
{
  "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "train_name": "Subarna Express",
  "total_seats": 250,
  "available_seats": 248,
  "seats": [
    {
      "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
      "seat_number": 1,
      "position": "window",
      "compartment_name": "A",
      "comp_type": "ac",
      "booking_status": null
    },
    {
      "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
      "seat_number": 2,
      "position": "corridor",
      "compartment_name": "A",
      "comp_type": "ac",
      "booking_status": "reserved"
    }
  ]
}
```

Each train has 5 compartments (A-E) with 50 seats each (250 total). Compartments A and B are `ac` type; C, D, and E are `non_ac` type. Seat positions alternate between `window` and `corridor`. The `booking_status` field is `null` for available seats, or one of `reserved`, `confirmed`, `refunded`, or `cancelled`.

**Error responses:**

| Status | Detail               | Cause                         |
|--------|----------------------|-------------------------------|
| 404    | `Schedule not found` | No schedule with that ID      |

---

## Booking Endpoints

All booking endpoints require Bearer token authentication.

### `POST /bookings`

Create a new seat reservation. The reservation expires after 5 minutes if not paid. Uses `SELECT FOR UPDATE` to prevent double-booking the same seat.

**Auth required:** Yes

**Rate limit:** 5 requests per 60 seconds per user

**Request body:**

| Field             | Type | Required | Description                                    |
|-------------------|------|----------|------------------------------------------------|
| `schedule_id`     | UUID | Yes      | Schedule to book                               |
| `seat_id`         | UUID | Yes      | Seat to reserve                                |
| `idempotency_key` | UUID | Yes      | Client-generated UUID for idempotent creation  |

The `idempotency_key` ensures that retrying the same request returns the original booking rather than creating a duplicate. Clients should generate a UUID v4 and reuse it across retries.

**Pricing:** AC compartments (A, B) cost 1500.00. Non-AC compartments (C, D, E) cost 800.00.

**curl:**

```bash
curl -X POST http://localhost:8000/bookings \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "idempotency_key": "11111111-2222-3333-4444-555555555555"
  }'
```

**Response: `201 Created`**

```json
{
  "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "status": "reserved",
  "total_amount": "1500.00",
  "reserved_at": "2025-01-15T14:30:00+00:00",
  "expires_at": "2025-01-15T14:35:00+00:00",
  "confirmed_at": null,
  "cancelled_at": null,
  "idempotency_key": "11111111-2222-3333-4444-555555555555"
}
```

**Error responses:**

| Status | Detail                                     | Cause                                          |
|--------|--------------------------------------------|-------------------------------------------------|
| 401    | `Invalid or expired token`                 | Missing or invalid Bearer token                 |
| 404    | `Schedule not found`                       | Invalid schedule_id                             |
| 404    | `Seat not found`                           | Invalid seat_id                                 |
| 409    | `Seat already booked for this schedule`    | Another user already holds this seat            |
| 409    | `You have an overlapping journey`          | User has a booking with overlapping departure/arrival times |
| 429    | `Too many booking requests`                | Rate limit exceeded                             |

---

### `POST /bookings/{booking_id}/pay`

Pay for a reserved booking. Calls the (mock) payment gateway. On success, the booking status changes to `confirmed`. On payment failure, the booking is `cancelled`.

**Auth required:** Yes

**Rate limit:** 3 requests per 60 seconds per user

**Path parameters:**

| Parameter    | Type | Description       |
|--------------|------|-------------------|
| `booking_id` | UUID | ID of the booking |

**Request body:**

| Field             | Type | Required | Description                                   |
|-------------------|------|----------|-----------------------------------------------|
| `idempotency_key` | UUID | Yes      | Client-generated UUID for idempotent payment  |

**curl:**

```bash
curl -X POST http://localhost:8000/bookings/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/pay \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "66666666-7777-8888-9999-aaaaaaaaaaaa"
  }'
```

**Response: `200 OK`**

```json
{
  "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "status": "confirmed",
  "total_amount": "1500.00",
  "reserved_at": "2025-01-15T14:30:00+00:00",
  "expires_at": "2025-01-15T14:35:00+00:00",
  "confirmed_at": "2025-01-15T14:31:00+00:00",
  "cancelled_at": null,
  "idempotency_key": "11111111-2222-3333-4444-555555555555"
}
```

If payment fails (determined by the mock gateway's configurable failure rate), the booking status becomes `cancelled` and `cancelled_at` is set.

**Error responses:**

| Status | Detail                                          | Cause                                    |
|--------|-------------------------------------------------|------------------------------------------|
| 400    | `Booking is <status>, not reserved`             | Booking is not in `reserved` status      |
| 400    | `Reservation expired`                           | The 5-minute reservation window passed   |
| 403    | `Not your booking`                              | Authenticated user does not own booking  |
| 404    | `Booking not found`                             | Invalid booking_id                       |
| 429    | `Too many payment requests`                     | Rate limit exceeded                      |

---

### `GET /bookings`

List all bookings for the authenticated user. Optionally filter by status.

**Auth required:** Yes

**Query parameters:**

| Parameter | Type           | Required | Description                                           |
|-----------|----------------|----------|-------------------------------------------------------|
| `status`  | string or null | No       | Filter by status: `reserved`, `confirmed`, `cancelled`, `refunded` |

**curl:**

```bash
# All bookings
curl http://localhost:8000/bookings \
  -H "Authorization: Bearer <access_token>"

# Only confirmed bookings
curl "http://localhost:8000/bookings?status=confirmed" \
  -H "Authorization: Bearer <access_token>"
```

**Response: `200 OK`**

```json
[
  {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "status": "confirmed",
    "total_amount": "1500.00",
    "reserved_at": "2025-01-15T14:30:00+00:00",
    "expires_at": "2025-01-15T14:35:00+00:00",
    "confirmed_at": "2025-01-15T14:31:00+00:00",
    "cancelled_at": null,
    "idempotency_key": "11111111-2222-3333-4444-555555555555"
  }
]
```

Results are ordered by `reserved_at` descending (most recent first).

---

### `GET /bookings/{booking_id}`

Get a single booking by ID.

**Auth required:** Yes

**Path parameters:**

| Parameter    | Type | Description       |
|--------------|------|-------------------|
| `booking_id` | UUID | ID of the booking |

**curl:**

```bash
curl http://localhost:8000/bookings/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee \
  -H "Authorization: Bearer <access_token>"
```

**Response: `200 OK`**

Returns a single `BookingResponse` object (same schema as shown in the create/pay responses above).

---

### `POST /bookings/{booking_id}/refund`

Refund a confirmed booking. The booking must be confirmed and departure must be more than 1 hour away.

**Auth required:** Yes

**Rate limit:** 3 requests per 60 seconds per user

**Path parameters:**

| Parameter    | Type | Description       |
|--------------|------|-------------------|
| `booking_id` | UUID | ID of the booking |

**Request body:** None

**curl:**

```bash
curl -X POST http://localhost:8000/bookings/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/refund \
  -H "Authorization: Bearer <access_token>"
```

**Response: `200 OK`**

```json
{
  "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "status": "refunded",
  "total_amount": "1500.00",
  "reserved_at": "2025-01-15T14:30:00+00:00",
  "expires_at": "2025-01-15T14:35:00+00:00",
  "confirmed_at": "2025-01-15T14:31:00+00:00",
  "cancelled_at": "2025-01-15T15:00:00+00:00",
  "idempotency_key": "11111111-2222-3333-4444-555555555555"
}
```

**Error responses:**

| Status | Detail                                          | Cause                                      |
|--------|-------------------------------------------------|--------------------------------------------|
| 400    | `Booking is <status>, not confirmed`            | Booking is not in `confirmed` status       |
| 400    | `Cannot refund within 1 hour of departure`      | Departure is less than 1 hour away         |
| 403    | `Not your booking`                              | Authenticated user does not own booking    |
| 404    | `Booking not found`                             | Invalid booking_id                         |
| 429    | `Too many payment requests`                     | Rate limit exceeded                        |

---

## Admin Endpoints

All admin endpoints require Bearer token authentication with a user whose `role` is `"admin"`. The seed data creates an admin account with email `admin@railbook.com` and password `admin123`.

### `GET /admin/stats`

Get platform-wide booking and revenue statistics.

**Auth required:** Yes (admin only)

**curl:**

```bash
curl http://localhost:8000/admin/stats \
  -H "Authorization: Bearer <admin_access_token>"
```

**Response: `200 OK`**

```json
{
  "total_bookings": 42,
  "confirmed_bookings": 30,
  "cancelled_bookings": 8,
  "refunded_bookings": 4,
  "total_revenue": 45000.00
}
```

---

### `GET /admin/bookings`

List all bookings across all users with pagination.

**Auth required:** Yes (admin only)

**Query parameters:**

| Parameter | Type           | Default | Constraints | Description                    |
|-----------|----------------|---------|-------------|--------------------------------|
| `status`  | string or null | null    | --          | Filter by booking status       |
| `limit`   | int            | 50      | max 200     | Number of results to return    |
| `offset`  | int            | 0       | min 0       | Number of results to skip      |

**curl:**

```bash
# All bookings, first page
curl "http://localhost:8000/admin/bookings?limit=10&offset=0" \
  -H "Authorization: Bearer <admin_access_token>"

# Only cancelled bookings
curl "http://localhost:8000/admin/bookings?status=cancelled" \
  -H "Authorization: Bearer <admin_access_token>"
```

**Response: `200 OK`**

```json
[
  {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234",
    "status": "confirmed",
    "total_amount": 1500.00,
    "reserved_at": "2025-01-15T14:30:00+00:00",
    "confirmed_at": "2025-01-15T14:31:00+00:00"
  }
]
```

Results are ordered by `reserved_at` descending. Note that the admin bookings response includes a subset of fields compared to the user-facing `BookingResponse`.

---

### `GET /admin/occupancy`

Get occupancy rates per schedule. Each entry shows the number of booked seats (reserved or confirmed) out of the total capacity (250 seats per train).

**Auth required:** Yes (admin only)

**curl:**

```bash
curl http://localhost:8000/admin/occupancy \
  -H "Authorization: Bearer <admin_access_token>"
```

**Response: `200 OK`**

```json
[
  {
    "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "departure_time": "2025-01-16T07:00:00+00:00",
    "train_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "booked_seats": 12,
    "total_seats": 250,
    "occupancy_pct": 4.8
  }
]
```

Results are ordered by departure time ascending.

---

### `GET /admin/audit`

Query the audit trail. Every booking state transition is recorded with the action, previous/new status, metadata, and IP address.

**Auth required:** Yes (admin only)

**Query parameters:**

| Parameter    | Type           | Default | Constraints | Description                         |
|--------------|----------------|---------|-------------|-------------------------------------|
| `booking_id` | string or null | null    | --          | Filter by booking ID                |
| `limit`      | int            | 50      | max 200     | Number of results to return         |

**curl:**

```bash
# Recent audit entries
curl http://localhost:8000/admin/audit \
  -H "Authorization: Bearer <admin_access_token>"

# Audit trail for a specific booking
curl "http://localhost:8000/admin/audit?booking_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" \
  -H "Authorization: Bearer <admin_access_token>"
```

**Response: `200 OK`**

```json
[
  {
    "id": 1,
    "booking_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "action": "reserved",
    "previous_status": null,
    "new_status": "reserved",
    "metadata": {
      "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
      "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234"
    },
    "created_at": "2025-01-15T14:30:00+00:00"
  },
  {
    "id": 2,
    "booking_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "action": "confirmed",
    "previous_status": "reserved",
    "new_status": "confirmed",
    "metadata": {
      "gateway_ref": "MOCK-a1b2c3d4"
    },
    "created_at": "2025-01-15T14:31:00+00:00"
  }
]
```

**Audit actions recorded by the system:**

| Action              | Description                                      |
|---------------------|--------------------------------------------------|
| `reserved`          | Booking created with status `reserved`           |
| `payment_attempted` | Payment attempt initiated                        |
| `confirmed`         | Payment succeeded, booking confirmed             |
| `payment_failed`    | Payment failed, booking cancelled                |
| `refunded`          | Booking refunded                                 |
| `expired`           | Reservation expired (background cleanup)         |

---

## Demo Endpoints

These endpoints are for testing and demonstration purposes. They do not require authentication.

### `POST /demo/race-condition`

Simulate a race condition by spawning two concurrent booking attempts for the same seat. This demonstrates that the system's `SELECT FOR UPDATE` locking prevents double-booking.

**Auth required:** No

**Request body:**

| Field         | Type         | Required | Description                                           |
|---------------|--------------|----------|-------------------------------------------------------|
| `schedule_id` | UUID         | Yes      | Schedule to book                                      |
| `seat_id`     | UUID         | Yes      | Seat to contest                                       |
| `user_id_a`   | UUID or null | No       | First user (defaults to alice@example.com)             |
| `user_id_b`   | UUID or null | No       | Second user (defaults to bob@example.com)              |

**curl:**

```bash
curl -X POST http://localhost:8000/demo/race-condition \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "seat_id": "e5f6a7b8-c9d0-1234-efab-345678901234"
  }'
```

**Response: `200 OK`**

```json
{
  "attempt_a": {
    "user": "alice",
    "status_code": 201,
    "detail": "reserved",
    "elapsed_ms": 15.2
  },
  "attempt_b": {
    "user": "bob",
    "status_code": 409,
    "detail": "Seat already booked for this schedule",
    "elapsed_ms": 18.7
  },
  "winner": "alice"
}
```

One attempt succeeds with `201` and the other fails with `409`. The `winner` field indicates which user secured the seat.

**Error responses:**

| Status | Detail                                                         | Cause                                |
|--------|----------------------------------------------------------------|--------------------------------------|
| 400    | `Demo users not found. Provide user_id_a and user_id_b.`      | Default demo users not seeded        |

---

### `GET /demo/config`

Return the current mock payment gateway configuration.

**Auth required:** No

**curl:**

```bash
curl http://localhost:8000/demo/config
```

**Response: `200 OK`**

```json
{
  "payment_gateway": {
    "failure_rate": 0.0,
    "latency_ms": 500
  }
}
```

| Field          | Description                                              |
|----------------|----------------------------------------------------------|
| `failure_rate` | Probability (0.0 to 1.0) that a payment will fail        |
| `latency_ms`   | Simulated payment processing delay in milliseconds       |

---

### `PUT /demo/config`

Update the mock payment gateway configuration. Use this to simulate payment failures or slow processing.

**Auth required:** No

**Request body:**

| Field          | Type          | Required | Description                                |
|----------------|---------------|----------|--------------------------------------------|
| `failure_rate` | float or null | No       | Set failure probability (clamped to 0.0-1.0) |
| `latency_ms`   | int or null   | No       | Set processing latency in ms (min 0)        |

**curl:**

```bash
# Set 50% payment failure rate with 1-second latency
curl -X PUT http://localhost:8000/demo/config \
  -H "Content-Type: application/json" \
  -d '{
    "failure_rate": 0.5,
    "latency_ms": 1000
  }'
```

**Response: `200 OK`**

```json
{
  "payment_gateway": {
    "failure_rate": 0.5,
    "latency_ms": 1000
  }
}
```

---

## Rate Limiting

Rate limiting is enforced per-endpoint category when Redis is available. If Redis is unavailable, rate limiting is silently skipped.

The rate limiter uses a sliding window algorithm. Rate limit headers are included in all responses for rate-limited endpoints:

| Header                  | Description                              |
|-------------------------|------------------------------------------|
| `X-RateLimit-Limit`     | Maximum requests allowed in the window   |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset`     | Window duration in seconds               |
| `Retry-After`           | Seconds until the next request is allowed (only on 429) |

**Rate limit tiers:**

| Endpoint Category  | Limit                         | Key                |
|--------------------|-------------------------------|--------------------|
| Auth (`/auth/*`)   | 10 requests per 5 minutes     | Client IP address  |
| Booking (`POST /bookings`) | 5 requests per 60 seconds | User ID |
| Payment (`/bookings/*/pay`, `/bookings/*/refund`) | 3 requests per 60 seconds | User ID |

When a rate limit is exceeded, the API returns `429 Too Many Requests` with a detail message and `Retry-After` header.

---

## Booking Lifecycle

A booking follows this state machine:

```
                         payment succeeds
  (create) --> reserved -----------------> confirmed --> (refund) --> refunded
                  |
                  |  payment fails
                  +---> cancelled
                  |
                  |  5 min timeout
                  +---> cancelled (by cleanup)
```

**States:**

| Status      | Description                                     |
|-------------|-------------------------------------------------|
| `reserved`  | Seat is held; payment pending (5 min expiry)     |
| `confirmed` | Payment succeeded; booking is finalized          |
| `cancelled` | Payment failed or reservation expired            |
| `refunded`  | Confirmed booking was refunded by the user       |

The background cleanup task runs periodically and cancels reservations that have passed their `expires_at` timestamp.
