"""Import every model here so SQLAlchemy registers all tables
before create_all() runs. Models must be imported before
Base.metadata knows about them."""

from app.models.user import AuthSession, AuditLog, PatientAccessGrant, PatientProfile, ThirdPartyConsent, User
from app.models.consent import ConsentDirective
from app.models.memory import Evidence, MemoryCard, MemoryRevision, Source
from app.models.people import FaceMatch, Person
from app.models.graph import GraphEdge, GraphEvidence, GraphNode
from app.models.conversation import ConversationMessage, ConversationSession, SafetyEvent
from app.models.clinical import EngagementLog, Notification

__all__ = [
    "User",
    "PatientProfile",
    "PatientAccessGrant",
    "AuthSession",
    "ThirdPartyConsent",
    "AuditLog",
    "ConsentDirective",
    "Source",
    "MemoryCard",
    "MemoryRevision",
    "Evidence",
    "Person",
    "FaceMatch",
    "GraphNode",
    "GraphEdge",
    "GraphEvidence",
    "ConversationSession",
    "ConversationMessage",
    "SafetyEvent",
    "EngagementLog",
    "Notification",
]

MODEL_COUNT = len(__all__)
