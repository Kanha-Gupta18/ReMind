"""Auth routes: /auth/login, /auth/refresh, /auth/logout, /auth/me (spec §22)."""

from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import AuthSession, User
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.audit_service import log_action
from app.services.auth_service import authenticate_user, issue_tokens, refresh_access, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    user = authenticate_user(db, body.email, body.password)
    result = issue_tokens(db, user)
    log_action(db, user.id, "auth.login", "user", user.id, details={"email": user.email})
    db.commit()
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return refresh_access(body.refresh_token, db)


@router.post("/logout")
def logout(
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    auth_session = db.get(AuthSession, getattr(current, "_auth_session_id", None))
    if auth_session is not None:
        revoke_session(auth_session, "logout")
    log_action(db, current.id, "auth.logout", "user", current.id)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current: Annotated[User, Depends(get_current_user)]):
    """Who am I? Lets the frontends validate a stored token."""
    return UserOut.model_validate(current)
