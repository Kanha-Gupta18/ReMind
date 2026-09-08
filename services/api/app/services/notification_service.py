"""Notifications: alerts for family, caregivers, and clinicians."""

from sqlalchemy.orm import Session

from app.models.clinical import Notification
from app.models.constants import AccessGrantStatus, ConsentAction, NotificationType, Role
from app.models.memory import MemoryCard
from app.models.user import PatientAccessGrant, User
from app.services import consent_service


def notify(
    db: Session,
    user_id: str,
    patient_id: str,
    required_action: str,
    type: str,
    message: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        patient_id=patient_id,
        required_action=required_action,
        type=type,
        message=message,
    )
    db.add(notification)
    db.flush()
    return notification


def notify_role(
    db: Session,
    patient_id: str,
    role: str,
    required_action: str | ConsentAction,
    type: str,
    message: str,
) -> list[Notification]:
    """Notify every user with the given role linked to a patient.

    Example: all family_reviewers when a memory reaches AWAITING_REVIEW.
    """
    users = (
        db.query(User)
        .join(PatientAccessGrant, PatientAccessGrant.user_id == User.id)
        .filter(
            PatientAccessGrant.patient_id == patient_id,
            PatientAccessGrant.status == AccessGrantStatus.ACTIVE.value,
            User.role == role,
            User.is_active.is_(True),
        )
        .all()
    )
    action_value = required_action.value if isinstance(required_action, ConsentAction) else required_action
    return [
        notify(db, u.id, patient_id, action_value, type, message)
        for u in users
        if consent_service.action_is_allowed(db, u, patient_id, action_value)
    ]


def notification_is_visible(db: Session, notification: Notification, user: User) -> bool:
    return bool(
        notification.user_id == user.id
        and notification.patient_id
        and notification.required_action
        and consent_service.action_is_allowed(
            db, user, notification.patient_id, notification.required_action
        )
    )


def list_for_user(
    db: Session,
    user: User,
    unread_only: bool = False,
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        query = query.filter(Notification.read.is_(False))
    return [
        item for item in query.order_by(Notification.created_at.desc()).all()
        if notification_is_visible(db, item, user)
    ]


def mark_read(db: Session, notification_id: str) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise ValueError(f"Notification {notification_id} not found")
    notification.read = True
    db.flush()
    return notification


def mark_all_read(db: Session, user: User) -> int:
    items = list_for_user(db, user, unread_only=True)
    for item in items:
        item.read = True
    return len(items)


# ---------------------------------------------------------------------------
# Convenience wrappers for the common workflows
# ---------------------------------------------------------------------------


def notify_review_needed(db: Session, memory: MemoryCard) -> list[Notification]:
    return notify_role(
        db,
        memory.patient_id,
        Role.FAMILY_REVIEWER.value,
        ConsentAction.MEMORIES_REVIEW,
        NotificationType.REVIEW_NEEDED.value,
        f"A new memory is ready for review: {memory.title}",
    )


def notify_upload_complete(db: Session, patient_id: str) -> list[Notification]:
    return notify_role(
        db,
        patient_id,
        Role.FAMILY_CONTRIBUTOR.value,
        ConsentAction.SOURCES_VIEW,
        NotificationType.UPLOAD_COMPLETE.value,
        "A source you uploaded has finished processing.",
    )


def notify_dispute_flagged(
    db: Session, patient_id: str, memory_title: str
) -> list[Notification]:
    return notify_role(
        db,
        patient_id,
        Role.FAMILY_REVIEWER.value,
        ConsentAction.MEMORIES_REVIEW,
        NotificationType.DISPUTE_FLAGGED.value,
        f"Memory flagged for dispute: {memory_title}",
    )
