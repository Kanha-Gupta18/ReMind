"""Evidence management and provenance (spec §18.4, §5.1.2).

Evidence is the first-class proof behind a memory: each row references a
source, asserts a claim, and carries its own confidence + review status.
The provenance trail lets anyone answer 'why does this memory say X?' by
joining evidence -> sources -> pipeline results.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.constants import EvidenceReviewStatus, EvidenceType
from app.models.base import utcnow
from app.models.memory import Evidence, MemoryCard, Source


def add_evidence(
    db: Session,
    memory_id: str,
    source_id: str,
    evidence_type: str,
    claim: str,
    confidence: float | None = None,
    extractor_version: str | None = None,
    revision_id: str | None = None,
) -> Evidence:
    """Record one piece of evidence for a memory (status PENDING)."""
    if revision_id is None:
        memory = db.get(MemoryCard, memory_id)
        if memory is not None:
            revision_id = memory.candidate_revision_id or memory.approved_revision_id
    ev = Evidence(
        memory_id=memory_id,
        revision_id=revision_id,
        source_id=source_id,
        evidence_type=evidence_type,
        claim=claim,
        confidence=confidence,
        extractor_version=extractor_version,
        review_status=EvidenceReviewStatus.PENDING.value,
    )
    db.add(ev)
    db.flush()
    return ev


def update_evidence_review(
    db: Session, evidence_id: str, review_status: str, reviewed_by: str,
) -> Evidence:
    """Reviewer accepts, rejects, or disputes a piece of evidence."""
    ev = db.get(Evidence, evidence_id)
    if ev is None:
        raise ValueError(f"Evidence {evidence_id} not found")
    ev.review_status = review_status
    ev.reviewed_by = reviewed_by
    ev.reviewed_at = utcnow()
    db.flush()
    return ev


def get_evidence_for_memory(db: Session, memory_id: str) -> list[Evidence]:
    return (
        db.query(Evidence)
        .filter(Evidence.memory_id == memory_id)
        .order_by(Evidence.created_at)
        .all()
    )


def independent_source_count(db: Session, memory_id: str) -> int:
    """Number of distinct sources backing a memory (feeds §8.2
    source_corroboration score)."""
    return (
        db.query(func.count(func.distinct(Evidence.source_id)))
        .filter(Evidence.memory_id == memory_id, Evidence.source_id.isnot(None))
        .scalar()
        or 0
    )


def get_memory_provenance(db: Session, memory_id: str) -> list[dict]:
    """Full traceability: each evidence row joined to its source.

    Returns [{evidence, source}] so any client can walk from a memory
    back to the raw uploaded files and their provenance (§5.1.2).
    """
    evidence_rows = get_evidence_for_memory(db, memory_id)
    source_ids = {ev.source_id for ev in evidence_rows if ev.source_id}
    sources = (
        db.query(Source).filter(Source.id.in_(source_ids)).all() if source_ids else []
    )
    source_map = {s.id: s for s in sources}
    return [
        {"evidence": ev, "source": source_map.get(ev.source_id)}
        for ev in evidence_rows
    ]
