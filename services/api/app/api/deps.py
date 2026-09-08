"""FastAPI dependencies: authentication, RBAC, and tenant isolation.

Patterns used by every protected route:
  current_user = Depends(get_current_user)          -> User
  current_user = Depends(require_roles(Role.X, ...)) -> User (else 403)
  scope        = Depends(get_patient_scope)          -> str | None
  patient_id   = Depends(ensure_patient_access)      -> str (else 403)
"""

from datetime import timedelta
from typing import Annotated

import jwt as pyjwt
from fastapi import Cookie, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_token
from app.models.constants import AccessGrantStatus, ConsentAction, Role
from app.models.base import utcnow
from app.models.user import AuthSession, PatientAccessGrant, User
from app.services import consent_service

# Accepts Authorization: Bearer <token> (auto_error=False so we can also
# fall back to the httpOnly cookie).
bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    if credentials is not None:
        return credentials.credentials
    return cookie_token


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    remind_token: Annotated[str | None, Cookie()] = None,
) -> User:
    """Resolve the authenticated user from a bearer token or cookie."""
    token = _extract_token(credentials, remind_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not an access token",
        )

    session_id = payload.get("sid")
    auth_session = db.get(AuthSession, session_id) if session_id else None
    now = utcnow()
    if (
        auth_session is None
        or auth_session.user_id != payload.get("sub")
        or auth_session.revoked_at is not None
        or auth_session.idle_expires_at <= now
        or auth_session.absolute_expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    auth_session.last_seen_at = now
    auth_session.idle_expires_at = min(
        now + timedelta(minutes=settings.session_idle_minutes),
        auth_session.absolute_expires_at,
    )
    db.commit()
    user._auth_session_id = auth_session.id
    return user


def require_roles(*roles: str):
    """Dependency factory: allow only the given roles (spec §23).

    Usage: Depends(require_roles(Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value))
    """

    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this role",
            )
        return user

    return checker


def _resolve_patient_scope(
    db: Session,
    user: User,
    requested_patient_id: str | None,
) -> str:
    """Resolve one patient from active relationship grants."""
    if user.role == Role.PATIENT.value:
        if requested_patient_id and requested_patient_id != user.id:
            raise HTTPException(status_code=403, detail="Access to this patient is not allowed")
        return user.id
    if user.role == Role.ADMINISTRATOR.value:
        raise HTTPException(
            status_code=403,
            detail="Administrators cannot access patient content",
        )

    query = (
        db.query(PatientAccessGrant)
        .join(User, User.id == PatientAccessGrant.patient_id)
        .filter(
            PatientAccessGrant.user_id == user.id,
            PatientAccessGrant.status == AccessGrantStatus.ACTIVE.value,
            User.role == Role.PATIENT.value,
            User.is_active.is_(True),
        )
    )
    if requested_patient_id:
        grant = query.filter(PatientAccessGrant.patient_id == requested_patient_id).first()
        if grant is None:
            raise HTTPException(status_code=403, detail="Access to this patient is not allowed")
        return grant.patient_id

    grants = query.limit(2).all()
    if not grants:
        raise HTTPException(status_code=403, detail="No patient relationship is configured")
    if len(grants) > 1:
        raise HTTPException(status_code=400, detail="Select a patient for this request")
    return grants[0].patient_id


def get_patient_scope(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    patient_id: Annotated[str | None, Query()] = None,
    x_patient_id: Annotated[str | None, Header(alias="X-Patient-ID")] = None,
) -> str:
    """Tenant isolation using an explicit, active account-patient relationship."""
    if patient_id and x_patient_id and patient_id != x_patient_id:
        raise HTTPException(status_code=400, detail="Conflicting patient selections")
    return _resolve_patient_scope(db, user, x_patient_id or patient_id)


def ensure_patient_access(
    patient_id: str,
    scope: Annotated[str, Depends(get_patient_scope)],
) -> str:
    """For route paths like /patients/{patient_id}/...: verify the caller
    may operate on this patient, else 403."""
    if scope == patient_id:
        return patient_id
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access to this patient is not allowed",
    )


def require_consent_action(
    db: Session,
    user: User,
    patient_id: str,
    action: str | ConsentAction,
) -> None:
    """Fail unless role, relationship, and the active directive allow an action."""
    if not consent_service.action_is_allowed(db, user, patient_id, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The active consent directive denies this action",
        )
