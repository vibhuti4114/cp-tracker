"""
Redis connection pool and caching utilities.

Responsibilities:
- Async Redis connection via redis-py
- get/set/delete cache helpers with TTL
- Rate limiting (sliding window counter)
- Session / token blacklist
- Pub/Sub helpers (optional, for future real-time features)
"""

import json
import logging
from typing import Any, Optional
from functools import wraps

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_redis_pool: Optional[Redis] = None


async def get_redis() -> Redis:
    """Return (or lazily create) the shared async Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection closed.")


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

class CacheManager:
    """
    High-level cache operations built on top of the Redis pool.

    Key naming convention:
        cp_tracker:<namespace>:<identifier>
    """

    PREFIX = "cp_tracker"

    def __init__(self, redis: Redis):
        self._r = redis

    def _key(self, namespace: str, identifier: str) -> str:
        return f"{self.PREFIX}:{namespace}:{identifier}"

    # --- Generic -----------------------------------------------------------

    async def get(self, namespace: str, identifier: str) -> Optional[Any]:
        """Return deserialized value or None on miss."""
        raw = await self._r.get(self._key(namespace, identifier))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def set(
        self,
        namespace: str,
        identifier: str,
        value: Any,
        ttl: int = settings.REDIS_CACHE_TTL,
    ) -> None:
        """Serialize and store value with TTL (seconds)."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await self._r.setex(self._key(namespace, identifier), ttl, serialized)

    async def delete(self, namespace: str, identifier: str) -> int:
        """Remove a key. Returns number of keys deleted."""
        return await self._r.delete(self._key(namespace, identifier))

    async def exists(self, namespace: str, identifier: str) -> bool:
        return bool(await self._r.exists(self._key(namespace, identifier)))

    async def flush_namespace(self, namespace: str) -> int:
        """Delete all keys under a namespace (use carefully)."""
        pattern = f"{self.PREFIX}:{namespace}:*"
        keys = await self._r.keys(pattern)
        if keys:
            return await self._r.delete(*keys)
        return 0

    # --- Platform stats cache shorthand ------------------------------------

    async def get_platform_stats(self, user_id: int, platform: str) -> Optional[dict]:
        return await self.get("stats", f"{user_id}:{platform}")

    async def set_platform_stats(
        self, user_id: int, platform: str, data: dict, ttl: int = settings.REDIS_CACHE_TTL
    ) -> None:
        await self.set("stats", f"{user_id}:{platform}", data, ttl)

    async def invalidate_user_stats(self, user_id: int) -> None:
        """Bust all cached stats for a user across all platforms."""
        await self.flush_namespace(f"stats:{user_id}")
        # Also bust aggregated analytics
        await self.delete("analytics", str(user_id))

    # --- Token blacklist (logout / token revocation) -----------------------

    async def blacklist_token(self, jti: str, ttl: int) -> None:
        """Add a JWT ID to the blacklist until it would have expired."""
        await self.set("blacklist", jti, "1", ttl=ttl)

    async def is_token_blacklisted(self, jti: str) -> bool:
        return await self.exists("blacklist", jti)

    # --- Rate limiting (fixed window counter) ------------------------------

    async def check_rate_limit(
        self,
        identifier: str,
        max_requests: int = settings.REDIS_RATE_LIMIT_MAX,
        window: int = settings.REDIS_RATE_LIMIT_TTL,
    ) -> tuple[bool, int, int]:
        """
        Increment a fixed-window counter for `identifier`.

        Returns:
            (allowed, current_count, ttl_remaining)
        """
        key = self._key("ratelimit", identifier)
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        results = await pipe.execute()

        count: int = results[0]
        ttl: int = results[1]

        if ttl == -1:
            # Key exists but has no expiry — set it now (race-safe)
            await self._r.expire(key, window)
            ttl = window

        allowed = count <= max_requests
        return allowed, count, ttl

    # --- Leaderboard / Sorted Sets ----------------------------------------

    async def update_leaderboard(self, board: str, username: str, score: float) -> None:
        key = self._key("leaderboard", board)
        await self._r.zadd(key, {username: score})

    async def get_leaderboard(
        self, board: str, top_n: int = 10, with_scores: bool = True
    ) -> list:
        key = self._key("leaderboard", board)
        return await self._r.zrevrange(key, 0, top_n - 1, withscores=with_scores)


# ---------------------------------------------------------------------------
# Dependency for FastAPI
# ---------------------------------------------------------------------------

async def get_cache() -> CacheManager:
    """FastAPI dependency that yields a CacheManager instance."""
    redis = await get_redis()
    return CacheManager(redis)
