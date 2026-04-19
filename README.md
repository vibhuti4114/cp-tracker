# 🏆 Competitive Programming Tracker API

A production-ready **FastAPI + Redis + PostgreSQL** backend that aggregates and
analyzes user data from **Codeforces**, **LeetCode**, **CodeChef**, and **AtCoder**
into a single unified API.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Multi-platform aggregation** | Codeforces, LeetCode, CodeChef, AtCoder |
| **Multiple handles per platform** | Link as many accounts as you want |
| **JWT Auth** | Access + refresh tokens, token blacklisting on logout |
| **Redis caching** | Platform stats, analytics, leaderboards |
| **Rate limiting** | Fixed-window counter (strict limits on auth endpoints) |
| **Async throughout** | SQLAlchemy 2 async + redis-py async |
| **Leaderboards** | Redis Sorted Sets — top-N by rating or problems solved |
| **Alembic migrations** | Version-controlled schema changes |
| **Docker Compose** | One-command local setup |
| **Test suite** | pytest-asyncio, 25+ tests, mocked Redis & DB |

---

## 🗂 Project Structure

```
cp-tracker/
├── app/
│   ├── core/
│   │   ├── config.py          # Pydantic settings (reads .env)
│   │   ├── database.py        # SQLAlchemy async engine + session
│   │   ├── redis.py           # Redis pool + CacheManager
│   │   ├── security.py        # JWT, password hashing, FastAPI deps
│   │   └── middleware.py      # Redis rate-limit middleware
│   ├── models/
│   │   └── models.py          # ORM: User, PlatformAccount, RatingHistory, Submission
│   ├── schemas/
│   │   └── schemas.py         # Pydantic v2 request/response models
│   ├── routers/
│   │   ├── auth.py            # /auth — register, login, refresh, logout
│   │   ├── users.py           # /users — profile management
│   │   ├── accounts.py        # /accounts — link/unlink/sync handles
│   │   ├── analytics.py       # /analytics — aggregated stats & history
│   │   └── leaderboard.py     # /leaderboard — Redis Sorted Set boards
│   ├── services/
│   │   ├── platform_fetchers.py  # Async fetchers for each platform
│   │   ├── sync_service.py       # Orchestrates fetch → DB → cache
│   │   └── analytics_service.py  # Computes aggregated analytics
│   └── main.py                # FastAPI app factory + lifespan
├── alembic/
│   ├── env.py                 # Async Alembic configuration
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py    # Initial schema migration
├── tests/
│   ├── conftest.py            # Fixtures: SQLite in-memory DB, mock Redis
│   ├── test_auth.py           # Auth endpoint tests
│   ├── test_accounts_analytics.py
│   └── test_redis_cache.py    # CacheManager unit tests
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── .env.example
```

---

## 🚀 Quick Start

### 1 — Clone & configure

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY, DATABASE_URL, REDIS_URL
```

### 2 — Docker Compose (recommended)

```bash
docker compose up --build
# API:   http://localhost:8000
# Docs:  http://localhost:8000/docs
# Redis Commander (debug profile):
docker compose --profile debug up
# UI:    http://localhost:8081
```

### 3 — Local (virtualenv)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run DB migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

---

## 🔌 API Reference

### Auth — `/api/v1/auth`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/register` | Create account |
| `POST` | `/login` | Obtain JWT tokens |
| `POST` | `/refresh` | Rotate access token |
| `POST` | `/logout` | Blacklist current token |

### Platform Accounts — `/api/v1/accounts`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List linked handles |
| `POST` | `/` | Link a new handle (verified via platform API) |
| `DELETE` | `/{id}` | Unlink a handle |
| `POST` | `/{id}/sync` | Sync one account now |
| `POST` | `/sync-all` | Sync all accounts |

### Analytics — `/api/v1/analytics`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Full aggregated analytics (cached) |
| `GET` | `/submissions` | Paginated submission feed |
| `GET` | `/rating-history` | Rating change history |
| `DELETE` | `/cache` | Bust analytics cache |

### Leaderboard — `/api/v1/leaderboard`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{board}` | Top-N for `problems_solved`, `codeforces_rating`, etc. |
| `POST` | `/refresh` | Rebuild leaderboards from DB |

---

## 🔴 Redis Key Design

```
cp_tracker:stats:{user_id}:{platform}     → Platform stat snapshot     TTL: 1h
cp_tracker:analytics:{user_id}            → Aggregated analytics        TTL: 30m
cp_tracker:blacklist:{jti}                → Revoked JWT ID              TTL: token lifetime
cp_tracker:ratelimit:{ip}:global          → Rate limit counter          TTL: 60s
cp_tracker:ratelimit:{ip}:strict          → Auth rate limit counter     TTL: 60s
cp_tracker:leaderboard:{board}            → Sorted set (ZSET)           No TTL
```

---

## 🧪 Running Tests

```bash
pip install -r requirements.txt
pytest                  # all tests
pytest -k test_auth     # auth tests only
pytest -v --tb=long     # verbose
```

Tests use **SQLite in-memory** (no Postgres needed) and a **fully mocked
CacheManager** — no Redis required.

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | JWT signing key (32+ chars) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async Postgres DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `REDIS_CACHE_TTL` | `3600` | Default cache TTL (seconds) |
| `REDIS_RATE_LIMIT_MAX` | `100` | Max requests per window |
| `REDIS_RATE_LIMIT_TTL` | `60` | Rate limit window (seconds) |
| `DEBUG` | `false` | Enable debug logging & auto-create tables |

---

## 🛠 Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "add streak table"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

---

## 📐 Architecture Notes

- **Async-first**: Every DB query and Redis call is `await`-ed; no blocking I/O.
- **Cache-aside pattern**: Read from Redis → on miss compute from DB → write to Redis.
- **Token revocation**: Logout adds the JWT's `jti` claim to a Redis blacklist that auto-expires when the token would have expired anyway.
- **Rate limiting**: Implemented as middleware using a per-IP Redis counter. Auth endpoints get a strict sub-limit (10 req/min) to resist brute force.
- **Leaderboards**: Stored as Redis Sorted Sets (`ZADD` / `ZREVRANGE`) for O(log N) updates and O(log N + M) top-N reads.
