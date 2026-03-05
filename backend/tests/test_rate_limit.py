import uuid
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ratelimit.dependencies import rate_limit_auth, rate_limit_booking, rate_limit_payment
from app.ratelimit.limiter import RateLimiter, RateLimitResult


def _make_limiter(fake_check):
    limiter = RateLimiter.__new__(RateLimiter)
    limiter.check = fake_check
    return limiter


async def _make_rl_client(session_factory):
    """Client with rate limiting enabled (overrides removed)."""

    async def override_get_db():
        async with session_factory() as session:
            yield session

    from app.database import get_db

    app.dependency_overrides[get_db] = override_get_db
    # Remove rate limit overrides so real dependencies run
    app.dependency_overrides.pop(rate_limit_auth, None)
    app.dependency_overrides.pop(rate_limit_booking, None)
    app.dependency_overrides.pop(rate_limit_payment, None)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _register_user(client):
    email = f"rl-{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "testpass123", "full_name": "Test User"},
    )
    return resp.json()["access_token"]


async def test_rate_limit_blocks_after_threshold(session_factory):
    """Booking rate limit blocks after exceeding limit."""
    call_count = 0

    async def fake_check(key, limit, window_seconds):
        nonlocal call_count
        call_count += 1
        if call_count > 5:
            return RateLimitResult(allowed=False, remaining=0, retry_after=60)
        return RateLimitResult(allowed=True, remaining=limit - call_count)

    limiter = _make_limiter(fake_check)

    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=limiter):
            token = await _register_user(client)
            headers = {"Authorization": f"Bearer {token}"}

            for _ in range(5):
                await client.post(
                    "/bookings",
                    json={
                        "schedule_id": str(uuid.uuid4()),
                        "seat_id": str(uuid.uuid4()),
                        "idempotency_key": str(uuid.uuid4()),
                    },
                    headers=headers,
                )

            resp = await client.post(
                "/bookings",
                json={
                    "schedule_id": str(uuid.uuid4()),
                    "seat_id": str(uuid.uuid4()),
                    "idempotency_key": str(uuid.uuid4()),
                },
                headers=headers,
            )
            assert resp.status_code == 429
            assert "Too many booking requests" in resp.json()["detail"]


async def test_rate_limit_429_headers(session_factory):
    """429 response should include rate limit and Retry-After headers."""

    async def fake_check(key, limit, window_seconds):
        # Allow auth requests, block booking requests
        if key.startswith("rl:auth:"):
            return RateLimitResult(allowed=True, remaining=limit - 1)
        return RateLimitResult(allowed=False, remaining=0, retry_after=60)

    limiter = _make_limiter(fake_check)

    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=limiter):
            token = await _register_user(client)
            headers = {"Authorization": f"Bearer {token}"}

            resp = await client.post(
                "/bookings",
                json={
                    "schedule_id": str(uuid.uuid4()),
                    "seat_id": str(uuid.uuid4()),
                    "idempotency_key": str(uuid.uuid4()),
                },
                headers=headers,
            )
            assert resp.status_code == 429
            assert resp.headers["X-RateLimit-Limit"] == "5"
            assert resp.headers["X-RateLimit-Remaining"] == "0"
            assert resp.headers["X-RateLimit-Reset"] == "60"
            assert resp.headers["Retry-After"] == "60"


async def test_rate_limit_separate_per_user(session_factory):
    """Each user should have independent rate limit keys."""
    user_keys = set()

    async def fake_check(key, limit, window_seconds):
        user_keys.add(key)
        return RateLimitResult(allowed=True, remaining=limit - 1)

    limiter = _make_limiter(fake_check)

    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=limiter):
            token_a = await _register_user(client)
            token_b = await _register_user(client)

            await client.post(
                "/bookings",
                json={
                    "schedule_id": str(uuid.uuid4()),
                    "seat_id": str(uuid.uuid4()),
                    "idempotency_key": str(uuid.uuid4()),
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            await client.post(
                "/bookings",
                json={
                    "schedule_id": str(uuid.uuid4()),
                    "seat_id": str(uuid.uuid4()),
                    "idempotency_key": str(uuid.uuid4()),
                },
                headers={"Authorization": f"Bearer {token_b}"},
            )

    booking_keys = [k for k in user_keys if k.startswith("rl:booking:")]
    assert len(booking_keys) == 2, f"Expected 2 different booking keys, got {booking_keys}"


async def test_auth_rate_limit_by_ip(session_factory):
    """Auth endpoints should rate limit by IP, not user."""
    seen_keys = set()

    async def fake_check(key, limit, window_seconds):
        seen_keys.add(key)
        return RateLimitResult(allowed=True, remaining=limit - 1)

    limiter = _make_limiter(fake_check)

    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=limiter):
            await client.post(
                "/auth/login",
                json={"email": "alice@example.com", "password": "password123"},
            )

    auth_keys = [k for k in seen_keys if k.startswith("rl:auth:")]
    assert len(auth_keys) == 1
    assert "rl:auth:" in auth_keys[0]


async def test_graceful_degradation_redis_down(session_factory):
    """When Redis is unavailable, requests should pass through."""
    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=None):
            token = await _register_user(client)
            resp = await client.post(
                "/bookings",
                json={
                    "schedule_id": str(uuid.uuid4()),
                    "seat_id": str(uuid.uuid4()),
                    "idempotency_key": str(uuid.uuid4()),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code != 429


async def test_payment_rate_limit_stricter(session_factory):
    """Payment rate limit should be 3 req/60s (stricter than booking's 5)."""
    limits_seen = {}

    async def fake_check(key, limit, window_seconds):
        prefix = key.split(":")[1]
        limits_seen[prefix] = limit
        return RateLimitResult(allowed=True, remaining=limit - 1)

    limiter = _make_limiter(fake_check)

    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=limiter):
            token = await _register_user(client)
            headers = {"Authorization": f"Bearer {token}"}

            await client.post(
                "/bookings",
                json={
                    "schedule_id": str(uuid.uuid4()),
                    "seat_id": str(uuid.uuid4()),
                    "idempotency_key": str(uuid.uuid4()),
                },
                headers=headers,
            )
            await client.post(
                f"/bookings/{uuid.uuid4()}/pay",
                json={"idempotency_key": str(uuid.uuid4())},
                headers=headers,
            )

    assert limits_seen.get("booking") == 5
    assert limits_seen.get("payment") == 3


async def test_auth_rate_limit_blocks(session_factory):
    """Auth rate limit blocks after exceeding threshold."""

    async def fake_check(key, limit, window_seconds):
        return RateLimitResult(allowed=False, remaining=0, retry_after=300)

    limiter = _make_limiter(fake_check)

    async with await _make_rl_client(session_factory) as client:
        with patch("app.ratelimit.dependencies._get_limiter", return_value=limiter):
            resp = await client.post(
                "/auth/login",
                json={"email": "test@test.com", "password": "password"},
            )
            assert resp.status_code == 429
            assert "Too many auth requests" in resp.json()["detail"]
