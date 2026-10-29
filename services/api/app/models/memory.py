"""Sources, memory cards, revisions, and evidence (spec §5, §7, §18, §39)."""

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import (
    DateAccuracy,
    DeletionStatus,
    EvidenceReviewStatus,
    MemoryStatus,
    SourceStatus,
    Visibility,
)


class Source(Base):
    """One raw file (photo, voice note, video, text export) uploaded by family.

    Processing flow: pending -> queued -> processing -> completed | failed.
    context_tags are the family's notes BEFORE AI runs
    ("these are from the 1990s", "this is his brother Ramesh").

    Provenance fields (spec §5.1.2) make every derived fact traceable:
    checksum, capture_date, extraction method, consent scope, and a soft
    deletion_status.
    """

    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)

    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # photo|video|audio|document|message_export
    file_size = Column(Integer, nullable=True)
    storage_path = Column(String, nullable=True)  # v1: local disk; later: S3 key

    status = Column(String, default=SourceStatus.PENDING.value)
    pipeline_type = Column(String, nullable=True)  # vision|speech|nlp|location

    context_tags = Column(JSON, default=list)
    pipeline_results = Column(JSON, nullable=True)

    # Provenance (§5.1.2)
    checksum = Column(String, nullable=True)
    capture_date = Column(Date, nullable=True)
    extraction_method = Column(String, nullable=True)
    consent_scope = Column(String, nullable=True)
    deletion_status = Column(String, default=DeletionStatus.ACTIVE.value)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class MemoryCard(Base):
    """A single reconstructed memory shown to the patient.

    Status lifecycle (spec §7.3): AI drafts (DRAFT/AI_RECONSTRUCTED) ->
    family reviews (AWAITING_REVIEW) -> APPROVED | DISPUTED | REJECTED;
    later ARCHIVED / RESTRICTED / DELETED.

    confidence_score (0-100) comes from the weighted formula in §8.2;
    confidence_breakdown stores each sub-score + its weight so the score
    is fully explainable. contradictions lists conflicting facts.
    sensitivity_flags hide content by default (§16).
    """

    __tablename__ = "memory_cards"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    title = Column(String(500), nullable=False)
    narrative = Column(String, nullable=True)
    media_urls = Column(JSON, default=list)

    people_identified = Column(JSON, default=list)  # display cache; graph holds links
    tags = Column(JSON, default=list)

    memory_date = Column(Date, nullable=True)
    date_accuracy = Column(String, default=DateAccuracy.APPROXIMATE.value)

    confidence_score = Column(Integer, default=0)  # 0-100
    confidence_breakdown = Column(JSON, nullable=True)  # §8.2 sub-scores
    explanation = Column(String, nullable=True)
    contradictions = Column(JSON, default=list)

    status = Column(String, default=MemoryStatus.DRAFT.value)
    visibility = Column(String, default=Visibility.BOTH.value)

    sensitivity_flags = Column(JSON, default=list)  # SensitivityCategory values
    model_version = Column(String, nullable=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_revision_id = Column(
        String,
        ForeignKey(
            "memory_revisions.id", use_alter=True,
            name="fk_memory_cards_approved_revision", ondelete="SET NULL",
        ),
        nullable=True,
    )
    candidate_revision_id = Column(
        String,
        ForeignKey(
            "memory_revisions.id", use_alter=True,
            name="fk_memory_cards_candidate_revision", ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MemoryRevision(Base):
    """An immutable revision of a memory's content (spec §39).

    Every edit creates a new revision; the chain is linked by
    superseded_by_id. A memory's current content points at its latest
    approved revision, preserving full history.
    """

    __tablename__ = "memory_revisions"

    id = Column(String, primary_key=True, default=new_id)
    memory_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)

    revision_number = Column(Integer, default=1)
    content = Column(JSON, nullable=True)  # {title, narrative, media_urls, ...}
    change_note = Column(String, nullable=True)
    status = Column(String, default="draft")  # draft|approved|rejected|superseded
    superseded_by_id = Column(String, ForeignKey("memory_revisions.id"), nullable=True)

    authored_by = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class MemoryReviewRecord(Base):
    """An append-only submission or review decision for one revision."""

    __tablename__ = "memory_review_records"

    id = Column(String, primary_key=True, default=new_id)
    memory_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)
    revision_id = Column(String, ForeignKey("memory_revisions.id"), nullable=False)
    decision = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    actor_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Evidence(Base):
    """A first-class unit of proof behind a memory (spec §18.4).

    Each piece of evidence is traceable to a source (source_id) and
    carries its own confidence and review status, so nothing enters a
    memory without provenance.
    """

    __tablename__ = "evidence"

    id = Column(String, primary_key=True, default=new_id)
    memory_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)
    revision_id = Column(
        String,
        ForeignKey("memory_revisions.id", name="fk_evidence_revision", ondelete="SET NULL"),
        nullable=True,
    )
    source_id = Column(String, ForeignKey("sources.id"), nullable=True)

    evidence_type = Column(String, nullable=False)  # EvidenceType
    claim = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    extractor_version = Column(String, nullable=True)
    review_status = Column(String, default=EvidenceReviewStatus.PENDING.value)
    reviewed_by = Column(
        String, ForeignKey("users.id", name="fk_evidence_reviewer"), nullable=True
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
