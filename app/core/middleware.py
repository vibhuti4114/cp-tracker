"""
Redis-backed rate limiting middleware.
Uses a fixed-window counter keyed on the client IP.
"""

import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.redis import get_redis, CacheManager
from app.core.config import settings

logger = logging.getLogger(__name__)

# Endpoints that get a tighter limit (e.g. login brute-force protection)
STRICT_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}
STRICT_MAX = 10   # per window


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Resolve client IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (
            request.client.host if request.client else "unknown"
        )

        path = request.url.path
        is_strict = path in STRICT_PATHS
        max_requests = STRICT_MAX if is_strict else settings.REDIS_RATE_LIMIT_MAX

        try:
            redis = await get_redis()
            cache = CacheManager(redis)
            identifier = f"{client_ip}:{'strict' if is_strict else 'global'}"

            allowed, count, ttl = await cache.check_rate_limit(
                identifier,
                max_requests=max_requests,
                window=settings.REDIS_RATE_LIMIT_TTL,
            )
        except Exception as exc:
            logger.error("Rate limit check failed: %s — allowing request.", exc)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": ttl,
                },
                headers={
                    "Retry-After": str(ttl),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(ttl),
                },
            )

        response: Response = await call_next(request)
        remaining = max(0, max_requests - count)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(ttl)
        return response
