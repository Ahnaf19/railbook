from fastapi import Depends, HTTPException, Request, Response, status

from app.auth.dependencies import get_current_user
from app.models import User
from app.ratelimit.limiter import RateLimiter


def _get_limiter() -> RateLimiter | None:
    try:
        from app.redis import get_redis

        return RateLimiter(get_redis())
    except Exception:
        return None


async def rate_limit_booking(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
):
    """5 requests per 60 seconds per user for booking endpoints."""
    limiter = _get_limiter()
    if not limiter:
        return
    result = await limiter.check(f"rl:booking:{user.id}", limit=5, window_seconds=60)
    response.headers["X-RateLimit-Limit"] = "5"
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = "60"
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many booking requests",
            headers={
                "X-RateLimit-Limit": "5",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "60",
                "Retry-After": str(result.retry_after),
            },
        )


async def rate_limit_payment(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
):
    """3 requests per 60 seconds per user for payment endpoints."""
    limiter = _get_limiter()
    if not limiter:
        return
    result = await limiter.check(f"rl:payment:{user.id}", limit=3, window_seconds=60)
    response.headers["X-RateLimit-Limit"] = "3"
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = "60"
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many payment requests",
            headers={
                "X-RateLimit-Limit": "3",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "60",
                "Retry-After": str(result.retry_after),
            },
        )


async def rate_limit_auth(request: Request, response: Response):
    """10 requests per 5 minutes per IP for auth endpoints."""
    limiter = _get_limiter()
    if not limiter:
        return
    ip = request.client.host if request.client else "unknown"
    result = await limiter.check(f"rl:auth:{ip}", limit=10, window_seconds=300)
    response.headers["X-RateLimit-Limit"] = "10"
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = "300"
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many auth requests",
        )
