"""
CP Tracker API — FastAPI application factory.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.redis import get_redis, close_redis
from app.core.middleware import RateLimitMiddleware
from app.routers import auth, users, accounts, analytics, leaderboard

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up CP Tracker API…")

    # Warm up Redis
    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connected.")

    # Create tables (dev — use Alembic in production)
    if settings.DEBUG:
        await init_db()
        logger.info("Database tables ensured.")

    yield

    # Shutdown
    await close_redis()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Aggregates competitive programming stats across Codeforces, "
            "LeetCode, CodeChef, and AtCoder into a single unified API."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # --- Middleware ---------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)

    # --- Routers ------------------------------------------------------
    PREFIX = "/api/v1"
    app.include_router(auth.router,        prefix=PREFIX)
    app.include_router(users.router,       prefix=PREFIX)
    app.include_router(accounts.router,    prefix=PREFIX)
    app.include_router(analytics.router,   prefix=PREFIX)
    app.include_router(leaderboard.router, prefix=PREFIX)

    # --- Health check -------------------------------------------------
    @app.get("/health", tags=["Health"])
    async def health():
        try:
            redis = await get_redis()
            await redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
        return JSONResponse(
            content={
                "status": "ok" if redis_ok else "degraded",
                "version": settings.APP_VERSION,
                "redis": "ok" if redis_ok else "unavailable",
            }
        )

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
