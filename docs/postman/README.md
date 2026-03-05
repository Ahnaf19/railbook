# Postman Collection

Pre-built Postman collection and environment for testing the RailBook API interactively. Includes automatic token handling so you can run requests in sequence without manually copying JWTs.

## Files

| File | Description |
|---|---|
| `railbook.postman_collection.json` | Full API collection: 15 requests across 6 folders (Health, Auth, Trains, Bookings, Demo, Admin) |
| `railbook.local.postman_environment.json` | Local environment with `baseUrl` set to `http://localhost:8000` |

## Import into Postman

1. Open Postman and click **Import** (top left)
2. Drag both JSON files into the import dialog, or click **Upload Files** and select them
3. The collection "RailBook API" and environment "RailBook Local" will appear
4. Select "RailBook Local" from the environment dropdown (top right)

## Variables

The collection uses these variables, automatically populated by test scripts:

| Variable | Auto-set by | Description |
|---|---|---|
| `baseUrl` | Environment | API base URL (`http://localhost:8000`) |
| `accessToken` | Register / Login | JWT access token, used in Bearer auth |
| `refreshToken` | Register / Login / Refresh | JWT refresh token |
| `trainId` | List Trains | First train's UUID |
| `scheduleId` | Get Schedules | First schedule's UUID |
| `seatId` | Seat Availability | First available seat's UUID |
| `bookingId` | Create Booking | Newly created booking's UUID |

## Recommended Flow

Run these requests in order for a complete booking lifecycle:

1. **Auth > Login** -- logs in as `alice@example.com` / `password123` (seeded demo user). Automatically saves `accessToken` and `refreshToken`.
2. **Trains > List Trains** -- fetches all trains, saves `trainId`.
3. **Trains > Get Schedules** -- fetches schedules for the saved train, saves `scheduleId`.
4. **Trains > Seat Availability** -- fetches the seat map, saves `seatId` (first available seat).
5. **Bookings > Create Booking** -- reserves the seat using `{{scheduleId}}`, `{{seatId}}`, and a generated `{{$guid}}` for idempotency. Saves `bookingId`.
6. **Bookings > Pay Booking** -- pays for the reservation, confirming the booking.
7. **Bookings > Get Booking** -- view the confirmed booking details.
8. **Bookings > Refund Booking** -- cancels and refunds the confirmed booking.

## Auto-Token Handling

The Register, Login, and Refresh Token requests have **test scripts** that automatically extract `access_token` and `refresh_token` from the response and store them as collection variables. All subsequent requests use Bearer auth with `{{accessToken}}`, so you never need to copy tokens manually.

Similarly, List Trains, Get Schedules, and Seat Availability extract IDs from responses so downstream requests (Create Booking, Pay) can reference them automatically.

## Demo & Admin Requests

- **Demo > Race Condition** -- fires a concurrent booking simulation on the server side. Requires `scheduleId` and `seatId` to be set.
- **Demo > Get/Update Config** -- view or change the mock payment gateway settings (failure rate, latency).
- **Admin > Stats/Bookings/Occupancy/Audit** -- admin dashboard endpoints (require an admin user's token).
