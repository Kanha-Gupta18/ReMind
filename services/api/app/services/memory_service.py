"""Memory card lifecycle, revisions, and audit (spec §7.3, §39, §5).

Status lifecycle (§7.3):
  DRAFT -> AI_RECONSTRUCTED (pipeline finished)
  AI_RECONSTRUCTED -> AWAITING_REVIEW (submitted for family review)
  AWAITING_REVIEW -> APPROVED | DISPUTED | REJECTED
  APPROVED -> ARCHIVED | DISPUTED | DELETED
  DISPUTED -> AWAITING_REVIEW (re-review) | REJECTED
  RESTRICTED -> from any state by a support role

Every state change is written to the append-only audit log (§24) and
content edits go through MemoryRevision so the full history survives
(§39). Approved content is only ever read from the latest approved
revision.
"""

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.constants import (
    MemoryStatus,
    NotificationType,
    RevisionStatus,
)
from app.models.memory import MemoryCard, MemoryRevision
from app.services import audit_service, notification_service


def _audit(db, user_id, action, resource_id, details=None):
    audit_service.log_action(
        db, user_id=user_id, action=action,
        resource_type="memory_card", resource_id=resource_id,
        details=details,
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def create_memory_card(
    db: Session,
    patient_id: str,
    title: str,
    narrative: str | None = None,
    media_urls: list | None = None,
    memory_date=None,
    date_accuracy: str | None = None,
    confidence_score: int = 0,
    confidence_breakdown: dict | None = None,
    explanation: str | None = None,
    contradictions: list | None = None,
    sensitivity_flags: list | None = None,
    tags: list | None = None,
    status: str = MemoryStatus.DRAFT.value,
    model_version: str | None = None,
    created_by: str | None = None,
) -> MemoryCard:
    memory = MemoryCard(
        patient_id=patient_id,
        title=title,
        narrative=narrative,
        media_urls=media_urls or [],
        tags=tags or [],
        memory_date=memory_date,
        date_accuracy=date_accuracy,
        confidence_score=confidence_score,
        confidence_breakdown=confidence_breakdown,
        explanation=explanation,
        contradictions=contradictions or [],
        sensitivity_flags=sensitivity_flags or [],
        status=status,
        model_version=model_version,
        created_by=created_by,
    )
    db.add(memory)
    db.flush()
    create_revision(db, memory, created_by, "initial draft")
    _audit(db, created_by, "created", memory.id, {"title": title})
    return memory


# ---------------------------------------------------------------------------
# Revisions (§39)
# ---------------------------------------------------------------------------


def create_revision(
    db: Session,
    memory: MemoryCard,
    authored_by: str | None,
    note: str | None = None,
) -> MemoryRevision:
    current = (
        db.query(MemoryRevision)
        .filter(MemoryRevision.memory_id == memory.id)
        .order_by(MemoryRevision.revision_number.desc())
        .first()
    )
    number = (current.revision_number if current else 0) + 1
    revision = MemoryRevision(
        memory_id=memory.id,
        revision_number=number,
        content={
            "title": memory.title,
            "narrative": memory.narrative,
            "media_urls": memory.media_urls or [],
            "note": note,
        },
        status=RevisionStatus.DRAFT.value,
        authored_by=authored_by,
    )
    db.add(revision)
    db.flush()
    return revision


# ---------------------------------------------------------------------------
# Lifecycle transitions (§7.3)
# ---------------------------------------------------------------------------


def submit_for_review(db: Session, memory: MemoryCard, submitted_by: str | None = None) -> MemoryCard:
    """AI draft -> AWAITING_REVIEW; notifies all family reviewers."""
    if memory.status not in (MemoryStatus.DRAFT.value, MemoryStatus.AI_RECONSTRUCTED.value):
        raise ValueError(f"cannot submit memory in state {memory.status}")
    memory.status = MemoryStatus.AWAITING_REVIEW.value
    db.flush()
    notification_service.notify_review_needed(db, memory)
    _audit(db, submitted_by, "submitted_for_review", memory.id)
    return memory


def approve_memory(db: Session, memory: MemoryCard, reviewer: str) -> MemoryCard:
    """AWAITING_REVIEW -> APPROVED; approves the pending revision."""
    if memory.status != MemoryStatus.AWAITING_REVIEW.value:
        raise ValueError(f"only AWAITING_REVIEW memories can be approved (state {memory.status})")
    memory.status = MemoryStatus.APPROVED.value
    memory.approved_by = reviewer
    memory.approved_at = utcnow()
    db.flush()

    revision = (
        db.query(MemoryRevision)
        .filter(
            MemoryRevision.memory_id == memory.id,
            MemoryRevision.status == RevisionStatus.DRAFT.value,
        )
        .order_by(MemoryRevision.revision_number.desc())
        .first()
    )
    if revision:
        revision.status = RevisionStatus.APPROVED.value
        db.flush()
    _audit(db, reviewer, "approved", memory.id)
    return memory


def reject_memory(
    db: Session, memory: MemoryCard, reviewer: str, reason: str | None = None
) -> MemoryCard:
    if memory.status not in (MemoryStatus.AWAITING_REVIEW.value, MemoryStatus.DISPUTED.value):
        raise ValueError(f"cannot reject memory in state {memory.status}")
    memory.status = MemoryStatus.REJECTED.value
    db.flush()
    _audit(db, reviewer, "rejected", memory.id, {"reason": reason})
    return memory


def dispute_memory(
    db: Session, memory: MemoryCard, reviewer: str, reason: str | None = None
) -> MemoryCard:
    """APPROVED or AWAITING_REVIEW -> DISPUTED; notifies reviewers."""
    if memory.status not in (
        MemoryStatus.APPROVED.value,
        MemoryStatus.AWAITING_REVIEW.value,
        MemoryStatus.REJECTED.value,
    ):
        raise ValueError(f"cannot dispute memory in state {memory.status}")
    memory.status = MemoryStatus.DISPUTED.value
    db.flush()
    notification_service.notify_dispute_flagged(db, memory.patient_id, memory.title)
    _audit(db, reviewer, "disputed", memory.id, {"reason": reason})
    return memory


def restrict_memory(
    db: Session, memory: MemoryCard, actor: str, reason: str | None = None
) -> MemoryCard:
    """Support role hides a memory from patient-facing surfaces (§16)."""
    memory.status = MemoryStatus.RESTRICTED.value
    db.flush()
    _audit(db, actor, "restricted", memory.id, {"reason": reason})
    return memory


def archive_memory(db: Session, memory: MemoryCard, actor: str) -> MemoryCard:
    memory.status = MemoryStatus.ARCHIVED.value
    db.flush()
    _audit(db, actor, "archived", memory.id)
    return memory


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_memory(db: Session, memory_id: str) -> MemoryCard | None:
    return db.get(MemoryCard, memory_id)


def list_memories(
    db: Session,
    patient_id: str,
    status: str | None = None,
    approved_only: bool = False,
    include_deleted: bool = False,
) -> list[MemoryCard]:
    query = db.query(MemoryCard).filter(MemoryCard.patient_id == patient_id)
    if status:
        query = query.filter(MemoryCard.status == status)
    if approved_only and not status:
        query = query.filter(MemoryCard.status == MemoryStatus.APPROVED.value)
    if not include_deleted:
        query = query.filter(MemoryCard.status != MemoryStatus.DELETED.value)
    return query.order_by(MemoryCard.created_at.desc()).all()


def edit_memory(
    db: Session,
    memory: MemoryCard,
    actor: str,
    title: str | None = None,
    narrative: str | None = None,
    tags: list | None = None,
    note: str | None = None,
) -> MemoryCard:
    """Apply an edit as a new revision; content only changes on approval.

    The edit lands in a fresh DRAFT revision; approve_memory promotes it
    to APPROVED, making the change live while preserving the old revision
    (§39).
    """
    previous = (
        db.query(MemoryRevision)
        .filter(
            MemoryRevision.memory_id == memory.id,
            MemoryRevision.status == RevisionStatus.APPROVED.value,
        )
        .order_by(MemoryRevision.revision_number.desc())
        .first()
    )
    revision = create_revision(db, memory, actor, note=note)
    if previous:
        previous.status = RevisionStatus.SUPERSEDED.value
        previous.superseded_by_id = revision.id
        db.flush()

    if title:
        memory.title = title
    if narrative is not None:
        memory.narrative = narrative
    if tags is not None:
        memory.tags = tags
    memory.status = MemoryStatus.AWAITING_REVIEW.value
    db.flush()
    notification_service.notify_review_needed(db, memory)
    _audit(db, actor, "edited", memory.id, {"note": note})
    return memory


def revision_history(db: Session, memory_id: str) -> list[MemoryRevision]:
    return (
        db.query(MemoryRevision)
        .filter(MemoryRevision.memory_id == memory_id)
        .order_by(MemoryRevision.revision_number)
        .all()
    )
