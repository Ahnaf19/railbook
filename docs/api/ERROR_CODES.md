# RailBook API Error Codes

All error responses use a consistent JSON format:

```json
{
  "detail": "Human-readable error message"
}
```

For validation errors (422), FastAPI returns a structured list of field-level errors:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## HTTP Status Codes

### 400 Bad Request

The request is syntactically valid but semantically incorrect. The server understood the request but cannot process it due to business logic constraints.

**When it occurs:**

| Endpoint                        | Detail Message                              | Cause                                                     |
|---------------------------------|---------------------------------------------|------------------------------------------------------------|
| `POST /bookings/{id}/pay`       | `Booking is <status>, not reserved`         | Attempting to pay a booking that is not in `reserved` state |
| `POST /bookings/{id}/pay`       | `Reservation expired`                       | The 5-minute reservation window has elapsed                |
| `POST /bookings/{id}/refund`    | `Booking is <status>, not confirmed`        | Attempting to refund a booking that is not `confirmed`      |
| `POST /bookings/{id}/refund`    | `Cannot refund within 1 hour of departure`  | The train departs in less than 1 hour                      |
| `POST /demo/race-condition`     | `Demo users not found...`                   | Seed data not loaded and no user IDs provided              |

**Client handling:**

Display the error message to the user. These errors indicate the action is not valid in the current state. The client should refresh the booking status before retrying. For expired reservations, the user must create a new booking.

---

### 401 Unauthorized

Authentication is required but was not provided, or the provided credentials/token are invalid.

**When it occurs:**

| Endpoint               | Detail Message                           | Cause                                         |
|------------------------|------------------------------------------|------------------------------------------------|
| `POST /auth/login`     | `Invalid credentials`                    | Wrong email or password                        |
| `POST /auth/refresh`   | `Invalid token type`                     | Token provided is not a refresh token          |
| `POST /auth/refresh`   | `Invalid or expired refresh token`       | Refresh token is malformed, expired, or tampered |
| `POST /auth/refresh`   | `User not found`                         | User account was deleted after token issuance  |
| Any protected endpoint | `Invalid or expired token`               | Access token is missing, expired, or invalid   |
| Any protected endpoint | `Invalid token type`                     | A refresh token was used where an access token is expected |
| Any protected endpoint | `User not found`                         | User account associated with the token no longer exists |
| Any protected endpoint | `Not authenticated`                      | No `Authorization` header provided (FastAPI default for HTTPBearer) |

**Client handling:**

- For `Invalid credentials`: Prompt the user to check their email and password.
- For token errors: Attempt to refresh the token using `POST /auth/refresh`. If refresh also fails, redirect to login.
- Implement automatic token refresh in your HTTP client when a 401 is received on a protected endpoint.

**Example token refresh flow:**

```
1. API call returns 401
2. Call POST /auth/refresh with stored refresh_token
3. If refresh succeeds: store new tokens, retry original request
4. If refresh fails: redirect to login
```

---

### 403 Forbidden

The user is authenticated but does not have permission to perform the requested action.

**When it occurs:**

| Endpoint                      | Detail Message           | Cause                                           |
|-------------------------------|--------------------------|--------------------------------------------------|
| `POST /bookings/{id}/pay`     | `Not your booking`       | User attempted to pay for another user's booking |
| `POST /bookings/{id}/refund`  | `Not your booking`       | User attempted to refund another user's booking  |
| Any `/admin/*` endpoint       | `Admin access required`  | Non-admin user tried to access admin endpoints   |

**Client handling:**

- For `Not your booking`: This is a logic error in the client. Ensure booking IDs correspond to the authenticated user's bookings.
- For `Admin access required`: Hide admin UI elements from non-admin users. This error should not appear in normal usage.

---

### 404 Not Found

The requested resource does not exist.

**When it occurs:**

| Endpoint                                    | Detail Message         | Cause                             |
|---------------------------------------------|------------------------|-----------------------------------|
| `GET /trains/schedules/{schedule_id}/seats`  | `Schedule not found`   | No schedule with the given UUID   |
| `POST /bookings`                            | `Schedule not found`   | Invalid schedule_id in request    |
| `POST /bookings`                            | `Seat not found`       | Invalid seat_id in request        |
| `POST /bookings/{id}/pay`                   | `Booking not found`    | No booking with the given UUID    |
| `POST /bookings/{id}/refund`                | `Booking not found`    | No booking with the given UUID    |

**Client handling:**

- Verify that the IDs being sent are valid UUIDs obtained from previous API responses.
- If a previously valid resource returns 404, it may have been deleted or the ID may be incorrect. Refresh the parent listing.

---

### 409 Conflict

The request conflicts with the current state of a resource. Used exclusively for booking conflicts.

**When it occurs:**

| Endpoint            | Detail Message                            | Cause                                                              |
|---------------------|-------------------------------------------|--------------------------------------------------------------------|
| `POST /auth/register` | `Email already registered`             | A user with this email already exists                              |
| `POST /bookings`    | `Seat already booked for this schedule`   | Another user (or the same user) already holds a reservation or confirmation for this seat on this schedule |
| `POST /bookings`    | `You have an overlapping journey`         | The user already has an active booking (reserved or confirmed) whose schedule overlaps in time with the requested schedule |

**Client handling:**

- For `Seat already booked`: Refresh the seat availability map and let the user choose a different seat. This is expected behavior under high concurrency.
- For `You have an overlapping journey`: Inform the user they already have a booking during the same time window. They must cancel or refund the existing booking first.
- For `Email already registered`: Prompt the user to log in instead, or use a different email.

---

### 422 Unprocessable Entity

The request body failed validation. This is generated automatically by FastAPI/Pydantic when required fields are missing, types are wrong, or constraints are violated.

**When it occurs:**

Any endpoint that accepts a JSON request body, when:
- Required fields are missing
- Field types are incorrect (e.g., string where UUID is expected)
- UUID format is invalid

**Example response:**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "schedule_id"],
      "msg": "Field required",
      "input": {}
    },
    {
      "type": "uuid_parsing",
      "loc": ["body", "seat_id"],
      "msg": "Input should be a valid UUID",
      "input": "not-a-uuid"
    }
  ]
}
```

**Client handling:**

Parse the `detail` array to identify which fields failed validation. The `loc` field indicates the path to the problematic field. Display field-specific error messages in the form UI.

---

### 429 Too Many Requests

The client has exceeded the rate limit for this endpoint category.

**When it occurs:**

| Endpoint Category          | Limit                         | Detail Message                |
|----------------------------|-------------------------------|-------------------------------|
| `/auth/*`                  | 10 requests per 5 minutes (per IP)   | `Too many auth requests`      |
| `POST /bookings`           | 5 requests per 60 seconds (per user) | `Too many booking requests`   |
| `POST /bookings/*/pay`     | 3 requests per 60 seconds (per user) | `Too many payment requests`   |
| `POST /bookings/*/refund`  | 3 requests per 60 seconds (per user) | `Too many payment requests`   |

**Response headers (on 429):**

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 60
Retry-After: 23
```

**Client handling:**

1. Read the `Retry-After` header to determine how long to wait before retrying.
2. Implement exponential backoff for automated retries.
3. Show a user-friendly message: "Please wait before trying again."
4. Monitor `X-RateLimit-Remaining` on successful responses to preemptively throttle requests before hitting the limit.
5. Note: Rate limiting requires Redis. If Redis is unavailable, rate limits are not enforced.

**Example client-side implementation:**

```javascript
async function apiCall(url, options) {
  const response = await fetch(url, options);
  if (response.status === 429) {
    const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
    await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
    return apiCall(url, options); // Retry once
  }
  return response;
}
```

---

## Error Handling Best Practices

### For API Consumers

1. **Always check the HTTP status code first.** The `detail` message provides human-readable context but should not be parsed programmatically for control flow.

2. **Implement token refresh.** Access tokens expire every 15 minutes. Use the refresh token to obtain new tokens transparently.

3. **Use idempotency keys.** When creating bookings or processing payments, always generate a UUID v4 idempotency key and reuse it across retries. This prevents duplicate bookings even if the client is unsure whether a previous request succeeded.

4. **Handle 409 gracefully.** Seat conflicts are expected under concurrent usage. Design the UI to let users quickly select alternative seats.

5. **Respect rate limits.** Monitor the `X-RateLimit-Remaining` header and implement backoff strategies before hitting limits.

6. **Expect 422 for bad input.** Validate request bodies client-side to catch issues before sending, but always handle 422 as a fallback.
