"""Tests for Redis cache manager and rate limiting logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.redis import CacheManager


# ---------------------------------------------------------------------------
# CacheManager unit tests (fully mocked Redis)
# ---------------------------------------------------------------------------

def make_cache(mock_redis):
    return CacheManager(mock_redis)


@pytest.mark.asyncio
async def test_cache_set_and_get():
    redis = MagicMock()
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value='{"score": 1800}')
    cache = make_cache(redis)

    await cache.set("stats", "1:codeforces", {"score": 1800})
    redis.setex.assert_called_once()

    result = await cache.get("stats", "1:codeforces")
    assert result == {"score": 1800}


@pytest.mark.asyncio
async def test_cache_miss_returns_none():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    cache = make_cache(redis)

    result = await cache.get("stats", "99:leetcode")
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete():
    redis = MagicMock()
    redis.delete = AsyncMock(return_value=1)
    cache = make_cache(redis)

    deleted = await cache.delete("analytics", "42")
    assert deleted == 1
    redis.delete.assert_called_once_with("cp_tracker:analytics:42")


@pytest.mark.asyncio
async def test_token_blacklist():
    redis = MagicMock()
    redis.setex = AsyncMock()
    redis.exists = AsyncMock(return_value=True)
    cache = make_cache(redis)

    await cache.blacklist_token("some-jti", ttl=1800)
    redis.setex.assert_called_once()

    is_blacklisted = await cache.is_token_blacklisted("some-jti")
    assert is_blacklisted is True


@pytest.mark.asyncio
async def test_rate_limit_allowed():
    redis = MagicMock()
    pipe = MagicMock()
    pipe.incr = MagicMock()
    pipe.ttl = MagicMock()
    pipe.execute = AsyncMock(return_value=[5, 55])  # count=5, ttl=55s
    redis.pipeline = MagicMock(return_value=pipe)
    redis.expire = AsyncMock()
    cache = make_cache(redis)

    allowed, count, ttl = await cache.check_rate_limit("127.0.0.1", max_requests=100, window=60)
    assert allowed is True
    assert count == 5


@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    redis = MagicMock()
    pipe = MagicMock()
    pipe.incr = MagicMock()
    pipe.ttl = MagicMock()
    pipe.execute = AsyncMock(return_value=[101, 30])  # exceeded
    redis.pipeline = MagicMock(return_value=pipe)
    cache = make_cache(redis)

    allowed, count, ttl = await cache.check_rate_limit("127.0.0.1", max_requests=100, window=60)
    assert allowed is False
    assert count == 101


@pytest.mark.asyncio
async def test_rate_limit_sets_ttl_when_missing():
    """When TTL == -1 (key has no expiry), expire should be called."""
    redis = MagicMock()
    pipe = MagicMock()
    pipe.incr = MagicMock()
    pipe.ttl = MagicMock()
    pipe.execute = AsyncMock(return_value=[1, -1])
    redis.pipeline = MagicMock(return_value=pipe)
    redis.expire = AsyncMock()
    cache = make_cache(redis)

    allowed, count, ttl = await cache.check_rate_limit("new-ip", max_requests=100, window=60)
    redis.expire.assert_called_once()
    assert ttl == 60


@pytest.mark.asyncio
async def test_leaderboard_update_and_fetch():
    redis = MagicMock()
    redis.zadd = AsyncMock()
    redis.zrevrange = AsyncMock(return_value=[("alice", 1500.0), ("bob", 1400.0)])
    cache = make_cache(redis)

    await cache.update_leaderboard("codeforces_rating", "alice", 1500.0)
    redis.zadd.assert_called_once()

    board = await cache.get_leaderboard("codeforces_rating", top_n=2)
    assert board[0] == ("alice", 1500.0)


@pytest.mark.asyncio
async def test_platform_stats_cache(mock_cache):
    """Ensure set/get platform stats delegates correctly."""
    mock_cache.get_platform_stats = AsyncMock(return_value=None)
    mock_cache.set_platform_stats = AsyncMock()

    result = await mock_cache.get_platform_stats(1, "codeforces")
    assert result is None

    await mock_cache.set_platform_stats(1, "codeforces", {"rating": 1800})
    mock_cache.set_platform_stats.assert_called_once_with(1, "codeforces", {"rating": 1800})


@pytest.mark.asyncio
async def test_invalidate_user_stats(mock_cache):
    await mock_cache.invalidate_user_stats(1)
    mock_cache.invalidate_user_stats.assert_called_once_with(1)
