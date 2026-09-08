"""Engagement tracking and notifications."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base
from app.models.base import new_id, utcnow


class EngagementLog(Base):
    """What the patient does with each memory card.

    Drives the caregiver dashboard (most-engaged memories, patterns)
    and feeds the distress detector (rapid re-viewing, repeated questions).
    """

    __tablename__ = "engagement_logs"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    memory_card_id = Column(String, ForeignKey("memory_cards.id"), nullable=False)

    action = Column(String, nullable=False)  # viewed|dwell|asked_question|closed
    duration_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    """Alerts: 'new draft ready for review', 'distress signal', etc."""

    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    patient_id = Column(String, ForeignKey("users.id"), nullable=True)
    required_action = Column(String, nullable=True)
    type = Column(String, nullable=False)  # review_needed|upload_complete|distress|approval
    message = Column(String, nullable=False)
    read = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utcnow)
