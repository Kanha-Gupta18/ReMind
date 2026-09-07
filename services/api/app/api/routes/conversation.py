"""Conversation routes: sessions and turns (spec §21).

RBAC:
  - patient       start sessions and send turns
  - caregiver     stop a session for safety (§18.5)
  - support roles read session history
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai import conversation as agent
from app.api.deps import get_current_user, get_patient_scope, require_roles
from app.core.database import get_db
from app.models.constants import Role
from app.models.conversation import ConversationSession
from app.models.user import User
from app.schemas.conversation import MessageSend, SessionStart
from app.services import audit_service, safety_service

router = APIRouter(prefix="/conversations", tags=["conversation"])

_READ_ROLES = [Role.PATIENT.value, Role.FAMILY_REVIEWER.value, Role.CAREGIVER.value,
               Role.GUARDIAN.value, Role.CLINICIAN.value, Role.ADMINISTRATOR.value]


def _get_scoped(db: Session, session_id: str, scope: str | None) -> ConversationSession:
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if scope is not None and scope != session.patient_id:
        raise HTTPException(status_code=403, detail="Not your session")
    return session


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def start_session(
    body: SessionStart,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.PATIENT.value))],
):
    session = agent.start_session(db, current.id, session_type=body.session_type,
                                  started_by=current.id)
    db.commit()
    return {"id": session.id, "patient_id": session.patient_id,
            "session_type": session.session_type, "status": session.status}


@router.get("/sessions")
def list_sessions(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    query = db.query(ConversationSession).order_by(ConversationSession.created_at.desc())
    if scope:
        query = query.filter(ConversationSession.patient_id == scope)
    sessions = query.all()
    return {"items": [
        {"id": s.id, "patient_id": s.patient_id, "session_type": s.session_type,
         "status": s.status, "started_at": s.created_at.isoformat(),
         "ended_at": s.ended_at.isoformat() if s.ended_at else None}
        for s in sessions
    ], "count": len(sessions)}


@router.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    session = _get_scoped(db, session_id, scope)
    messages = agent.session_history(db, session.id)
    return {"items": [
        {"id": m.id, "role": m.role, "content": m.content,
         "tool_calls": m.tool_calls, "safety_flag": m.safety_flag,
         "created_at": m.created_at.isoformat()}
        for m in messages
    ], "count": len(messages)}


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: str,
    body: MessageSend,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.PATIENT.value))],
):
    session = db.get(ConversationSession, session_id)
    if session is None or session.patient_id != current.id:
        raise HTTPException(status_code=403, detail="Not your session")
    result = agent.respond(db, session_id, body.content)
    db.commit()
    return result


@router.post("/sessions/{session_id}/stop")
def stop_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    session = _get_scoped(db, session_id, scope)
    if current.role == Role.PATIENT.value:
        agent.stop_session(db, session_id)
        audit_service.log_action(db, current.id, "ended", "conversation_session", session.id)
        db.commit()
        return {"ok": True, "status": session.status}

    if current.role == Role.CAREGIVER.value:
        event = safety_service.stop_session_for_safety(
            db, session, severity="medium",
            context={"by": current.id}, action="session_stopped_by_caregiver",
        )
        audit_service.log_action(db, current.id, "stopped_for_safety",
                                 "conversation_session", session.id)
        db.commit()
        return {"ok": True, "status": session.status, "safety_event": event.id}

    raise HTTPException(status_code=403, detail="Only patient or caregiver may stop")
