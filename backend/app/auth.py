"""Authentication utilities: scrypt password hashing, JWT, rate limiting, and dependencies."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from datetime import timedelta
from typing import Any

import jwt
from fastapi import Depends, Request, Response
from sqlmodel import Session

from .config import get_settings
from .db import get_session, utcnow
from .errors import AppError
from .models import User

logger = logging.getLogger("relayops.auth")
COOKIE_NAME = "relayops_token"
TOKEN_EXPIRY_HOURS = 12


def hash_password(password: str) -> str:
    """Hash password using Python standard library hashlib.scrypt."""
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    return f"scrypt:16384:8:1:{salt.hex()}:{key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against scrypt hash."""
    try:
        parts = hashed.split(":")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = bytes.fromhex(parts[4])
        expected_key = parts[5]
        computed = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
        return secrets.compare_digest(computed.hex(), expected_key)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    """Create a signed HS256 JWT valid for 12 hours."""
    settings = get_settings()
    now = utcnow()
    exp = now + timedelta(hours=TOKEN_EXPIRY_HOURS)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "clearance": user.clearance,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT token."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as err:
        raise AppError("UNAUTHENTICATED", "Authentication token expired", status_code=401) from err
    except jwt.PyJWTError as err:
        raise AppError("UNAUTHENTICATED", "Invalid authentication token", status_code=401) from err


class LoginRateLimiter:
    """In-memory rate limiter tracking login attempts per IP address."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}

    def check(self, ip: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        valid_attempts = [t for t in self._attempts.get(ip, []) if t > cutoff]
        if len(valid_attempts) >= self.max_attempts:
            raise AppError(
                "RATE_LIMITED",
                "Too many login attempts. Please try again in a minute.",
                status_code=429,
            )
        valid_attempts.append(now)
        self._attempts[ip] = valid_attempts

    def reset(self) -> None:
        self._attempts.clear()


login_limiter = LoginRateLimiter(max_attempts=10, window_seconds=60)


def set_auth_cookie(response: Response, token: str) -> None:
    """Attach the JWT as an httpOnly SameSite=Lax cookie."""
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRY_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=(settings.env == "prod"),
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/", samesite="lax")


def get_token_from_request(request: Request) -> str | None:
    """Extract token from Authorization header or httpOnly cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """FastAPI dependency to retrieve the authenticated user from cookie or Bearer token."""
    token = get_token_from_request(request)
    if not token:
        raise AppError("UNAUTHENTICATED", "Authentication required", status_code=401)

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AppError("UNAUTHENTICATED", "Invalid token subject", status_code=401)

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise AppError("UNAUTHENTICATED", "User not found or inactive", status_code=401)

    return user
