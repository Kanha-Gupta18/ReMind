"""Memory card routes: lifecycle, revisions, evidence, engagement (spec §7, §18, §39).

RBAC (spec §23):
  - patient        read approved/releasable only; may create manual memories; engage
  - contributor     create; read non-deleted
  - reviewer        full review lifecycle: submit/approve/reject/dispute/edit/archive
  - guardian        approve/submit/edit
  - caregiver       restrict, read evidence/revisions (support)
  - clinician       read evidence/revisions (support)
  - administrator   no patient-content access
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_patient_scope,
    require_consent_action,
    require_roles,
)
from app.core.database import get_db
from app.models.clinical import EngagementLog
from app.models.constants import (
    EngagementAction,
    ConsentAction,
    DeletionStatus,
    EvidenceReviewStatus,
    MemoryStatus,
    Role,
)
from app.models.knowledge import Event, Place
from app.models.memory import Evidence, MemoryCard
from app.models.people import Person
from app.models.user import User
from app.schemas.memory import (
    EngageAction,
    EvidenceReviewAction,
    MemoryCreate,
    MemoryEdit,
    ReviewAction,
)
from app.services import (
    audit_service,
    consent_service,
    evidence_service,
    memory_service,
    patient_delivery_service,
    safety_service,
)

router = APIRouter(prefix="/memories", tags=["memories"])

_REVIEW_ROLES = [Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value]
_READ_EVERYTHING = [Role.FAMILY_REVIEWER.value, Role.CAREGIVER.value,
                    Role.GUARDIAN.value, Role.CLINICIAN.value]


def _patient_from_scope(scope: str | None, memory: MemoryCard) -> None:
    """403 unless the caller may operate on this memory's patient."""
    if scope is None or scope == memory.patient_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access to this memory is not allowed")


def _require_memory_action(
    db: Session,
    current: User,
    memory: MemoryCard,
    action: ConsentAction,
) -> None:
    require_consent_action(db, current, memory.patient_id, action)
    if not consent_service.content_categories_are_allowed(
        db,
        memory.patient_id,
        memory.sensitivity_flags,
    ):
        raise HTTPException(status_code=403, detail="Consent prohibits this content category")


@router.get("")
def list_memories(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    mem_status: str | None = None,
):
    """List memories in the caller's scope. Patients only ever see what
    passes the safety release gate (approved + releasable)."""
    require_consent_action(db, current, scope, ConsentAction.MEMORIES_VIEW)
    memories = memory_service.list_memories(
        db, scope, status=mem_status, include_deleted=False
    ) if scope else []
    out = []
    for m in memories:
        if not consent_service.content_categories_are_allowed(db, m.patient_id, m.sensitivity_flags):
            continue
        if _is_patient_viewer(current, m):
            allowed = safety_service.evaluate_release(
                m, safety_service.resolve_safety_level(db, m.patient_id)
            )["allowed"]
            if not allowed:
                continue
        out.append(_serialize(db, m, detail=False, patient_view=_is_patient_viewer(current, m)))
    return {"items": out, "count": len(out)}


def _is_patient_viewer(current: User, memory: MemoryCard) -> bool:
    return current.role == Role.PATIENT.value and memory.patient_id == current.id


@router.get("/{memory_id}")
def get_memory(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = memory_service.get_memory(db, memory_id)
    if memory is None or memory.status == MemoryStatus.DELETED.value:
        raise HTTPException(status_code=404, detail="Memory not found")
    _patient_from_scope(scope, memory)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_VIEW)

    if _is_patient_viewer(current, memory):
        result = safety_service.evaluate_release(
            memory, safety_service.resolve_safety_level(db, memory.patient_id)
        )
        if not result["allowed"]:
            raise HTTPException(status_code=403, detail=result["reason"])
    return _serialize(db, memory, detail=True, patient_view=_is_patient_viewer(current, memory))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_memory(
    body: MemoryCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(
        Role.PATIENT.value, Role.FAMILY_CONTRIBUTOR.value,
        Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value,
    ))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    patient_id = scope
    require_consent_action(db, current, patient_id, ConsentAction.MEMORIES_CREATE)
    if not consent_service.content_categories_are_allowed(
        db,
        patient_id,
        body.sensitivity_flags,
    ):
        raise HTTPException(status_code=403, detail="Consent prohibits this content category")
    try:
        memory = memory_service.create_memory_card(
            db,
            patient_id=patient_id,
            title=body.title,
            narrative=body.narrative,
            memory_date=body.memory_date,
            date_accuracy=body.date_accuracy,
            tags=body.tags,
            sensitivity_flags=body.sensitivity_flags,
            media_urls=body.media_urls,
            visibility=body.visibility,
            people_ids=body.people_ids,
            place_ids=body.place_ids,
            event_ids=body.event_ids,
            status=MemoryStatus.DRAFT.value,
            created_by=current.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _serialize(db, memory, detail=True)


@router.post("/{memory_id}/submit")
def submit_memory(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_REVIEW)
    try:
        memory_service.submit_for_review(db, memory, submitted_by=current.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/approve")
def approve_memory(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_REVIEW)
    try:
        memory_service.approve_memory(db, memory, reviewer=current.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/reject")
def reject_memory(
    memory_id: str,
    body: ReviewAction,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_REVIEW)
    try:
        memory_service.reject_memory(db, memory, reviewer=current.id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/dispute")
def dispute_memory(
    memory_id: str,
    body: ReviewAction,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_REVIEW)
    try:
        memory_service.dispute_memory(db, memory, reviewer=current.id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/restrict")
def restrict_memory(
    memory_id: str,
    body: ReviewAction,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(
        Role.CAREGIVER.value, Role.GUARDIAN.value,
        Role.CLINICIAN.value,
    ))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.SAFETY_MANAGE)
    memory_service.restrict_memory(db, memory, actor=current.id, reason=body.reason)
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/archive")
def archive_memory(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_REVIEW)
    memory_service.archive_memory(db, memory, actor=current.id)
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/delete")
def soft_delete_memory(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_EDIT)
    memory.status = MemoryStatus.DELETED.value
    audit_service.log_action(db, current.id, "deleted", "memory_card", memory.id)
    db.commit()
    return {"ok": True}


@router.patch("/{memory_id}")
def edit_memory(
    memory_id: str,
    body: MemoryEdit,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_EDIT)
    changes = body.model_dump(exclude_unset=True)
    note = changes.pop("note", None)
    try:
        memory_service.edit_memory(
            db, memory, actor=current.id, changes=changes, note=note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _serialize(db, memory, detail=True)


@router.get("/{memory_id}/revisions")
def get_revisions(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_READ_EVERYTHING))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_VIEW)
    revisions = memory_service.revision_history(db, memory.id)
    reviews_by_revision: dict[str, list] = {}
    for review in memory_service.review_history(db, memory.id):
        reviews_by_revision.setdefault(review.revision_id, []).append(review)
    return {"items": [
        {"id": r.id, "revision_number": r.revision_number, "status": r.status,
         "content": r.content, "authored_by": r.authored_by,
         "change_note": r.change_note,
         "is_approved": r.id == memory.approved_revision_id,
         "is_candidate": r.id == memory.candidate_revision_id,
         "reviews": [
             {"id": item.id, "decision": item.decision, "reason": item.reason,
              "actor_id": item.actor_id, "created_at": item.created_at.isoformat()}
             for item in reviews_by_revision.get(r.id, [])
         ],
         "created_at": r.created_at.isoformat()}
        for r in revisions
    ]}


@router.get("/{memory_id}/evidence")
def get_evidence(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_VIEW)
    _require_release(db, memory, current)
    provenance = evidence_service.get_memory_provenance(db, memory.id)
    if current.role == Role.PATIENT.value:
        provenance = [p for p in provenance
                      if p["evidence"].review_status == EvidenceReviewStatus.ACCEPTED.value
                      and (not p["evidence"].source_id or
                           (p["source"] and p["source"].patient_id == memory.patient_id
                            and p["source"].deletion_status == DeletionStatus.ACTIVE.value))]
    return {"items": [
        {"id": p["evidence"].id,
         "claim": p["evidence"].claim,
         "evidence_type": p["evidence"].evidence_type,
         "confidence": p["evidence"].confidence,
         "review_status": p["evidence"].review_status,
         "revision_id": p["evidence"].revision_id,
         "reviewed_by": p["evidence"].reviewed_by,
         "reviewed_at": (p["evidence"].reviewed_at.isoformat()
                         if p["evidence"].reviewed_at else None),
         "source_file": p["source"].file_name if p["source"] else None}
        for p in provenance
    ]}


@router.post("/{memory_id}/evidence/{evidence_id}/review")
def review_evidence(
    memory_id: str,
    evidence_id: str,
    body: EvidenceReviewAction,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    _require_memory_action(db, current, memory, ConsentAction.MEMORIES_REVIEW)
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.memory_id != memory.id:
        raise HTTPException(status_code=404, detail="Evidence not found")
    evidence_service.update_evidence_review(db, evidence.id, body.status, current.id)
    audit_service.log_action(
        db, current.id, body.status.lower(), "evidence", evidence.id,
        {"memory_id": memory.id, "revision_id": evidence.revision_id},
    )
    db.commit()
    return {
        "id": evidence.id, "review_status": evidence.review_status,
        "reviewed_by": evidence.reviewed_by,
        "reviewed_at": evidence.reviewed_at.isoformat(),
    }


@router.post("/{memory_id}/engage")
def engage(
    memory_id: str,
    body: EngageAction,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.PATIENT.value))],
):
    memory = memory_service.get_memory(db, memory_id)
    if memory is None or memory.patient_id != current.id:
        raise HTTPException(status_code=403, detail="Not your memory")
    require_consent_action(db, current, memory.patient_id, ConsentAction.MEMORIES_VIEW)
    _require_release(db, memory, current)
    log = EngagementLog(
        patient_id=current.id, memory_card_id=memory.id,
        action=body.action, duration_ms=body.duration_ms,
    )
    db.add(log)
    db.commit()
    return {"ok": True, "action": body.action}


def _get_scoped(db: Session, memory_id: str, scope: str | None) -> MemoryCard:
    memory = memory_service.get_memory(db, memory_id)
    if memory is None or memory.status == MemoryStatus.DELETED.value:
        raise HTTPException(status_code=404, detail="Memory not found")
    _patient_from_scope(scope, memory)
    return memory


def _require_release(db: Session, memory: MemoryCard, current: User) -> None:
    if current.role == Role.PATIENT.value and not patient_delivery_service.memory_is_visible(db, memory):
        raise HTTPException(status_code=403, detail="Memory is not available to the patient")


def _serialize(
    db: Session, m: MemoryCard, detail: bool, patient_view: bool = False,
) -> dict:
    content = (
        memory_service.content_for_delivery(db, m)
        if patient_view else memory_service.content_for_review(db, m)
    ) or {}
    data = {
        "id": m.id,
        "patient_id": m.patient_id,
        "title": content.get("title", m.title),
        "status": MemoryStatus.APPROVED.value if patient_view else m.status,
        "visibility": content.get("visibility", m.visibility),
        "date_accuracy": content.get("date_accuracy", m.date_accuracy),
        "confidence_score": content.get("confidence_score", m.confidence_score),
        "confidence_band": ((content.get("confidence_breakdown") or {}).get("band")),
        "explanation": content.get("explanation", m.explanation),
        "sensitivity_flags": content.get("sensitivity_flags", m.sensitivity_flags or []),
        "tags": content.get("tags", m.tags or []),
        "memory_date": content.get("memory_date"),
        "created_by": m.created_by,
        "approved_by": m.approved_by,
        "approved_at": m.approved_at.isoformat() if m.approved_at else None,
        "created_at": m.created_at.isoformat(),
        "structured_context": _structured_context(db, content, patient_view),
    }
    if not patient_view:
        data.update({
            "approved_revision_id": m.approved_revision_id,
            "candidate_revision_id": m.candidate_revision_id,
            "has_pending_revision": m.candidate_revision_id is not None,
        })
    if detail:
        data.update({
            "narrative": content.get("narrative"),
            "media_urls": content.get("media_urls", []),
            "contradictions": content.get("contradictions", []),
            "confidence_breakdown": content.get("confidence_breakdown"),
            "model_version": content.get("model_version"),
        })
    return data


def _structured_context(db: Session, content: dict, patient_view: bool) -> dict:
    people = (
        db.query(Person).filter(Person.id.in_(content.get("people_ids") or [])).all()
        if content.get("people_ids") else []
    )
    if patient_view:
        people = [
            person for person in people
            if patient_delivery_service.person_is_visible(db, person)
        ]
    places = (
        db.query(Place).filter(Place.id.in_(content.get("place_ids") or [])).all()
        if content.get("place_ids") else []
    )
    events = (
        db.query(Event).filter(Event.id.in_(content.get("event_ids") or [])).all()
        if content.get("event_ids") else []
    )
    return {
        "people": [{"id": item.id, "name": item.name} for item in people],
        "places": [{"id": item.id, "name": item.name} for item in places],
        "events": [{"id": item.id, "name": item.name} for item in events],
    }
