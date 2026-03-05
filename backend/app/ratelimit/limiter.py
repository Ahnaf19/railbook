import time
from dataclasses import dataclass

from loguru import logger
from redis.asyncio import Redis


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int = 0
    retry_after: int = 0


class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        try:
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            _, _, count, _ = await pipe.execute()

            if count > limit:
                return RateLimitResult(allowed=False, remaining=0, retry_after=window_seconds)
            return RateLimitResult(allowed=True, remaining=limit - count)
        except Exception:
            logger.warning("Redis unavailable for rate limiting, allowing request")
            return RateLimitResult(allowed=True, remaining=limit)
