"""Tests for P03: Authentication, scrypt password hashing, JWT cookies, rate limiting, and users router."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import COOKIE_NAME, hash_password, login_limiter, verify_password
from app.db import get_engine
from app.models import User


def test_password_hashing_and_verification() -> None:
    raw = "correct-horse-battery-staple"
    hashed = hash_password(raw)

    assert hashed.startswith("scrypt:")
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(raw, "malformed:hash") is False


def test_auth_flow_login_me_logout(client: TestClient) -> None:
    login_limiter.reset()

    # 1. Register a test user directly in DB
    with Session(get_engine()) as session:
        user = User(
            email="meera@payflow.dev",
            name="Meera Patel",
            password_hash=hash_password("password123"),
            role="lead",
            clearance=3,
        )
        session.add(user)
        session.commit()

    # 2. Login with valid credentials
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "meera@payflow.dev", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == "meera@payflow.dev"
    assert data["user"]["role"] == "lead"
    assert data["user"]["clearance"] == 3
    assert COOKIE_NAME in resp.cookies
    token = data["token"]

    # 3. Access /auth/me with Bearer token
    me_bearer = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_bearer.status_code == 200
    assert me_bearer.json()["email"] == "meera@payflow.dev"

    # 4. Access /auth/me with Cookie (no Authorization header)
    client.cookies.set(COOKIE_NAME, token)
    me_cookie = client.get("/api/v1/auth/me")
    assert me_cookie.status_code == 200
    assert me_cookie.json()["id"] == data["user"]["id"]

    # 5. Logout clears the cookie
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    set_cookie_header = logout_resp.headers.get("set-cookie", "")
    assert 'relayops_token=""' in set_cookie_header or "relayops_token=;" in set_cookie_header

    # 6. Unauthenticated request to /auth/me fails with 401
    client.cookies.delete(COOKIE_NAME)
    unauth = client.get("/api/v1/auth/me")
    assert unauth.status_code == 401
    assert unauth.json()["error"]["code"] == "UNAUTHENTICATED"


def test_login_invalid_credentials_generic_error(client: TestClient) -> None:
    login_limiter.reset()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["error"]["code"] == "UNAUTHENTICATED"
    assert data["error"]["message"] == "Invalid email or password"


def test_login_rate_limiting(client: TestClient) -> None:
    login_limiter.reset()

    # 10 attempts
    for _ in range(10):
        client.post(
            "/api/v1/auth/login",
            json={"email": "rate@test.com", "password": "wrong"},
        )

    # 11th attempt must trigger 429 RATE_LIMITED
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "rate@test.com", "password": "wrong"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"

    login_limiter.reset()


def test_users_router(client: TestClient) -> None:
    login_limiter.reset()

    with Session(get_engine()) as session:
        admin = User(
            email="admin@test.com",
            name="Admin User",
            password_hash=hash_password("adminpass123"),
            role="lead",
            clearance=3,
        )
        session.add(admin)
        session.commit()

    # Login as admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "adminpass123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create new user via POST /users
    create_res = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "kabir@payflow.dev",
            "name": "Kabir Sharma",
            "password": "successorpassword123",
            "role": "successor",
            "clearance": 1,
        },
    )
    assert create_res.status_code == 201
    user_data = create_res.json()
    assert user_data["email"] == "kabir@payflow.dev"
    assert "password_hash" not in user_data

    # List users
    list_res = client.get("/api/v1/users", headers=headers)
    assert list_res.status_code == 200
    emails = [u["email"] for u in list_res.json()]
    assert "kabir@payflow.dev" in emails
    assert "admin@test.com" in emails

    # Get single user
    single_res = client.get(f"/api/v1/users/{user_data['id']}", headers=headers)
    assert single_res.status_code == 200
    assert single_res.json()["name"] == "Kabir Sharma"
