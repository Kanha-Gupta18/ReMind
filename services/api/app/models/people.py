"""First-class people and photo face matches (spec §6.1.1, §18.2)."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import FaceMatchState, IdentityStatus


class Person(Base):
    """A person in the patient's life (spec §18.2).

    identity_status follows the same ladder as face-match states, from
    UNIDENTIFIED up to FAMILY_CONFIRMED (or DISPUTED). aliases captures
    nicknames ("Bhaiya", "Ramesh-ji") that matter for the conversational
    interface.
    """

    __tablename__ = "people"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    aliases = Column(JSON, default=list)
    relationship_to_patient = Column(String, nullable=True)
    identity_status = Column(String, default=IdentityStatus.UNIDENTIFIED.value)
    notes = Column(String, nullable=True)

    created_by = Column(String, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FaceMatch(Base):
    """Association of a face in one photo to a person (spec §6.1.1).

    State ladder: UNIDENTIFIED -> POSSIBLE_MATCH -> LIKELY_MATCH ->
    FAMILY_CONFIRMED (or DISPUTED). The AI pipeline may only suggest
    POSSIBLE/LIKELY matches; only a reviewer moves a match to
    FAMILY_CONFIRMED.
    """

    __tablename__ = "face_matches"

    id = Column(String, primary_key=True, default=new_id)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False)
    person_id = Column(String, ForeignKey("people.id"), nullable=True)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    face_match_state = Column(String, default=FaceMatchState.UNIDENTIFIED.value)
    confidence = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)

    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
