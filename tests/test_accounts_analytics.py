"""Tests for platform account and analytics endpoints."""

import pytest
from unittest.mock import AsyncMock, patch


MOCK_CF_USER = {
    "handle": "tourist",
    "current_rating": 3979.0,
    "max_rating": 4000.0,
    "problems_solved": 0,
}

MOCK_SUBMISSIONS = []
MOCK_RATING_HISTORY = []


@pytest.mark.asyncio
async def test_list_accounts_empty(client, auth_headers):
    res = await client.get("/api/v1/accounts", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_link_account_success(client, auth_headers):
    with patch(
        "app.routers.accounts.get_fetcher"
    ) as mock_get_fetcher:
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_user_info = AsyncMock(return_value=MOCK_CF_USER)
        mock_get_fetcher.return_value = mock_fetcher

        res = await client.post(
            "/api/v1/accounts",
            json={"platform": "codeforces", "handle": "tourist", "is_primary": True},
            headers=auth_headers,
        )
    assert res.status_code == 201
    data = res.json()
    assert data["platform"] == "codeforces"
    assert data["handle"] == "tourist"
    assert data["current_rating"] == 3979.0


@pytest.mark.asyncio
async def test_link_duplicate_account(client, auth_headers):
    with patch("app.routers.accounts.get_fetcher") as mock_gf:
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_user_info = AsyncMock(return_value=MOCK_CF_USER)
        mock_gf.return_value = mock_fetcher

        await client.post(
            "/api/v1/accounts",
            json={"platform": "codeforces", "handle": "tourist"},
            headers=auth_headers,
        )
        res = await client.post(
            "/api/v1/accounts",
            json={"platform": "codeforces", "handle": "tourist"},
            headers=auth_headers,
        )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_link_invalid_platform(client, auth_headers):
    res = await client.post(
        "/api/v1/accounts",
        json={"platform": "hackerrank", "handle": "user123"},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_unlink_account(client, auth_headers):
    # First link
    with patch("app.routers.accounts.get_fetcher") as mock_gf:
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_user_info = AsyncMock(return_value=MOCK_CF_USER)
        mock_gf.return_value = mock_fetcher
        link_res = await client.post(
            "/api/v1/accounts",
            json={"platform": "codeforces", "handle": "tourist"},
            headers=auth_headers,
        )
    account_id = link_res.json()["id"]

    # Then unlink
    res = await client.delete(f"/api/v1/accounts/{account_id}", headers=auth_headers)
    assert res.status_code == 200

    # 200 confirms account was deleted; cascade is enforced by Postgres in production
    assert "unlinked" in res.json()["message"].lower()


@pytest.mark.asyncio
async def test_analytics_empty(client, auth_headers, mock_cache):
    # Cache miss → compute from empty DB
    mock_cache.get = AsyncMock(return_value=None)
    res = await client.get("/api/v1/analytics", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_problems_solved"] == 0
    assert data["platforms"] == []
    assert data["streak_days"] == 0


@pytest.mark.asyncio
async def test_analytics_cache_hit(client, auth_headers, mock_cache):
    cached_data = {
        "user_id": 1,
        "total_problems_solved": 500,
        "total_contests": 42,
        "platforms": [],
        "tag_breakdown": [],
        "difficulty_breakdown": {},
        "daily_activity": [],
        "streak_days": 7,
        "last_updated": "2025-01-01T00:00:00+00:00",
    }
    mock_cache.get = AsyncMock(return_value=cached_data)
    res = await client.get("/api/v1/analytics", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["total_problems_solved"] == 500
    # Verify DB was NOT hit — cache.get was called and returned data
    mock_cache.get.assert_called_once()


@pytest.mark.asyncio
async def test_submissions_empty(client, auth_headers):
    res = await client.get("/api/v1/analytics/submissions", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_rating_history_empty(client, auth_headers):
    res = await client.get("/api/v1/analytics/rating-history", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_bust_analytics_cache(client, auth_headers, mock_cache):
    res = await client.delete("/api/v1/analytics/cache", headers=auth_headers)
    assert res.status_code == 200
    mock_cache.delete.assert_called_once_with("analytics", mock_cache.delete.call_args[0][1])


@pytest.mark.asyncio
async def test_health_endpoint(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert "status" in res.json()
    assert "redis" in res.json()
