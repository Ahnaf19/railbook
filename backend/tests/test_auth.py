import uuid

import jwt
import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture
async def registered_user(client: AsyncClient):
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "pass123", "full_name": "Auth Test User"},
    )
    return {"email": email, "password": "pass123", "response": resp}


async def test_register_returns_jwt(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": f"reg-{uuid.uuid4().hex[:8]}@test.com", "password": "p", "full_name": "A"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_returns_valid_jwt(client: AsyncClient, registered_user):
    resp = await client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    payload = jwt.decode(
        data["access_token"], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
    assert payload["type"] == "access"
    assert "sub" in payload


async def test_duplicate_email_returns_409(client: AsyncClient, registered_user):
    resp = await client.post(
        "/auth/register",
        json={
            "email": registered_user["email"],
            "password": "other",
            "full_name": "Dup",
        },
    )
    assert resp.status_code == 409


async def test_invalid_credentials_returns_401(client: AsyncClient):
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@nowhere.com", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_expired_token_rejected(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code in (401, 403)


async def test_refresh_token_rotation(client: AsyncClient, registered_user):
    login_resp = await client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_me_returns_current_user(client: AsyncClient, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "full_name" in data
