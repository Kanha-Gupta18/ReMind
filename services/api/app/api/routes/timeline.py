"""Timeline routes: patient-facing memory stream and caregiver analytics.

RBAC:
  - patient/support  read the safety-gated timeline, decades, places
  - caregiver/clinician/guardian/admin  read engagement analytics
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_roles
from app.core.database import get_db
from app.models.constants import Role
from app.models.user import User
from app.services import timeline_service

router = APIRouter(prefix="/timeline", tags=["timeline"])

_ANALYTICS_ROLES = [Role.CAREGIVER.value, Role.CLINICIAN.value,
                    Role.GUARDIAN.value, Role.ADMINISTRATOR.value]


def _scope_or_403(scope: str | None) -> str:
    if scope is None:
        raise HTTPException(status_code=403, detail="Administrator must pick a patient")
    return scope


def _serialize(m) -> dict:
    return {
        "id": m.id, "title": m.title, "memory_date": m.memory_date.isoformat() if m.memory_date else None,
        "date_accuracy": m.date_accuracy, "confidence_score": m.confidence_score,
        "sensitivity_flags": m.sensitivity_flags or [], "tags": m.tags or [],
        "media_urls": m.media_urls or [], "narrative": m.narrative,
        "created_at": m.created_at.isoformat(),
    }


@router.get("")
def get_timeline(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    limit: int | None = None,
):
    pid = _scope_or_403(scope)
    memories = timeline_service.get_timeline(
        db, pid, viewer_role=current.role, limit=limit
    )
    return {"items": [_serialize(m) for m in memories], "count": len(memories)}


@router.get("/decades")
def decades(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    pid = _scope_or_403(scope)
    groups = timeline_service.group_by_decade(db, pid)
    return {"items": groups}


@router.get("/places")
def places(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    pid = _scope_or_403(scope)
    groups = timeline_service.group_by_place(db, pid)
    return {"items": groups}


@router.get("/engagement")
def engagement(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_ANALYTICS_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    pid = _scope_or_403(scope)
    return timeline_service.engagement_stats(db, pid)
