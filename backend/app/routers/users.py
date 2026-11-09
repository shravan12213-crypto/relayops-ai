"""User management routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..auth import get_current_user, hash_password
from ..db import get_session
from ..errors import AppError
from ..models import User
from ..schemas import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger("relayops.routers.users")


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[UserRead]:
    """List all registered users."""
    users = session.exec(select(User).order_by(User.name.asc())).all()
    return [UserRead.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> UserRead:
    """Retrieve details for a specific user."""
    user = session.get(User, user_id)
    if not user:
        raise AppError("NOT_FOUND", "User not found", status_code=404)
    return UserRead.model_validate(user)


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
) -> UserRead:
    """Create a new user with scrypt hashed password."""
    existing = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if existing:
        raise AppError("CONFLICT", "A user with this email already exists", status_code=409)

    user = User(
        email=payload.email.lower(),
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        clearance=payload.clearance,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    logger.info("Created user %s (%s, clearance %d)", user.email, user.role, user.clearance)
    return UserRead.model_validate(user)

