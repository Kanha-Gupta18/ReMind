"""Memory lifecycle, immutable content revisions, and review records."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.constants import (
    DateAccuracy,
    MemoryStatus,
    ReviewDecision,
    RevisionStatus,
    Visibility,
)
from app.models.knowledge import (
    Event,
    MemoryEventLink,
    MemoryPersonLink,
    MemoryPlaceLink,
    Place,
)
from app.models.memory import MemoryCard, MemoryReviewRecord, MemoryRevision
from app.models.people import Person
from app.services import audit_service, notification_service


REVISION_FIELDS = {
    "title", "narrative", "media_urls", "people_ids", "place_ids",
    "event_ids", "tags", "memory_date", "date_accuracy", "visibility",
    "sensitivity_flags", "confidence_score", "confidence_breakdown",
    "explanation", "contradictions", "model_version",
}


def _audit(db, user_id, action, resource_id, details=None):
    audit_service.log_action(
        db, user_id=user_id, action=action, resource_type="memory_card",
        resource_id=resource_id, details=details,
    )


def _linked_ids(db: Session, model, column, memory_id: str) -> list[str]:
    return [row[0] for row in db.query(column).filter(model.memory_id == memory_id).all()]


def _snapshot(db: Session, memory: MemoryCard) -> dict:
    return {
        "title": memory.title,
        "narrative": memory.narrative,
        "media_urls": list(memory.media_urls or []),
        "people_ids": _linked_ids(db, MemoryPersonLink, MemoryPersonLink.person_id, memory.id),
        "place_ids": _linked_ids(db, MemoryPlaceLink, MemoryPlaceLink.place_id, memory.id),
        "event_ids": _linked_ids(db, MemoryEventLink, MemoryEventLink.event_id, memory.id),
        "tags": list(memory.tags or []),
        "memory_date": memory.memory_date.isoformat() if memory.memory_date else None,
        "date_accuracy": memory.date_accuracy,
        "visibility": memory.visibility,
        "sensitivity_flags": list(memory.sensitivity_flags or []),
        "confidence_score": memory.confidence_score or 0,
        "confidence_breakdown": memory.confidence_breakdown,
        "explanation": memory.explanation,
        "contradictions": list(memory.contradictions or []),
        "model_version": memory.model_version,
    }


def _normalise_content(content: dict) -> dict:
    normalised = dict(content)
    memory_date = normalised.get("memory_date")
    if isinstance(memory_date, date):
        normalised["memory_date"] = memory_date.isoformat()
    for field in (
        "media_urls", "people_ids", "place_ids", "event_ids", "tags",
        "sensitivity_flags", "contradictions",
    ):
        normalised[field] = list(normalised.get(field) or [])
    return normalised


def _validate_ids(db: Session, patient_id: str, model, ids: list[str], label: str) -> None:
    if not ids:
        return
    found = {
        item.id
        for item in db.query(model).filter(
            model.id.in_(set(ids)), model.patient_id == patient_id
        ).all()
    }
    missing = sorted(set(ids) - found)
    if missing:
        raise ValueError(f"Unknown {label} for this patient: {', '.join(missing)}")


def validate_structured_context(db: Session, patient_id: str, content: dict) -> None:
    _validate_ids(db, patient_id, Person, content.get("people_ids") or [], "people")
    _validate_ids(db, patient_id, Place, content.get("place_ids") or [], "places")
    _validate_ids(db, patient_id, Event, content.get("event_ids") or [], "events")


def _replace_links(db: Session, memory: MemoryCard, content: dict) -> None:
    for model in (MemoryPersonLink, MemoryPlaceLink, MemoryEventLink):
        db.query(model).filter(model.memory_id == memory.id).delete(
            synchronize_session=False
        )
    db.add_all(
        [MemoryPersonLink(memory_id=memory.id, person_id=item) for item in content["people_ids"]]
        + [MemoryPlaceLink(memory_id=memory.id, place_id=item) for item in content["place_ids"]]
        + [MemoryEventLink(memory_id=memory.id, event_id=item) for item in content["event_ids"]]
    )
    people = (
        db.query(Person).filter(Person.id.in_(content["people_ids"])).all()
        if content["people_ids"] else []
    )
    people_by_id = {person.id: person.name for person in people}
    memory.people_identified = [
        people_by_id[item] for item in content["people_ids"] if item in people_by_id
    ]


def _apply_content(
    db: Session, memory: MemoryCard, content: dict, *, update_links: bool,
) -> None:
    content = _normalise_content(content)
    memory.title = content["title"]
    memory.narrative = content.get("narrative")
    memory.media_urls = content["media_urls"]
    memory.tags = content["tags"]
    memory.memory_date = (
        date.fromisoformat(content["memory_date"]) if content.get("memory_date") else None
    )
    memory.date_accuracy = content.get("date_accuracy") or DateAccuracy.APPROXIMATE.value
    memory.visibility = content.get("visibility") or Visibility.BOTH.value
    memory.sensitivity_flags = content["sensitivity_flags"]
    memory.confidence_score = content.get("confidence_score") or 0
    memory.confidence_breakdown = content.get("confidence_breakdown")
    memory.explanation = content.get("explanation")
    memory.contradictions = content["contradictions"]
    memory.model_version = content.get("model_version")
    if update_links:
        _replace_links(db, memory, content)


def get_revision(db: Session, revision_id: str | None) -> MemoryRevision | None:
    return db.get(MemoryRevision, revision_id) if revision_id else None


def approved_revision(db: Session, memory: MemoryCard) -> MemoryRevision | None:
    return get_revision(db, memory.approved_revision_id)


def candidate_revision(db: Session, memory: MemoryCard) -> MemoryRevision | None:
    return get_revision(db, memory.candidate_revision_id)


def content_for_delivery(db: Session, memory: MemoryCard) -> dict | None:
    revision = approved_revision(db, memory)
    return _normalise_content(revision.content) if revision and revision.content else None


def content_for_review(db: Session, memory: MemoryCard) -> dict:
    revision = candidate_revision(db, memory) or approved_revision(db, memory)
    if revision and revision.content:
        return _normalise_content(revision.content)
    return _snapshot(db, memory)


def _record_review(
    db: Session, memory: MemoryCard, revision: MemoryRevision, decision: str,
    actor_id: str | None, reason: str | None = None,
) -> MemoryReviewRecord:
    record = MemoryReviewRecord(
        memory_id=memory.id, revision_id=revision.id, decision=decision,
        reason=reason, actor_id=actor_id,
    )
    db.add(record)
    db.flush()
    return record


def create_memory_card(
    db: Session, patient_id: str, title: str, narrative: str | None = None,
    media_urls: list | None = None, memory_date=None,
    date_accuracy: str | None = None, confidence_score: int = 0,
    confidence_breakdown: dict | None = None, explanation: str | None = None,
    contradictions: list | None = None, sensitivity_flags: list | None = None,
    tags: list | None = None, visibility: str = Visibility.BOTH.value,
    people_ids: list[str] | None = None, place_ids: list[str] | None = None,
    event_ids: list[str] | None = None, status: str = MemoryStatus.DRAFT.value,
    model_version: str | None = None, created_by: str | None = None,
) -> MemoryCard:
    memory = MemoryCard(
        patient_id=patient_id, title=title, narrative=narrative,
        media_urls=media_urls or [], tags=tags or [], memory_date=memory_date,
        date_accuracy=date_accuracy or DateAccuracy.APPROXIMATE.value,
        confidence_score=confidence_score, confidence_breakdown=confidence_breakdown,
        explanation=explanation, contradictions=contradictions or [],
        sensitivity_flags=sensitivity_flags or [], visibility=visibility,
        status=status, model_version=model_version, created_by=created_by,
    )
    db.add(memory)
    db.flush()
    content = _snapshot(db, memory)
    content.update(
        people_ids=list(people_ids or []), place_ids=list(place_ids or []),
        event_ids=list(event_ids or []),
    )
    validate_structured_context(db, patient_id, content)
    revision = create_revision(db, memory, created_by, content, "Initial draft")
    memory.candidate_revision_id = revision.id
    db.flush()
    _audit(db, created_by, "created", memory.id, {"title": title})
    return memory


def create_revision(
    db: Session, memory: MemoryCard, authored_by: str | None,
    content: dict, note: str | None = None,
) -> MemoryRevision:
    latest_number = (
        db.query(MemoryRevision.revision_number)
        .filter(MemoryRevision.memory_id == memory.id)
        .order_by(MemoryRevision.revision_number.desc())
        .scalar() or 0
    )
    revision = MemoryRevision(
        memory_id=memory.id, revision_number=latest_number + 1,
        content=_normalise_content(content), change_note=note,
        status=RevisionStatus.DRAFT.value, authored_by=authored_by,
    )
    db.add(revision)
    db.flush()
    return revision


def submit_for_review(
    db: Session, memory: MemoryCard, submitted_by: str | None = None,
) -> MemoryCard:
    revision = candidate_revision(db, memory)
    if revision is None or revision.status != RevisionStatus.DRAFT.value:
        raise ValueError("memory has no draft revision to submit")
    revision.status = RevisionStatus.AWAITING_REVIEW.value
    memory.status = MemoryStatus.AWAITING_REVIEW.value
    _record_review(db, memory, revision, ReviewDecision.SUBMITTED.value, submitted_by)
    notification_service.notify_review_needed(db, memory)
    _audit(db, submitted_by, "submitted_for_review", memory.id,
           {"revision_id": revision.id})
    return memory


def approve_memory(db: Session, memory: MemoryCard, reviewer: str) -> MemoryCard:
    revision = candidate_revision(db, memory)
    if (
        memory.status != MemoryStatus.AWAITING_REVIEW.value
        or revision is None
        or revision.status != RevisionStatus.AWAITING_REVIEW.value
    ):
        raise ValueError("memory has no submitted revision to approve")
    content = _normalise_content(revision.content or {})
    validate_structured_context(db, memory.patient_id, content)
    previous = approved_revision(db, memory)
    if previous is not None and previous.id != revision.id:
        previous.status = RevisionStatus.SUPERSEDED.value
        previous.superseded_by_id = revision.id
    revision.status = RevisionStatus.APPROVED.value
    memory.approved_revision_id = revision.id
    memory.candidate_revision_id = None
    _apply_content(db, memory, content, update_links=True)
    memory.status = MemoryStatus.APPROVED.value
    memory.approved_by = reviewer
    memory.approved_at = utcnow()
    _record_review(db, memory, revision, ReviewDecision.APPROVED.value, reviewer)
    _audit(db, reviewer, "approved", memory.id, {"revision_id": revision.id})
    return memory


def reject_memory(
    db: Session, memory: MemoryCard, reviewer: str, reason: str | None = None,
) -> MemoryCard:
    revision = candidate_revision(db, memory)
    if (
        memory.status != MemoryStatus.AWAITING_REVIEW.value
        or revision is None
        or revision.status != RevisionStatus.AWAITING_REVIEW.value
    ):
        raise ValueError("memory has no submitted revision to reject")
    revision.status = RevisionStatus.REJECTED.value
    memory.candidate_revision_id = None
    memory.status = (
        MemoryStatus.APPROVED.value if memory.approved_revision_id
        else MemoryStatus.REJECTED.value
    )
    _record_review(db, memory, revision, ReviewDecision.REJECTED.value, reviewer, reason)
    _audit(db, reviewer, "rejected", memory.id,
           {"revision_id": revision.id, "reason": reason})
    return memory


def dispute_memory(
    db: Session, memory: MemoryCard, reviewer: str, reason: str | None = None,
) -> MemoryCard:
    revision = candidate_revision(db, memory) or approved_revision(db, memory)
    if revision is None or memory.status not in {
        MemoryStatus.APPROVED.value, MemoryStatus.AWAITING_REVIEW.value,
    }:
        raise ValueError(f"cannot dispute memory in state {memory.status}")
    revision.status = RevisionStatus.DISPUTED.value
    memory.status = MemoryStatus.DISPUTED.value
    _record_review(db, memory, revision, ReviewDecision.DISPUTED.value, reviewer, reason)
    notification_service.notify_dispute_flagged(db, memory.patient_id, memory.title)
    _audit(db, reviewer, "disputed", memory.id,
           {"revision_id": revision.id, "reason": reason})
    return memory


def restrict_memory(
    db: Session, memory: MemoryCard, actor: str, reason: str | None = None,
) -> MemoryCard:
    memory.status = MemoryStatus.RESTRICTED.value
    _audit(db, actor, "restricted", memory.id, {"reason": reason})
    return memory


def archive_memory(db: Session, memory: MemoryCard, actor: str) -> MemoryCard:
    memory.status = MemoryStatus.ARCHIVED.value
    _audit(db, actor, "archived", memory.id)
    return memory


def get_memory(db: Session, memory_id: str) -> MemoryCard | None:
    return db.get(MemoryCard, memory_id)


def list_memories(
    db: Session, patient_id: str, status: str | None = None,
    approved_only: bool = False, include_deleted: bool = False,
) -> list[MemoryCard]:
    query = db.query(MemoryCard).filter(MemoryCard.patient_id == patient_id)
    if status:
        query = query.filter(MemoryCard.status == status)
    if approved_only and not status:
        query = query.filter(MemoryCard.approved_revision_id.isnot(None))
    if not include_deleted:
        query = query.filter(MemoryCard.status != MemoryStatus.DELETED.value)
    return query.order_by(MemoryCard.created_at.desc()).all()


def edit_memory(
    db: Session, memory: MemoryCard, actor: str, changes: dict,
    note: str | None = None,
) -> MemoryCard:
    current_candidate = candidate_revision(db, memory)
    if (
        current_candidate is not None
        and current_candidate.status == RevisionStatus.AWAITING_REVIEW.value
    ):
        raise ValueError("the submitted candidate must be reviewed before another edit")
    base = content_for_review(db, memory)
    candidate_content = dict(base)
    candidate_content.update(
        {key: value for key, value in changes.items() if key in REVISION_FIELDS}
    )
    candidate_content = _normalise_content(candidate_content)
    if not candidate_content.get("title") or not str(candidate_content["title"]).strip():
        raise ValueError("title cannot be empty")
    validate_structured_context(db, memory.patient_id, candidate_content)
    if current_candidate is not None:
        current_candidate.status = RevisionStatus.SUPERSEDED.value
    revision = create_revision(db, memory, actor, candidate_content, note)
    memory.candidate_revision_id = revision.id
    memory.status = MemoryStatus.DRAFT.value
    if memory.approved_revision_id is None:
        _apply_content(db, memory, candidate_content, update_links=False)
    _audit(db, actor, "edited", memory.id,
           {"revision_id": revision.id, "note": note})
    return memory


def revision_history(db: Session, memory_id: str) -> list[MemoryRevision]:
    return (
        db.query(MemoryRevision)
        .filter(MemoryRevision.memory_id == memory_id)
        .order_by(MemoryRevision.revision_number).all()
    )


def review_history(db: Session, memory_id: str) -> list[MemoryReviewRecord]:
    return (
        db.query(MemoryReviewRecord)
        .filter(MemoryReviewRecord.memory_id == memory_id)
        .order_by(MemoryReviewRecord.created_at, MemoryReviewRecord.id).all()
    )
