"""Authentication routes: login, logout, and current user profile."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session, select

from ..auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    login_limiter,
    set_auth_cookie,
    verify_password,
)
from ..db import get_session
from ..errors import AppError
from ..models import User
from ..schemas import LoginRequest, LoginResponse, StatusResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("relayops.routers.auth")


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Authenticate user with email and password, setting httpOnly cookie and returning JWT."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    login_limiter.check(client_ip)

    user = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if not user or not verify_password(payload.password, user.password_hash):
        logger.warning("Failed login attempt for email: %s from IP: %s", payload.email, client_ip)
        raise AppError("UNAUTHENTICATED", "Invalid email or password", status_code=401)

    if not user.is_active:
        raise AppError("FORBIDDEN", "Account is deactivated", status_code=403)

    token = create_access_token(user)
    set_auth_cookie(response, token)
    logger.info("User logged in successfully: %s (%s)", user.email, user.role)

    return LoginResponse(
        token=token,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", response_model=StatusResponse)
def logout(
    response: Response,
    _: User = Depends(get_current_user),
) -> StatusResponse:
    """Log out by clearing the httpOnly authentication cookie."""
    clear_auth_cookie(response)
    return StatusResponse(ok=True)


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Retrieve the authenticated user profile."""
    return UserRead.model_validate(current_user)
