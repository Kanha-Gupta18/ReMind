"""Authentication business logic: login, token issuance, refresh."""

import jwt as pyjwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.constants import Role
from app.models.user import User
from app.schemas.auth import LoginResponse, TokenResponse
from app.schemas.user import UserOut


def resolve_patient_id(user: User) -> str | None:
    """The patient a user operates on (tenant scope).

    patient -> themself; family/caregiver/clinician/guardian -> linked
    patient; administrator -> None (all patients).
    """
    if user.role == Role.ADMINISTRATOR.value:
        return None
    if user.role == Role.PATIENT.value:
        return user.id
    return user.patient_id


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise 401."""
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return user


def issue_tokens(user: User) -> LoginResponse:
    """Mint an access/refresh pair for a user."""
    access = create_access_token(user.id, user.role, resolve_patient_id(user))
    refresh = create_refresh_token(user.id)
    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
    )


def refresh_access(refresh_token: str, db: Session) -> TokenResponse:
    """Exchange a valid refresh token for a fresh token pair."""
    try:
        payload = decode_token(refresh_token)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    if payload.get("typ") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token",
        )

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role, resolve_patient_id(user)),
        refresh_token=create_refresh_token(user.id),
    )
