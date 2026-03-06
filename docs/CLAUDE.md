# Documentation

## File Map

| File | What it covers | Update when |
|------|---------------|-------------|
| `architecture/ARCHITECTURE.md` | System design, component interactions | Adding new services/modules |
| `architecture/CONCURRENCY.md` | 5 concurrency problems + solutions with code | Changing locking/transaction logic |
| `architecture/DATABASE.md` | All 8 tables, columns, constraints, indexes | Changing models or adding migrations |
| `api/API_REFERENCE.md` | Every endpoint, request/response, curl examples | Adding/changing endpoints |
| `api/ERROR_CODES.md` | All HTTP error codes and troubleshooting | Adding new error responses |
| `guides/DEVELOPER_GUIDE.md` | Setup, structure, conventions, testing | Changing dev workflow |
| `guides/USER_GUIDE.md` | End-user walkthrough | Changing UI features |
| `guides/DEPLOYMENT_GUIDE.md` | Docker, env vars, production | Changing deployment config |
| `guides/LOAD_TESTING_GUIDE.md` | Locust how-to, integrity checks | Changing load test setup |
| `postman/railbook.postman_collection.json` | Importable Postman collection | Adding/changing endpoints |
| `postman/railbook.local.postman_environment.json` | Local env vars for Postman | Changing default URLs/vars |

## Postman Collection Structure

Organized by folder: Health, Auth, Trains, Bookings, Demo, Admin. Auth endpoints have test scripts that auto-save tokens to collection variables. List Trains auto-saves first trainId.

## Conventions

- Use concrete examples (real endpoint paths, actual payloads)
- Keep curl examples copy-pasteable
- Cross-link between docs where relevant
- Postman collection variables: baseUrl, accessToken, refreshToken, bookingId, scheduleId, seatId, trainId
