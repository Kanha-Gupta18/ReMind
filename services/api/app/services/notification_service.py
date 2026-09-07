"""Notifications: alerts for family, caregivers, and clinicians."""

from sqlalchemy.orm import Session

from app.models.clinical import Notification
from app.models.constants import NotificationType, Role
from app.models.memory import MemoryCard
from app.models.user import User


def notify(
    db: Session,
    user_id: str,
    type: str,
    message: str,
) -> Notification:
    notification = Notification(user_id=user_id, type=type, message=message)
    db.add(notification)
    db.flush()
    return notification


def notify_role(
    db: Session,
    patient_id: str,
    role: str,
    type: str,
    message: str,
) -> list[Notification]:
    """Notify every user with the given role linked to a patient.

    Example: all family_reviewers when a memory reaches AWAITING_REVIEW.
    """
    users = (
        db.query(User)
        .filter(User.patient_id == patient_id, User.role == role, User.is_active.is_(True))
        .all()
    )
    return [notify(db, u.id, type, message) for u in users]


def list_for_user(
    db: Session,
    user_id: str,
    unread_only: bool = False,
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read.is_(False))
    return query.order_by(Notification.created_at.desc()).all()


def mark_read(db: Session, notification_id: str) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise ValueError(f"Notification {notification_id} not found")
    notification.read = True
    db.flush()
    return notification


def mark_all_read(db: Session, user_id: str) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read.is_(False))
        .update({"read": True}, synchronize_session=False)
    )
    return rows


# ---------------------------------------------------------------------------
# Convenience wrappers for the common workflows
# ---------------------------------------------------------------------------


def notify_review_needed(db: Session, memory: MemoryCard) -> list[Notification]:
    return notify_role(
        db,
        memory.patient_id,
        Role.FAMILY_REVIEWER.value,
        NotificationType.REVIEW_NEEDED.value,
        f"A new memory is ready for review: {memory.title}",
    )


def notify_upload_complete(db: Session, patient_id: str) -> list[Notification]:
    return notify_role(
        db,
        patient_id,
        Role.FAMILY_CONTRIBUTOR.value,
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
        NotificationType.DISPUTE_FLAGGED.value,
        f"Memory flagged for dispute: {memory_title}",
    )
