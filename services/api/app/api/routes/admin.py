"""Administrator routes (spec §23). Administrator-only, cross-patient.

User directory + coarse stats + user lifecycle (create, deactivate, role
change, password reset). Sensitive audit trail and per-patient details
stay inside the patient-scoped APIs.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import hash_password
from app.models.constants import Role
from app.models.memory import MemoryCard, Source
from app.models.user import User
from app.schemas.user import UserAdminOut, UserCreate, UserUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/admin", tags=["admin"])
_admin_only = require_roles(Role.ADMINISTRATOR.value)

_VALID_ROLES = {r.value for r in Role}
_PATIENTLESS_ROLES = {Role.PATIENT.value, Role.ADMINISTRATOR.value}


def _validate_patient_link(db: Session, role: str, patient_id: str | None) -> None:
    """Non-patient roles must link to a real patient; patientless roles cannot."""
    if role in _PATIENTLESS_ROLES:
        if patient_id is not None:
            raise HTTPException(status_code=400,
                                detail=f"Role '{role}' cannot be linked to a patient")
        return
    if patient_id is None:
        raise HTTPException(status_code=400,
                            detail=f"Role '{role}' requires a patient_id")
    patient = db.get(User, patient_id)
    if patient is None or patient.role != Role.PATIENT.value:
        raise HTTPException(status_code=400, detail="patient_id must reference a patient user")


@router.get("/users", dependencies=[Depends(_admin_only)])
def list_users(db: Annotated[Session, Depends(get_db)]):
    users = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    return {"items": [UserAdminOut.model_validate(u).model_dump() for u in users],
            "count": len(users)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR.value))],
):
    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    if db.query(User).filter(User.email == body.email).first() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    _validate_patient_link(db, body.role, body.patient_id)

    user = User(email=body.email, full_name=body.full_name, role=body.role,
                password_hash=hash_password(body.password), patient_id=body.patient_id)
    db.add(user)
    db.flush()
    log_action(db, current.id, "created", "user", user.id,
               {"email": user.email, "role": user.role})
    db.commit()
    return UserAdminOut.model_validate(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR.value))],
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current.id:
        if body.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        if body.role is not None and body.role != target.role:
            raise HTTPException(status_code=400,
                                detail="Cannot change your own role")

    if body.role is not None:
        if body.role not in _VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
        if body.role in _PATIENTLESS_ROLES:
            target.role = body.role
            target.patient_id = None
        else:
            pid = body.patient_id if body.patient_id is not None else target.patient_id
            if pid is None:
                raise HTTPException(status_code=400,
                                    detail=f"Role '{body.role}' requires a patient_id")
            _validate_patient_link(db, body.role, pid)
            target.role = body.role
            target.patient_id = pid

    if body.patient_id is not None:
        _validate_patient_link(db, target.role, body.patient_id)
        target.patient_id = body.patient_id

    if body.full_name is not None:
        target.full_name = body.full_name
    if body.password is not None:
        target.password_hash = hash_password(body.password)
    if body.is_active is not None:
        target.is_active = body.is_active

    log_action(db, current.id, "updated", "user", target.id, body.model_dump(exclude_none=True))
    db.commit()
    return UserAdminOut.model_validate(target)


@router.get("/stats", dependencies=[Depends(_admin_only)])
def stats(db: Annotated[Session, Depends(get_db)]):
    by_role = dict(
        db.query(User.role, func.count(User.id)).group_by(User.role).all()
    )
    return {
        "users_by_role": by_role,
        "total_users": db.query(User).count(),
        "total_sources": db.query(Source).count(),
        "total_memories": db.query(MemoryCard).count(),
    }
