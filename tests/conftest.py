"""
Shared pytest fixtures.
Uses SQLite in-memory DB and fully mocked Redis — no live services needed.
"""

import pytest
import pytest_asyncio
import sqlalchemy as sa
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.redis import get_cache, CacheManager
from app.core.database import get_db

# ---------------------------------------------------------------------------
# Separate SQLite-native metadata (BigInteger → Integer, Enum → String)
# so SQLite autoincrement works correctly.
# ---------------------------------------------------------------------------

class TestBase(DeclarativeBase):
    pass

def _build_sqlite_metadata():
    """Clone app metadata with SQLite-compatible column types."""
    from app.core.database import Base as AppBase
    from app.models import models  # register ORM classes

    new_meta = sa.MetaData()
    for table in AppBase.metadata.sorted_tables:
        cols = []
        for col in table.columns:
            t = col.type
            if isinstance(t, sa.BigInteger):
                t = sa.Integer()
            elif isinstance(t, sa.Enum):
                t = sa.String(64)
            cols.append(
                sa.Column(
                    col.name, t,
                    primary_key=col.primary_key,
                    autoincrement=col.autoincrement,
                    nullable=col.nullable,
                    unique=col.unique,
                    default=col.default,
                    server_default=col.server_default,
                )
            )
        # Include unique constraints (skip multi-col ones for simplicity)
        constraints = []
        for uc in table.constraints:
            if isinstance(uc, sa.UniqueConstraint) and len(uc.columns) > 1:
                constraints.append(
                    sa.UniqueConstraint(*[c.name for c in uc.columns], name=uc.name)
                )
        sa.Table(table.name, new_meta, *cols, *constraints)
    return new_meta

SQLITE_META = _build_sqlite_metadata()

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLITE_META.create_all)

    session = TestSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLITE_META.drop_all)


# ---------------------------------------------------------------------------
# Mock CacheManager
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cache():
    cache = MagicMock(spec=CacheManager)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.exists = AsyncMock(return_value=False)
    cache.blacklist_token = AsyncMock()
    cache.is_token_blacklisted = AsyncMock(return_value=False)
    cache.check_rate_limit = AsyncMock(return_value=(True, 1, 60))
    cache.get_platform_stats = AsyncMock(return_value=None)
    cache.set_platform_stats = AsyncMock()
    cache.invalidate_user_stats = AsyncMock()
    cache.update_leaderboard = AsyncMock()
    cache.get_leaderboard = AsyncMock(return_value=[])
    cache.flush_namespace = AsyncMock(return_value=0)
    return cache


# ---------------------------------------------------------------------------
# Test client with stub lifespan (no Redis ping on startup)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _stub_lifespan(app):
    yield


@pytest_asyncio.fixture
async def client(db_session, mock_cache):
    import app.main as main_module

    orig = main_module.lifespan
    main_module.lifespan = _stub_lifespan
    _app = main_module.create_app()
    main_module.lifespan = orig

    async def override_db():
        yield db_session

    async def override_cache():
        return mock_cache

    _app.dependency_overrides[get_db] = override_db
    _app.dependency_overrides[get_cache] = override_cache

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    _app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth header helper
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_headers(client):
    reg = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "Secret123",
    })
    assert reg.status_code == 201, f"Register failed: {reg.json()}"
    login = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Secret123",
    })
    assert login.status_code == 200, f"Login failed: {login.json()}"
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
