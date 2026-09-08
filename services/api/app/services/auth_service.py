"""Authentication business logic: login, session issuance, rotation, revocation."""

from datetime import timedelta
from hmac import compare_digest

import jwt as pyjwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    new_token_id,
    token_id_hash,
    verify_password,
)
from app.models.base import utcnow
from app.models.user import AuthSession, User
from app.schemas.auth import LoginResponse, TokenResponse
from app.schemas.user import UserOut


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


def _session_is_usable(session: AuthSession) -> bool:
    now = utcnow()
    return (
        session.revoked_at is None
        and session.idle_expires_at > now
        and session.absolute_expires_at > now
    )


def issue_tokens(db: Session, user: User) -> LoginResponse:
    """Create a persistent login session and its first rotating token pair."""
    now = utcnow()
    refresh_id = new_token_id()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=token_id_hash(refresh_id),
        created_at=now,
        last_seen_at=now,
        idle_expires_at=now + timedelta(minutes=settings.session_idle_minutes),
        absolute_expires_at=now + timedelta(minutes=settings.refresh_token_expire_minutes),
    )
    db.add(session)
    db.flush()
    access = create_access_token(user.id, user.role, session.id)
    refresh = create_refresh_token(user.id, session.id, refresh_id)
    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
    )


def refresh_access(refresh_token: str, db: Session) -> TokenResponse:
    """Rotate a valid refresh token. A replayed or revoked token is rejected."""
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

    session_id = payload.get("sid")
    refresh_id = payload.get("jti")
    if not session_id or not refresh_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token session")

    auth_session = (
        db.query(AuthSession)
        .filter(AuthSession.id == session_id)
        .with_for_update()
        .first()
    )
    if (
        auth_session is None
        or auth_session.user_id != payload.get("sub")
        or not _session_is_usable(auth_session)
        or not compare_digest(auth_session.refresh_token_hash, token_id_hash(refresh_id))
    ):
        raise HTTPException(status_code=401, detail="Refresh session is invalid or expired")

    user = db.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    now = utcnow()
    next_refresh_id = new_token_id()
    auth_session.refresh_token_hash = token_id_hash(next_refresh_id)
    auth_session.last_seen_at = now
    auth_session.idle_expires_at = min(
        now + timedelta(minutes=settings.session_idle_minutes),
        auth_session.absolute_expires_at,
    )
    result = TokenResponse(
        access_token=create_access_token(user.id, user.role, auth_session.id),
        refresh_token=create_refresh_token(user.id, auth_session.id, next_refresh_id),
    )
    db.commit()
    return result


def revoke_session(session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoke_reason = reason


def revoke_user_sessions(db: Session, user_id: str, reason: str) -> int:
    sessions = db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    ).all()
    for session in sessions:
        revoke_session(session, reason)
    return len(sessions)
