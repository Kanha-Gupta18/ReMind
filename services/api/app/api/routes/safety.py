"""Safety routes: events, acknowledgment, caregiver stop, level (spec §16, §18.5).

RBAC:
  - caregiver/clinician/guardian  view consented events
  - caregiver                      issue a consented safety stop
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_consent_action, require_roles
from app.core.database import get_db
from app.models.constants import ConsentAction, Role
from app.models.conversation import ConversationSession, SafetyEvent
from app.models.user import User
from app.services import audit_service, safety_service

router = APIRouter(prefix="/safety", tags=["safety"])

_EVENT_ROLES = [Role.CAREGIVER.value, Role.CLINICIAN.value,
                Role.GUARDIAN.value]


def _resolve_scope(scope: str | None, patient_id: str | None = None) -> str:
    """Scope resolution: linked roles use their patient; administrator must
    pass patient_id explicitly (cross-patient)."""
    if scope is not None:
        if patient_id and patient_id != scope:
            raise HTTPException(status_code=403, detail="Not your patient")
        return scope
    if patient_id is None:
        raise HTTPException(status_code=403, detail="Administrator must pick a patient")
    return patient_id


@router.get("/events")
def list_events(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_EVENT_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
    unacknowledged_only: bool = False,
):
    pid = _resolve_scope(scope, patient_id)
    require_consent_action(db, current, pid, ConsentAction.SAFETY_VIEW)
    events = safety_service.list_patient_events(db, pid, unacknowledged_only=unacknowledged_only)
    return {"items": [
        {"id": e.id, "event_type": e.event_type, "severity": e.severity,
         "context": e.context, "action_taken": e.action_taken,
         "session_id": e.session_id, "acknowledged_by": e.acknowledged_by,
         "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None,
         "created_at": e.created_at.isoformat()}
        for e in events
    ], "count": len(events)}


@router.post("/events/{event_id}/acknowledge")
def acknowledge_event(
    event_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_EVENT_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    event = db.get(SafetyEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if scope is not None and event.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your patient")
    require_consent_action(db, current, event.patient_id, ConsentAction.SAFETY_MANAGE)
    safety_service.acknowledge_event(db, event_id, current.id)
    audit_service.log_action(db, current.id, "acknowledged", "safety_event", event_id)
    db.commit()
    return {"ok": True}


@router.post("/sessions/{session_id}/stop")
def caregiver_stop(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.CAREGIVER.value))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if scope is not None and session.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your patient")
    require_consent_action(db, current, session.patient_id, ConsentAction.SAFETY_MANAGE)
    event = safety_service.stop_session_for_safety(
        db, session, context={"by": current.id}, action="session_stopped_by_caregiver"
    )
    db.commit()
    return {"ok": True, "safety_event": event.id}


@router.get("/level")
def safety_level(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    require_consent_action(db, current, pid, ConsentAction.SAFETY_VIEW)
    return {"patient_id": pid, "safety_level": safety_service.resolve_safety_level(db, pid)}
