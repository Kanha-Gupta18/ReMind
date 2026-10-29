"""Canonical enum values for ReMind, matching the professor's spec.

Stored as plain strings (e.g. "AWAITING_REVIEW") so the database stays
readable and compatible with any client. Use these constants everywhere
instead of typing raw strings, so a typo fails loudly instead of
silently writing a bad row.
"""

from enum import Enum


class Role(str, Enum):
    """Who can do what (spec §23). Seven roles total."""

    PATIENT = "patient"
    FAMILY_CONTRIBUTOR = "family_contributor"
    FAMILY_REVIEWER = "family_reviewer"
    CAREGIVER = "caregiver"
    GUARDIAN = "guardian"
    CLINICIAN = "clinician"
    ADMINISTRATOR = "administrator"


class AccessGrantStatus(str, Enum):
    """Lifecycle of an account's relationship with a patient."""

    ACTIVE = "active"
    REVOKED = "revoked"


class PatientProfileStatus(str, Enum):
    """Operational state of a patient profile."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DECEASED = "deceased"


class ConsentAction(str, Enum):
    """Patient-scoped actions that an advance directive can authorize."""

    PROFILE_VIEW = "profile:view"
    PROFILE_EDIT = "profile:edit"
    RELATIONSHIPS_VIEW = "relationships:view"
    RELATIONSHIPS_MANAGE = "relationships:manage"
    CONSENT_VIEW = "consent:view"
    CONSENT_MANAGE = "consent:manage"
    SOURCES_VIEW = "sources:view"
    SOURCES_UPLOAD = "sources:upload"
    SOURCES_PROCESS = "sources:process"
    SOURCES_DELETE = "sources:delete"
    MEMORIES_VIEW = "memories:view"
    MEMORIES_CREATE = "memories:create"
    MEMORIES_EDIT = "memories:edit"
    MEMORIES_REVIEW = "memories:review"
    PEOPLE_VIEW = "people:view"
    PEOPLE_CREATE = "people:create"
    PEOPLE_VERIFY = "people:verify"
    GRAPH_VIEW = "graph:view"
    GRAPH_EDIT = "graph:edit"
    GRAPH_REVIEW = "graph:review"
    CONVERSATIONS_VIEW = "conversations:view"
    SAFETY_VIEW = "safety:view"
    SAFETY_MANAGE = "safety:manage"
    ENGAGEMENT_VIEW = "engagement:view"


class MemoryStatus(str, Enum):
    """Lifecycle of a memory card (spec §7.3). Nine states."""

    DRAFT = "DRAFT"
    AI_RECONSTRUCTED = "AI_RECONSTRUCTED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"
    RESTRICTED = "RESTRICTED"
    DELETED = "DELETED"


class SafetyLevel(str, Enum):
    """Content-access gating level (spec §16.2)."""

    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    CAREGIVER_RECOMMENDED = "CAREGIVER_RECOMMENDED"
    CAREGIVER_REQUIRED = "CAREGIVER_REQUIRED"
    HIDDEN = "HIDDEN"


class SensitivityCategory(str, Enum):
    """Sensitive content categories that gate what the patient sees (§16)."""

    DEATH = "DEATH"
    BEREAVEMENT = "BEREAVEMENT"
    TRAUMA = "TRAUMA"
    ABUSE = "ABUSE"
    ESTRANGEMENT = "ESTRANGEMENT"
    DIVORCE = "DIVORCE"
    FAMILY_CONFLICT = "FAMILY_CONFLICT"
    SERIOUS_ILLNESS = "SERIOUS_ILLNESS"
    ACCIDENT = "ACCIDENT"
    WAR = "WAR"
    VIOLENCE = "VIOLENCE"
    OTHER_RESTRICTED = "OTHER_RESTRICTED"


class IdentityStatus(str, Enum):
    """Confidence ladder for a person's identity (spec §18.2)."""

    UNIDENTIFIED = "UNIDENTIFIED"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    LIKELY_MATCH = "LIKELY_MATCH"
    FAMILY_CONFIRMED = "FAMILY_CONFIRMED"
    DISPUTED = "DISPUTED"


class FaceMatchState(str, Enum):
    """State of a face-in-photo to person match (spec §6.1.1)."""

    UNIDENTIFIED = "UNIDENTIFIED"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    LIKELY_MATCH = "LIKELY_MATCH"
    FAMILY_CONFIRMED = "FAMILY_CONFIRMED"
    DISPUTED = "DISPUTED"


class SourceStatus(str, Enum):
    """Processing status of an uploaded source."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, Enum):
    """Kinds of raw material a family can upload."""

    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    MESSAGE_EXPORT = "message_export"


class PipelineType(str, Enum):
    """Which extraction pipeline a source runs through."""

    VISION = "vision"
    SPEECH = "speech"
    NLP = "nlp"
    LOCATION = "location"


class DeletionStatus(str, Enum):
    """Soft-deletion states for sources (§5.1.2)."""

    ACTIVE = "active"
    SOFT_DELETED = "soft_deleted"
    DELETED = "deleted"


class DateAccuracy(str, Enum):
    """How precise a memory's date is."""

    EXACT = "exact"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    APPROXIMATE = "approximate"


class Visibility(str, Enum):
    """Who may see a memory (consent/field-level protection §24)."""

    PATIENT = "patient"
    FAMILY_ONLY = "family_only"
    BOTH = "both"


class EvidenceType(str, Enum):
    """Kinds of evidence behind a memory (spec §18.4)."""

    FACE_MATCH = "face_match"
    TRANSCRIPT = "transcript"
    DOCUMENT_EXCERPT = "document_excerpt"
    FAMILY_STATEMENT = "family_statement"
    LOCATION_EXIF = "location_exif"
    SEMANTIC = "semantic"


class EvidenceReviewStatus(str, Enum):
    """Review state of a piece of evidence."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DISPUTED = "DISPUTED"


class GraphNodeType(str, Enum):
    """Node kinds in the knowledge graph (spec §9)."""

    PERSON = "person"
    PATIENT = "patient"
    FAMILY_MEMBER = "family_member"
    CAREGIVER = "caregiver"
    CLINICIAN = "clinician"
    RELATIONSHIP = "relationship"
    MEMORY = "memory"
    EVENT = "event"
    PLACE = "place"
    ORGANIZATION = "organization"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    MESSAGE = "message"
    DATE_RANGE = "date_range"
    TOPIC = "topic"
    OBJECT = "object"
    SOURCE = "source"
    CONSENT_DIRECTIVE = "consent_directive"
    SENSITIVE_CATEGORY = "sensitive_category"


class EdgeStatus(str, Enum):
    """Review state of a knowledge-graph edge (§9)."""

    CONFIRMED = "CONFIRMED"
    SUGGESTED = "SUGGESTED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"


class ConversationSessionType(str, Enum):
    """Kinds of conversation the patient can have (§21)."""

    CHAT = "chat"
    REMINISCENCE = "reminiscence"
    SUPPORT = "support"


class ConversationSessionStatus(str, Enum):
    """Lifecycle of a conversation session."""

    ACTIVE = "active"
    ENDED = "ended"
    STOPPED = "stopped"


class MessageRole(str, Enum):
    """Who wrote a conversation message (§21)."""

    PATIENT = "patient"
    SYSTEM = "system"
    TOOL = "tool"


class SafetyEventType(str, Enum):
    """Kinds of safety incidents (spec §18.5)."""

    DISTRESS = "distress"
    CAREGIVER_STOP = "caregiver_stop"
    RESTRICTED_QUERY = "restricted_query"


class Severity(str, Enum):
    """Severity ladder used by safety events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CognitionLevel(str, Enum):
    """Patient cognition staging."""

    EARLY = "early"
    MODERATE = "moderate"
    ADVANCED = "advanced"


class RevisionStatus(str, Enum):
    """Lifecycle of a memory revision (spec §39)."""

    DRAFT = "draft"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"


class ReviewDecision(str, Enum):
    """Append-only decisions recorded against a memory revision."""

    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPUTED = "disputed"


class NotificationType(str, Enum):
    """Kinds of notification we can raise."""

    REVIEW_NEEDED = "review_needed"
    UPLOAD_COMPLETE = "upload_complete"
    DISTRESS = "distress"
    APPROVAL = "approval"
    DISPUTE_FLAGGED = "dispute_flagged"
    FAMILY_HELP = "family_help"


class EngagementAction(str, Enum):
    """Actions a patient takes on a memory card."""

    VIEWED = "viewed"
    DWELL = "dwell"
    ASKED_QUESTION = "asked_question"
    CLOSED = "closed"


class ConfidenceBand(str, Enum):
    """Confidence bands (spec §8.2): 90-100, 75-89, 50-74, 25-49, 0-24."""

    HIGH = "high"
    GOOD = "good"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"
