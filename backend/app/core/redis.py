import logging
from typing import Optional
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_pool: Optional[aioredis.ConnectionPool] = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Return singleton Redis connection pool."""
    global redis_pool
    if redis_pool is None:
        redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
    return redis_pool


async def get_redis_client() -> Redis:
    """Provide an asynchronous Redis client instance."""
    pool = get_redis_pool()
    return aioredis.Redis(connection_pool=pool)


async def check_redis_health() -> bool:
    """Ping Redis to confirm connectivity."""
    try:
        client = await get_redis_client()
        pong = await client.ping()
        return bool(pong)
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False
