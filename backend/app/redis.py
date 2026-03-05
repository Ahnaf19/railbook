from redis.asyncio import ConnectionPool, Redis

from app.config import settings

pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True, max_connections=20)


def get_redis() -> Redis:
    """Get a Redis client backed by a shared connection pool."""
    return Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    await pool.aclose()
