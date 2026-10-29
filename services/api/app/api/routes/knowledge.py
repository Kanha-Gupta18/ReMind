"""Canonical place and event routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_consent_action, require_roles
from app.core.database import get_db
from app.models.constants import ConsentAction, Role
from app.models.user import User
from app.schemas.knowledge import EventCreate, PlaceCreate
from app.services import audit_service, knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_CREATE_ROLES = [
    Role.FAMILY_CONTRIBUTOR.value,
    Role.FAMILY_REVIEWER.value,
    Role.GUARDIAN.value,
]


def _patient(scope: str | None) -> str:
    if scope is None:
        raise HTTPException(status_code=403, detail="No patient relationship is configured")
    return scope


@router.get("/places")
def list_places(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    patient_id = _patient(scope)
    require_consent_action(db, current, patient_id, ConsentAction.GRAPH_VIEW)
    items = knowledge_service.list_places(db, patient_id)
    return {"items": [_place_json(item) for item in items], "count": len(items)}


@router.post("/places", status_code=status.HTTP_201_CREATED)
def create_place(
    body: PlaceCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_CREATE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    patient_id = _patient(scope)
    require_consent_action(db, current, patient_id, ConsentAction.GRAPH_EDIT)
    place = knowledge_service.create_place(
        db, patient_id, current.id, body.name, body.aliases, body.description
    )
    audit_service.log_action(db, current.id, "created", "place", place.id)
    db.commit()
    return _place_json(place)


@router.get("/events")
def list_events(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    patient_id = _patient(scope)
    require_consent_action(db, current, patient_id, ConsentAction.GRAPH_VIEW)
    items = knowledge_service.list_events(db, patient_id)
    return {"items": [_event_json(item) for item in items], "count": len(items)}


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(
    body: EventCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_CREATE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    patient_id = _patient(scope)
    require_consent_action(db, current, patient_id, ConsentAction.GRAPH_EDIT)
    event = knowledge_service.create_event(
        db, patient_id, current.id, body.name, body.description,
        body.start_date, body.end_date, body.date_accuracy,
    )
    audit_service.log_action(db, current.id, "created", "event", event.id)
    db.commit()
    return _event_json(event)


def _place_json(place) -> dict:
    return {
        "id": place.id, "patient_id": place.patient_id, "name": place.name,
        "aliases": place.aliases or [], "description": place.description,
        "created_at": place.created_at.isoformat(),
    }


def _event_json(event) -> dict:
    return {
        "id": event.id, "patient_id": event.patient_id, "name": event.name,
        "description": event.description,
        "start_date": event.start_date.isoformat() if event.start_date else None,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "date_accuracy": event.date_accuracy,
        "created_at": event.created_at.isoformat(),
    }
