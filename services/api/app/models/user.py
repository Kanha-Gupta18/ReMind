"""Identity, roles, patient records, third-party consent, and the audit trail."""

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship as orm_relationship

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import AccessGrantStatus, CognitionLevel, PatientProfileStatus, Role, SafetyLevel


class User(Base):
    """Everyone who uses ReMind: patients, family, caregivers, guardians,
    clinicians, and administrators.

    A 'patient' is a User with role='patient'. Other users receive access through
    explicit PatientAccessGrant records, so one account can support more than one
    patient without broadening its authority.

    Roles (spec §23): patient | family_contributor | family_reviewer |
    caregiver | guardian | clinician | administrator.
    """

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_id)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)

    role = Column(String, nullable=False)  # Role

    phone = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    access_grants = orm_relationship(
        "PatientAccessGrant",
        foreign_keys="PatientAccessGrant.user_id",
        back_populates="user",
    )

    auth_sessions = orm_relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def patient_ids(self) -> list[str]:
        return [
            grant.patient_id for grant in self.access_grants
            if grant.status == AccessGrantStatus.ACTIVE.value
        ]


class PatientAccessGrant(Base):
    """A revocable relationship between one account and one patient."""

    __tablename__ = "patient_access_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", name="uq_patient_access_grant_user_patient"),
    )

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship = Column(String, nullable=False)
    status = Column(String, default=AccessGrantStatus.ACTIVE.value, nullable=False)
    granted_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = orm_relationship("User", foreign_keys=[user_id], back_populates="access_grants")


class AuthSession(Base):
    """Server-side login session supporting timeout, rotation, and revocation."""

    __tablename__ = "auth_sessions"

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    idle_expires_at = Column(DateTime(timezone=True), nullable=False)
    absolute_expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoke_reason = Column(String, nullable=True)

    user = orm_relationship("User", back_populates="auth_sessions")


class PatientProfile(Base):
    """Clinical + legal data about a patient, separate from their login.

    safety_level (spec §16.2) gates how much sensitive content the
    patient interface may show without a caregiver present.
    """

    __tablename__ = "patient_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_patient_profiles_user_id"),
    )

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    preferred_name = Column(String, nullable=False)
    preferred_language = Column(String, default="en", nullable=False)
    accessibility_profile = Column(JSON, default=dict, nullable=False)
    status = Column(String, default=PatientProfileStatus.ACTIVE.value, nullable=False)

    date_of_birth = Column(Date, nullable=True)
    diagnosis = Column(String, nullable=True)
    diagnosis_date = Column(Date, nullable=True)
    cognition_level = Column(String, nullable=True)  # CognitionLevel

    guardian_id = Column(String, ForeignKey("users.id"), nullable=True)

    safety_level = Column(String, default=SafetyLevel.NORMAL.value)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ThirdPartyConsent(Base):
    """Consent records for anyone who appears in the patient's data.

    Ethical framework §1: every third party has the right to be
    informed and to request removal. person_id links to the people
    table once that person is known.
    """

    __tablename__ = "third_party_consent"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    person_id = Column(String, ForeignKey("people.id"), nullable=True)
    person_name = Column(String, nullable=False)
    contact = Column(String, nullable=True)
    consent_given = Column(Boolean, default=False)
    notes = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Immutable trail of every action on every memory.

    Ethical framework §5: every action is logged with timestamp + user ID.
    Spec §24: the audit log is append-only; ip_address and user_agent
    record who did it and from where.
    """

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)  # created, approved, rejected, flagged, edited
    resource_type = Column(String, nullable=False)  # memory_card, source, edge
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
