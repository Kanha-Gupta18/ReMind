"""Identity, roles, patient records, third-party consent, and the audit trail."""

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, JSON, String

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import CognitionLevel, Role, SafetyLevel


class User(Base):
    """Everyone who uses ReMind: patients, family, caregivers, guardians,
    clinicians, and administrators.

    A 'patient' is a User with role='patient'. Family/guardian/caregiver/
    clinician users link to their patient via patient_id.

    Roles (spec §23): patient | family_contributor | family_reviewer |
    caregiver | guardian | clinician | administrator.
    """

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_id)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)

    role = Column(String, nullable=False)  # Role

    # For family/guardian/caregiver/clinician: which patient do they serve?
    patient_id = Column(String, ForeignKey("users.id"), nullable=True)

    phone = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PatientProfile(Base):
    """Clinical + legal data about a patient, separate from their login.

    safety_level (spec §16.2) gates how much sensitive content the
    patient interface may show without a caregiver present.
    """

    __tablename__ = "patient_profiles"

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

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
