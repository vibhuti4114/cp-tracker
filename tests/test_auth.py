"""Tests for /api/v1/auth endpoints."""

import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    res = await client.post("/api/v1/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "Alice123",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "Bob12345"}
    await client.post("/api/v1/auth/register", json=payload)
    res = await client.post("/api/v1/auth/register", json={**payload, "username": "bob2"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client):
    res = await client.post("/api/v1/auth/register", json={
        "username": "charlie",
        "email": "charlie@example.com",
        "password": "weak",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/v1/auth/register", json={
        "username": "diana",
        "email": "diana@example.com",
        "password": "Diana123",
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "diana@example.com",
        "password": "Diana123",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "username": "eve",
        "email": "eve@example.com",
        "password": "Eve12345",
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "eve@example.com",
        "password": "wrongpass",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client, auth_headers):
    res = await client.get("/api/v1/users/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_logout(client, auth_headers, mock_cache):
    res = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert res.status_code == 200
    mock_cache.blacklist_token.assert_called_once()
