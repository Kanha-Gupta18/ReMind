"""Notification routes: a user's own inbox (spec §18.5 workflows)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.clinical import Notification
from app.models.user import User
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    unread: bool = False,
):
    notifications = notification_service.list_for_user(db, current, unread_only=unread)
    return {"items": [
        {"id": n.id, "type": n.type, "message": n.message, "read": n.read,
         "created_at": n.created_at.isoformat()}
        for n in notifications
    ], "count": len(notifications)}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    notification = db.get(Notification, notification_id)
    if notification is None or not notification_service.notification_is_visible(db, notification, current):
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    count = notification_service.mark_all_read(db, current)
    db.commit()
    return {"ok": True, "updated": count}
