"""FastAPI dependencies: authentication, RBAC, and tenant isolation.

Patterns used by every protected route:
  current_user = Depends(get_current_user)          -> User
  current_user = Depends(require_roles(Role.X, ...)) -> User (else 403)
  scope        = Depends(get_patient_scope)          -> str | None
  patient_id   = Depends(ensure_patient_access)      -> str (else 403)
"""

from typing import Annotated

import jwt as pyjwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.constants import Role
from app.models.user import User

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

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
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


def get_patient_scope(user: Annotated[User, Depends(get_current_user)]) -> str | None:
    """Tenant isolation (spec §24): the patient this caller may access.

    patient -> themself; family/caregiver/clinician/guardian -> their
    linked patient; administrator -> None (access to all).
    """
    if user.role == Role.ADMINISTRATOR.value:
        return None
    if user.role == Role.PATIENT.value:
        return user.id
    if not user.patient_id:
        raise HTTPException(status_code=403, detail="No patient relationship is configured")
    return user.patient_id


def ensure_patient_access(
    patient_id: str,
    scope: Annotated[str | None, Depends(get_patient_scope)],
) -> str:
    """For route paths like /patients/{patient_id}/...: verify the caller
    may operate on this patient, else 403."""
    if scope is None or scope == patient_id:
        return patient_id
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access to this patient is not allowed",
    )
