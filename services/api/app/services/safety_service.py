"""Safety gating and safety events (spec §16, §18.5).

Three jobs:
  1. Resolve a patient's safety level from their profile.
  2. Decide whether a memory may be released to a viewer (the gating
     matrix below) — this is what keeps sensitive content away from the
     patient unless conditions allow.
  3. Record and acknowledge safety events (distress, caregiver stop,
     restricted queries).

Release matrix for SENSITIVE memories (memory.sensitivity_flags non-empty)
when the viewer is the PATIENT:

  NORMAL                -> allowed, display "full"
  CAUTION               -> allowed, display "caution"
  CAREGIVER_RECOMMENDED -> allowed, display "caregiver_recommended"
  CAREGIVER_REQUIRED    -> blocked unless a caregiver is present
  HIDDEN                -> blocked

Rules that apply in every case:
  - memory.status == RESTRICTED -> blocked for patients and contributors.
  - Non-patient viewers (family_reviewer, caregiver, guardian, clinician,
    administrator) bypass patient gating — they are the support network.
  - memory.visibility applies last (family_only vs patient).

Display levels: full | caution | caregiver_recommended | restricted | hidden.
"""

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.constants import (
    MemoryStatus,
    Role,
    SafetyEventType,
    SafetyLevel,
    Severity,
    Visibility,
)
from app.models.conversation import ConversationSession, SafetyEvent
from app.models.memory import MemoryCard
from app.models.user import PatientProfile, User

# Roles that may see sensitive content without patient gating.
_SUPPORT_ROLES = {
    Role.FAMILY_REVIEWER.value,
    Role.CAREGIVER.value,
    Role.GUARDIAN.value,
    Role.CLINICIAN.value,
    Role.ADMINISTRATOR.value,
}


def resolve_safety_level(db: Session, patient_id: str) -> str:
    """Current safety level of a patient (defaults to NORMAL)."""
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == patient_id).first()
    if profile is None:
        return SafetyLevel.NORMAL.value
    return profile.safety_level or SafetyLevel.NORMAL.value


def is_sensitive(memory: MemoryCard) -> bool:
    return bool(memory.sensitivity_flags)


def evaluate_release(
    memory: MemoryCard,
    safety_level: str,
    caregiver_present: bool = False,
    viewer_role: str | None = None,
) -> dict:
    """Decide whether a memory may be shown to a viewer.

    Returns {allowed, display_level, reason}.
    """
    if memory.status == MemoryStatus.DELETED.value:
        return {"allowed": False, "display_level": "hidden", "reason": "Memory deleted"}
    if viewer_role is None or viewer_role == Role.PATIENT.value:
        if memory.approved_revision_id is None:
            return {"allowed": False, "display_level": "hidden", "reason": "Memory is not approved"}
        if memory.status in {
            MemoryStatus.DISPUTED.value,
            MemoryStatus.ARCHIVED.value,
            MemoryStatus.RESTRICTED.value,
        }:
            return {"allowed": False, "display_level": "hidden",
                    "reason": f"Memory is {memory.status.lower()}"}
        if memory.visibility not in {Visibility.PATIENT.value, Visibility.BOTH.value}:
            return {"allowed": False, "display_level": "hidden", "reason": "Memory is not patient-visible"}
    if memory.status == MemoryStatus.RESTRICTED.value:
        if viewer_role in {Role.CAREGIVER.value, Role.GUARDIAN.value,
                           Role.CLINICIAN.value, Role.ADMINISTRATOR.value}:
            return {"allowed": True, "display_level": "restricted",
                    "reason": "RESTRICTED memory shown to support staff only"}
        return {"allowed": False, "display_level": "hidden",
                "reason": "RESTRICTED memory"}

    # Support network bypasses patient-facing sensitivity gating.
    if viewer_role and viewer_role != Role.PATIENT.value:
        if viewer_role not in _SUPPORT_ROLES:
            # family_contributor sees family-only content, still not sensitive-restricted
            return {"allowed": True, "display_level": "caution",
                    "reason": "viewed by family contributor"}
        return {"allowed": True, "display_level": "full",
                "reason": "support role may view sensitive content"}

    # Patient viewer: apply the release matrix.
    if not is_sensitive(memory):
        return {"allowed": True, "display_level": "full", "reason": "not sensitive"}

    if safety_level == SafetyLevel.HIDDEN.value:
        return {"allowed": False, "display_level": "hidden",
                "reason": "content hidden at HIDDEN safety level"}
    if safety_level == SafetyLevel.CAREGIVER_REQUIRED.value:
        if not caregiver_present:
            return {"allowed": False, "display_level": "restricted",
                    "reason": "caregiver required for sensitive content"}
        return {"allowed": True, "display_level": "caregiver_recommended",
                "reason": "caregiver present; sensitive content shown"}
    if safety_level == SafetyLevel.CAREGIVER_RECOMMENDED.value:
        return {"allowed": True, "display_level": "caregiver_recommended",
                "reason": "caregiver recommended for sensitive content"}
    if safety_level == SafetyLevel.CAUTION.value:
        return {"allowed": True, "display_level": "caution",
                "reason": "caution label shown for sensitive content"}

    return {"allowed": True, "display_level": "full", "reason": "NORMAL safety level"}


# ---------------------------------------------------------------------------
# Safety events (§18.5)
# ---------------------------------------------------------------------------


def record_safety_event(
    db: Session,
    patient_id: str,
    event_type: str,
    severity: str = Severity.LOW.value,
    context: dict | None = None,
    session_id: str | None = None,
    memory_card_id: str | None = None,
    action_taken: str | None = None,
) -> SafetyEvent:
    event = SafetyEvent(
        patient_id=patient_id,
        event_type=event_type,
        severity=severity,
        context=context or {},
        session_id=session_id,
        memory_card_id=memory_card_id,
        action_taken=action_taken,
    )
    db.add(event)
    db.flush()
    return event


def acknowledge_event(db: Session, event_id: str, user_id: str) -> SafetyEvent:
    event = db.get(SafetyEvent, event_id)
    if event is None:
        raise ValueError(f"Safety event {event_id} not found")
    event.acknowledged_by = user_id
    event.acknowledged_at = utcnow()
    db.flush()
    return event


def list_patient_events(
    db: Session, patient_id: str, unacknowledged_only: bool = False
) -> list[SafetyEvent]:
    query = db.query(SafetyEvent).filter(SafetyEvent.patient_id == patient_id)
    if unacknowledged_only:
        query = query.filter(SafetyEvent.acknowledged_at.is_(None))
    return query.order_by(SafetyEvent.created_at.desc()).all()


def record_restricted_query(
    db: Session,
    patient_id: str,
    session_id: str,
    query: str,
    reason: str,
) -> tuple[SafetyEvent, str]:
    """Block a query that touches restricted content and log it.

    Returns (event, guardrail_message). The conversation agent returns
    the message to the patient — never the restricted content (§21).
    """
    event = record_safety_event(
        db,
        patient_id=patient_id,
        event_type=SafetyEventType.RESTRICTED_QUERY.value,
        severity=Severity.MEDIUM.value,
        context={"query": query, "reason": reason},
        session_id=session_id,
        action_taken="query_blocked",
    )
    message = (
        "I don't have information about that, and I'd rather not guess. "
        "Is there something else we could talk about?"
    )
    return event, message


def stop_session_for_safety(
    db: Session,
    session: ConversationSession,
    severity: str = Severity.MEDIUM.value,
    context: dict | None = None,
    action: str = "session_stopped",
) -> SafetyEvent:
    """Caregiver/distress stop: log it and mark the session stopped (§18.5)."""
    session.status = "stopped"
    session.ended_at = utcnow()
    db.flush()
    return record_safety_event(
        db,
        patient_id=session.patient_id,
        event_type=SafetyEventType.CAREGIVER_STOP.value,
        severity=severity,
        context=context or {},
        session_id=session.id,
        action_taken=action,
    )
