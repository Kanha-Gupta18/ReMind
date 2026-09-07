"""Conversation sessions, messages, and safety events (spec §16, §18.5, §21)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import (
    ConversationSessionStatus,
    ConversationSessionType,
    MessageRole,
    SafetyEventType,
    Severity,
)


class ConversationSession(Base):
    """A chat session between the patient and the conversational AI (§21)."""

    __tablename__ = "conversation_sessions"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    session_type = Column(String, default=ConversationSessionType.CHAT.value)
    status = Column(String, default=ConversationSessionStatus.ACTIVE.value)
    started_by = Column(String, ForeignKey("users.id"), nullable=True)

    ended_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class ConversationMessage(Base):
    """One turn in a conversation session (§21).

    role is patient (the user), system (the AI reply), or tool (a record
    of a knowledge-graph tool call). tool_calls captures which tools ran
    and their results so the AI's answers stay evidence-based.
    """

    __tablename__ = "conversation_messages"

    id = Column(String, primary_key=True, default=new_id)
    session_id = Column(String, ForeignKey("conversation_sessions.id"), nullable=False)

    role = Column(String, nullable=False)  # MessageRole
    content = Column(String, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    safety_flag = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class SafetyEvent(Base):
    """A detected or reported safety incident (spec §16, §18.5).

    Covers distress signals, caregiver-issued stops, and blocked
    restricted queries, with severity and the action taken.
    """

    __tablename__ = "safety_events"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, ForeignKey("conversation_sessions.id"), nullable=True)
    memory_card_id = Column(String, ForeignKey("memory_cards.id"), nullable=True)

    event_type = Column(String, nullable=False)  # SafetyEventType
    severity = Column(String, default=Severity.LOW.value)
    context = Column(JSON, nullable=True)
    action_taken = Column(String, nullable=True)

    acknowledged_by = Column(String, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
