"""Memory card routes: lifecycle, revisions, evidence, engagement (spec §7, §18, §39).

RBAC (spec §23):
  - patient        read approved/releasable only; may create manual memories; engage
  - contributor     create; read non-deleted
  - reviewer        full review lifecycle: submit/approve/reject/dispute/edit/archive
  - guardian        approve/submit/edit
  - caregiver       restrict, read evidence/revisions (support)
  - clinician       read evidence/revisions (support)
  - administrator   everything
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_roles
from app.core.database import get_db
from app.models.clinical import EngagementLog
from app.models.constants import (
    EngagementAction,
    MemoryStatus,
    Role,
    Visibility,
)
from app.models.memory import MemoryCard
from app.models.user import User
from app.schemas.memory import EngageAction, MemoryCreate, MemoryEdit, ReviewAction
from app.services import audit_service, evidence_service, memory_service, safety_service

router = APIRouter(prefix="/memories", tags=["memories"])

_REVIEW_ROLES = [Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value, Role.ADMINISTRATOR.value]
_READ_EVERYTHING = [Role.FAMILY_REVIEWER.value, Role.CAREGIVER.value,
                    Role.GUARDIAN.value, Role.CLINICIAN.value, Role.ADMINISTRATOR.value]


def _patient_from_scope(scope: str | None, memory: MemoryCard) -> None:
    """403 unless the caller may operate on this memory's patient."""
    if scope is None or scope == memory.patient_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access to this memory is not allowed")


@router.get("")
def list_memories(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    mem_status: str | None = None,
):
    """List memories in the caller's scope. Patients only ever see what
    passes the safety release gate (approved + releasable)."""
    memories = memory_service.list_memories(
        db, scope, status=mem_status, include_deleted=False
    ) if scope else []
    out = []
    for m in memories:
        if _is_patient_viewer(current, m):
            allowed = safety_service.evaluate_release(
                m, safety_service.resolve_safety_level(db, m.patient_id)
            )["allowed"]
            if not allowed:
                continue
        out.append(_serialize(db, m, detail=False))
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
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    _patient_from_scope(scope, memory)

    if _is_patient_viewer(current, memory):
        result = safety_service.evaluate_release(
            memory, safety_service.resolve_safety_level(db, memory.patient_id)
        )
        if not result["allowed"]:
            raise HTTPException(status_code=403, detail=result["reason"])
    return _serialize(db, memory, detail=True)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_memory(
    body: MemoryCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(
        Role.PATIENT.value, Role.FAMILY_CONTRIBUTOR.value,
        Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value, Role.ADMINISTRATOR.value,
    ))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    patient_id = scope
    if patient_id is None:
        raise HTTPException(status_code=403, detail="Administrator must pick a patient")
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
        status=MemoryStatus.DRAFT.value,
        created_by=current.id,
    )
    memory.visibility = body.visibility or Visibility.BOTH.value
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
    memory_service.submit_for_review(db, memory, submitted_by=current.id)
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
    memory_service.approve_memory(db, memory, reviewer=current.id)
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
    memory_service.reject_memory(db, memory, reviewer=current.id, reason=body.reason)
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
    memory_service.dispute_memory(db, memory, reviewer=current.id, reason=body.reason)
    db.commit()
    return _serialize(db, memory, detail=False)


@router.post("/{memory_id}/restrict")
def restrict_memory(
    memory_id: str,
    body: ReviewAction,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(
        Role.CAREGIVER.value, Role.GUARDIAN.value,
        Role.CLINICIAN.value, Role.ADMINISTRATOR.value,
    ))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
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
    memory_service.edit_memory(
        db, memory, actor=current.id,
        title=body.title, narrative=body.narrative, tags=body.tags, note=body.note,
    )
    db.commit()
    return _serialize(db, memory, detail=True)


@router.get("/{memory_id}/revisions")
def get_revisions(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    revisions = memory_service.revision_history(db, memory.id)
    return {"items": [
        {"revision_number": r.revision_number, "status": r.status,
         "content": r.content, "authored_by": r.authored_by,
         "created_at": r.created_at.isoformat()}
        for r in revisions
    ]}


@router.get("/{memory_id}/evidence")
def get_evidence(
    memory_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    memory = _get_scoped(db, memory_id, scope)
    provenance = evidence_service.get_memory_provenance(db, memory.id)
    return {"items": [
        {"id": p["evidence"].id,
         "claim": p["evidence"].claim,
         "evidence_type": p["evidence"].evidence_type,
         "confidence": p["evidence"].confidence,
         "review_status": p["evidence"].review_status,
         "source_file": p["source"].file_name if p["source"] else None}
        for p in provenance
    ]}


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
    log = EngagementLog(
        patient_id=current.id, memory_card_id=memory.id,
        action=body.action, duration_ms=body.duration_ms,
    )
    db.add(log)
    db.commit()
    return {"ok": True, "action": body.action}


def _get_scoped(db: Session, memory_id: str, scope: str | None) -> MemoryCard:
    memory = memory_service.get_memory(db, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    _patient_from_scope(scope, memory)
    return memory


def _serialize(db: Session, m: MemoryCard, detail: bool) -> dict:
    data = {
        "id": m.id,
        "patient_id": m.patient_id,
        "title": m.title,
        "status": m.status,
        "visibility": m.visibility,
        "date_accuracy": m.date_accuracy,
        "confidence_score": m.confidence_score,
        "confidence_band": m.confidence_breakdown.get("band") if m.confidence_breakdown else None,
        "explanation": m.explanation,
        "sensitivity_flags": m.sensitivity_flags or [],
        "tags": m.tags or [],
        "memory_date": m.memory_date.isoformat() if m.memory_date else None,
        "created_by": m.created_by,
        "approved_by": m.approved_by,
        "approved_at": m.approved_at.isoformat() if m.approved_at else None,
        "created_at": m.created_at.isoformat(),
    }
    if detail:
        data.update({
            "narrative": m.narrative,
            "media_urls": m.media_urls or [],
            "contradictions": m.contradictions or [],
            "confidence_breakdown": m.confidence_breakdown,
            "model_version": m.model_version,
        })
    return data
