"""Versioned consent directives (spec §17)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint

from app.core.database import Base
from app.models.base import new_id, utcnow


class ConsentDirective(Base):
    """A signed, versioned consent directive for a patient.

    Each new version supersedes the previous one (supersedes_id is a
    self-referencing FK), forming an auditable version chain so consent
    history is never lost. permissions/restrictions/guardian_rules are
    JSON documents describing what is allowed and what is off-limits.

    Spec §17: valid_from, supersedes, permissions, restrictions, signer,
    witness, guardian_rules, training_opt_in, post_death_policy.
    """

    __tablename__ = "consent_directives"
    __table_args__ = (
        UniqueConstraint("patient_id", "version", name="uq_consent_directive_patient_version"),
    )

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    version = Column(Integer, default=1)
    valid_from = Column(DateTime(timezone=True), default=utcnow)
    supersedes_id = Column(String, ForeignKey("consent_directives.id"), nullable=True)

    permissions = Column(JSON, default=dict)
    restrictions = Column(JSON, default=dict)
    guardian_rules = Column(JSON, default=dict)

    signer = Column(String, nullable=True)
    signed_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    witness = Column(String, nullable=True)
    training_opt_in = Column(Boolean, default=False)
    post_death_policy = Column(JSON, default=lambda: {"mode": "keep_private"}, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow)
