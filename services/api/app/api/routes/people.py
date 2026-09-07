"""People + face-match routes (spec §6.1.1, §18.2).

RBAC:
  - everyone in scope reads people and their graph relations
  - contributor/reviewer  create people, propose aliases/relations
  - reviewer/guardian/admin  update identity and confirm face matches
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_roles
from app.core.database import get_db
from app.models.constants import FaceMatchState, IdentityStatus, Role
from app.models.people import FaceMatch, Person
from app.models.user import User
from app.schemas.people import FaceMatchConfirm, PersonCreate, PersonUpdate
from app.services import audit_service, graph_service

router = APIRouter(prefix="/people", tags=["people"])

_EDIT_ROLES = [Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value, Role.ADMINISTRATOR.value]
_CREATE_ROLES = _EDIT_ROLES + [Role.FAMILY_CONTRIBUTOR.value]


def _scope_patient(scope: str | None, current: User, body_patient_id: str | None = None) -> str:
    if scope is None:
        if body_patient_id is None:
            raise HTTPException(status_code=400, detail="patient_id required")
        return body_patient_id
    return scope


def _resolve_scope(scope: str | None, patient_id: str | None = None) -> str:
    """Scope resolution: linked roles use their patient; administrator must
    pass patient_id explicitly (cross-patient)."""
    if scope is not None:
        if patient_id and patient_id != scope:
            raise HTTPException(status_code=403, detail="Not your patient")
        return scope
    if patient_id is None:
        raise HTTPException(status_code=403, detail="Administrator must pick a patient")
    return patient_id


@router.get("")
def list_people(
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    people = db.query(Person).filter(Person.patient_id == pid).order_by(Person.name).all()
    return {"items": [_json(p) for p in people], "count": len(people)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_person(
    patient_id: str | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
    current: Annotated[User, Depends(require_roles(*_CREATE_ROLES))] = None,
    scope: Annotated[str | None, Depends(get_patient_scope)] = None,
    body: PersonCreate = Body(...),
):
    pid = _scope_patient(scope, current, patient_id)
    person = Person(
        patient_id=pid, name=body.name, aliases=body.aliases,
        relationship_to_patient=body.relationship_to_patient,
        identity_status=IdentityStatus.UNIDENTIFIED.value,
        notes=body.notes, created_by=current.id,
    )
    db.add(person)
    db.flush()
    audit_service.log_action(db, current.id, "created", "person", person.id)
    db.commit()
    return _json(person)


@router.patch("/{person_id}")
def update_person(
    person_id: str,
    body: PersonUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_EDIT_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    if scope is not None and person.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your patient")
    if body.aliases is not None:
        person.aliases = body.aliases
    if body.relationship_to_patient is not None:
        person.relationship_to_patient = body.relationship_to_patient
    if body.identity_status is not None:
        allowed = {IdentityStatus.UNIDENTIFIED.value, IdentityStatus.POSSIBLE_MATCH.value,
                   IdentityStatus.LIKELY_MATCH.value, IdentityStatus.FAMILY_CONFIRMED.value,
                   IdentityStatus.DISPUTED.value}
        if body.identity_status not in allowed:
            raise HTTPException(status_code=400, detail="Invalid identity status")
        person.identity_status = body.identity_status
    if body.notes is not None:
        person.notes = body.notes
    audit_service.log_action(db, current.id, "updated", "person", person.id,
                             {"identity_status": person.identity_status})
    db.commit()
    return _json(person)


@router.get("/{person_id}/relations")
def person_relations(
    person_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    if scope is not None and person.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your patient")
    nodes = graph_service.find_nodes(db, person.patient_id, "person", person.name)
    if not nodes:
        return {"items": []}
    return {"items": graph_service.resolve_relations_for_person(db, person.patient_id, nodes[0].id)}


@router.get("/face-matches")
def list_face_matches(
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    matches = db.query(FaceMatch).filter(FaceMatch.patient_id == pid)\
        .order_by(FaceMatch.created_at.desc()).all()
    return {"items": [
        {"id": f.id, "source_id": f.source_id, "person_id": f.person_id,
         "face_match_state": f.face_match_state, "confidence": f.confidence,
         "model_version": f.model_version, "reviewed_by": f.reviewed_by,
         "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None}
        for f in matches
    ], "count": len(matches)}


@router.post("/face-matches/{match_id}/confirm")
def confirm_face_match(
    match_id: str,
    body: FaceMatchConfirm,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_EDIT_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    match = db.get(FaceMatch, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Face match not found")
    if scope is not None and match.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your patient")
    person = db.get(Person, body.person_id)
    if person is None or person.patient_id != match.patient_id:
        raise HTTPException(status_code=400, detail="Person must belong to the same patient")
    match.person_id = person.id
    match.face_match_state = FaceMatchState.FAMILY_CONFIRMED.value
    match.reviewed_by = current.id
    from app.models.base import utcnow
    match.reviewed_at = utcnow()
    person.identity_status = IdentityStatus.FAMILY_CONFIRMED.value
    audit_service.log_action(db, current.id, "confirmed_face_match", "face_match", match.id,
                             {"person_id": person.id})
    db.commit()
    return {"ok": True, "face_match_state": match.face_match_state,
            "person_identity_status": person.identity_status}


def _json(p: Person) -> dict:
    return {
        "id": p.id, "patient_id": p.patient_id, "name": p.name,
        "aliases": p.aliases or [], "relationship_to_patient": p.relationship_to_patient,
        "identity_status": p.identity_status, "notes": p.notes,
        "created_at": p.created_at.isoformat(),
    }
