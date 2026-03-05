# RailBook Deployment Guide

This guide covers deploying RailBook using Docker Compose, configuring environment variables, and production hardening.

---

## Table of Contents

- [Docker Compose Setup](#docker-compose-setup)
- [Environment Variables](#environment-variables)
- [Production Considerations](#production-considerations)

---

## Docker Compose Setup

The project includes a `docker-compose.yml` at the repository root that defines four services:

| Service    | Image                | Port  | Description                              |
|------------|----------------------|-------|------------------------------------------|
| `postgres` | postgres:16-alpine   | 5432  | PostgreSQL database                      |
| `redis`    | redis:7-alpine       | 6379  | Redis for rate limiting and seat caching |
| `backend`  | Custom (Python 3.11) | 8000  | FastAPI application                      |
| `frontend` | Custom (Node 20 + Nginx) | 3000 | React SPA served by Nginx             |

### Starting all services

```bash
cd /Users/ahnaftanjid/Documents/railbook
docker-compose up --build -d
```

The `--build` flag ensures images are rebuilt with the latest code. The `-d` flag runs containers in the background.

### Service dependencies

The startup order is enforced through `depends_on` with health checks:
1. `postgres` starts first (healthcheck: `pg_isready`)
2. `redis` starts in parallel with postgres (healthcheck: `redis-cli ping`)
3. `backend` starts after both postgres and redis are healthy
4. `frontend` starts after backend is available

### Verifying deployment

```bash
# Check all containers are running
docker-compose ps

# Check backend health
curl http://localhost:8000/health

# Check logs
docker-compose logs backend
docker-compose logs postgres
```

### Stopping services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

### Data persistence

PostgreSQL data is persisted in a named Docker volume `pgdata`. This volume survives `docker-compose down` but is removed with `docker-compose down -v`.

Redis data is not persisted (no volume mount). Rate limit counters and seat availability caches are ephemeral by design.

---

## Environment Variables

All configuration is managed through environment variables, loaded by Pydantic Settings (with `.env` file support).

### Backend environment variables

| Variable                          | Default                                                              | Description                                    |
|-----------------------------------|----------------------------------------------------------------------|------------------------------------------------|
| `DATABASE_URL`                    | `postgresql+asyncpg://railbook:railbook_secret@localhost:5432/railbook` | PostgreSQL connection string (asyncpg driver)  |
| `REDIS_URL`                       | `redis://localhost:6379/0`                                           | Redis connection string                        |
| `JWT_SECRET`                      | `change-me-in-production-use-a-long-random-string`                   | Secret key for JWT signing (HS256)             |
| `JWT_ALGORITHM`                   | `HS256`                                                              | JWT signing algorithm                          |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15`                                                                 | Access token lifetime in minutes               |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`   | `7`                                                                  | Refresh token lifetime in days                 |
| `APP_ENV`                         | `development`                                                        | Environment name                               |
| `APP_DEBUG`                       | `True`                                                               | Enables SQLAlchemy query echo when True        |

### Docker Compose environment

The `docker-compose.yml` sets these for the backend service:

```yaml
environment:
  DATABASE_URL: postgresql+asyncpg://railbook:railbook_secret@postgres:5432/railbook
  REDIS_URL: redis://redis:6379/0
  JWT_SECRET: change-me-in-production-use-a-long-random-string
  APP_ENV: development
```

Note that within Docker Compose, hostnames use service names (`postgres`, `redis`) rather than `localhost`.

### PostgreSQL environment

| Variable            | Value             | Description          |
|---------------------|-------------------|----------------------|
| `POSTGRES_USER`     | `railbook`        | Database user        |
| `POSTGRES_PASSWORD` | `railbook_secret` | Database password    |
| `POSTGRES_DB`       | `railbook`        | Database name        |

### Using a .env file

For local development, create a `.env` file in `/Users/ahnaftanjid/Documents/railbook/backend/`:

```bash
DATABASE_URL=postgresql+asyncpg://railbook:railbook_secret@localhost:5432/railbook
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-here
APP_ENV=development
APP_DEBUG=True
```

Pydantic Settings automatically loads this file. The `extra = "ignore"` setting means unknown variables are silently ignored.

---

## Production Considerations

### 1. Change the JWT secret

The default `JWT_SECRET` is a placeholder. In production, generate a strong random secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Set this as the `JWT_SECRET` environment variable. All existing tokens become invalid when the secret changes.

### 2. Change database credentials

Replace the default PostgreSQL credentials (`railbook` / `railbook_secret`) with strong, unique values. Update both the `postgres` service environment and the `DATABASE_URL` in the backend.

### 3. Disable debug mode

Set `APP_DEBUG=False` in production. When debug mode is enabled, SQLAlchemy echoes all SQL queries to stdout, which impacts performance and may log sensitive data.

### 4. CORS configuration

The backend currently allows origins `http://localhost:3000` and `http://localhost:5173`. For production, update the CORS middleware in `app/main.py` to allow only your production domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. HTTPS termination

The application does not handle TLS itself. Place a reverse proxy (Nginx, Caddy, or a cloud load balancer) in front of the backend to terminate HTTPS.

### 6. Database connection pooling

The default pool settings (`pool_size=10`, `max_overflow=20`) support up to 30 concurrent database connections. Adjust these in `app/database.py` based on your PostgreSQL `max_connections` setting and expected concurrency:

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,       # Base connections
    max_overflow=40,    # Burst connections
    pool_pre_ping=True, # Validate stale connections
    pool_recycle=300,   # Recycle every 5 minutes
)
```

### 7. Redis persistence

Redis is used for rate limiting and seat availability caching. Both are ephemeral and rebuild automatically. No Redis persistence configuration is needed. If Redis goes down, the application continues to function -- rate limiting is disabled and seat queries fall back to the database.

### 8. Run database migrations

Migrations are not run automatically in the Docker container. Run them before or after deploying a new version:

```bash
docker-compose exec backend uv run alembic upgrade head
```

The seed data, however, runs automatically on application startup via the lifespan handler. It is idempotent and skips if data already exists.

### 9. Uvicorn workers

The default Docker configuration runs a single Uvicorn worker. For production, consider using multiple workers or running behind Gunicorn with Uvicorn workers:

```dockerfile
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Note: With multiple workers, the in-memory mock payment gateway state is not shared across workers. For a real deployment, replace the mock gateway with an actual payment provider integration.

### 10. Logging

The application uses [loguru](https://github.com/Delgan/loguru) for structured logging. In production, consider:
- Configuring log output to JSON format for log aggregation
- Setting appropriate log levels
- Shipping logs to a centralized service (ELK, Datadog, etc.)

### 11. Health checks

The `/health` endpoint returns `{"status": "ok"}` and can be used by load balancers, container orchestrators, or monitoring services. It does not currently check database connectivity at request time (only at startup).

### 12. Seed data in production

The seed data includes demo users with known passwords (`admin123`, `password123`). In production:
- Either modify `app/seed.py` to skip demo users
- Or change demo user passwords after initial deployment
- Or use a separate seed script for production that only creates the admin account with a secure password

### 13. Rate limiting in production

Rate limit thresholds are configured in `app/ratelimit/dependencies.py`:

| Category | Limit | Window |
|----------|-------|--------|
| Auth     | 10 requests | 5 minutes |
| Booking  | 5 requests  | 60 seconds |
| Payment  | 3 requests  | 60 seconds |

Adjust these values based on your expected traffic patterns. The rate limiter keys are:
- Auth: keyed by client IP (`rl:auth:{ip}`)
- Booking: keyed by user ID (`rl:booking:{user_id}`)
- Payment: keyed by user ID (`rl:payment:{user_id}`)

### 14. Monitoring the reservation cleanup

The background cleanup task runs continuously and cancels expired reservations (those past their 5-minute `expires_at` window). Monitor logs for cleanup activity. If the cleanup task fails, expired reservations will remain in `reserved` status and block those seats until manually resolved.

### Example production docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "127.0.0.1:5432:5432"  # Bind to localhost only
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "127.0.0.1:6379:6379"  # Bind to localhost only
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  backend:
    build: ./backend
    ports:
      - "127.0.0.1:8000:8000"  # Behind reverse proxy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: ${JWT_SECRET}
      APP_ENV: production
      APP_DEBUG: "False"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "127.0.0.1:3000:80"  # Behind reverse proxy
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  pgdata:
```

Use this with a `.env` file at the repository root:

```bash
POSTGRES_USER=railbook_prod
POSTGRES_PASSWORD=<strong-random-password>
POSTGRES_DB=railbook
JWT_SECRET=<strong-random-secret>
```
