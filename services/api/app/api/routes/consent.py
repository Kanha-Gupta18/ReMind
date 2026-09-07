"""Consent routes: versioned directives + third-party consent (spec §17, §24).

RBAC:
  - everyone in scope may view directives and third-party records
  - patient/guardian/admin may sign a new directive version
  - guardian/admin manage third-party consent records
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_roles
from app.core.database import get_db
from app.models.constants import Role
from app.models.user import User
from app.schemas.consent import (
    ConsentDirectiveCreate,
    ConsentDirectiveOut,
    ThirdPartyConsentCreate,
    ThirdPartyConsentOut,
    ThirdPartyConsentUpdate,
)
from app.services import audit_service, consent_service

router = APIRouter(prefix="/consent", tags=["consent"])

_SIGN_ROLES = [Role.PATIENT.value, Role.GUARDIAN.value, Role.ADMINISTRATOR.value]
_MANAGE_ROLES = [Role.GUARDIAN.value, Role.ADMINISTRATOR.value]


def _resolve_scope(scope: str | None, patient_id: str | None = None) -> str:
    """Scope resolution: family/caregiver/clinician/guardian use their linked
    patient; administrator must pass patient_id explicitly (cross-patient)."""
    if scope is not None:
        if patient_id and patient_id != scope:
            raise HTTPException(status_code=403, detail="Not your patient")
        return scope
    if patient_id is None:
        raise HTTPException(status_code=403, detail="Administrator must pick a patient")
    return patient_id


def _directive_json(d) -> dict:
    return {
        "id": d.id, "patient_id": d.patient_id, "version": d.version,
        "valid_from": d.valid_from.isoformat(),
        "supersedes_id": d.supersedes_id,
        "permissions": d.permissions or {},
        "restrictions": d.restrictions or {},
        "guardian_rules": d.guardian_rules or {},
        "signer": d.signer, "witness": d.witness,
        "training_opt_in": d.training_opt_in,
        "post_death_policy": d.post_death_policy,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


def _third_party_json(c) -> dict:
    return {
        "id": c.id, "patient_id": c.patient_id,
        "person_id": c.person_id, "person_name": c.person_name,
        "contact": c.contact, "consent_given": c.consent_given,
        "notes": c.notes, "created_at": c.created_at.isoformat(),
    }


@router.get("/directives")
def list_directives(
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    directives = consent_service.list_directives(db, pid)
    return {"items": [_directive_json(d) for d in directives], "count": len(directives)}


@router.get("/directives/{directive_id}")
def get_directive(
    directive_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    directive = consent_service.get_directive(db, directive_id)
    if directive is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    if scope is not None and scope != directive.patient_id:
        raise HTTPException(status_code=403, detail="Not your patient")
    return _directive_json(directive)


@router.post("/directives", status_code=status.HTTP_201_CREATED, response_model=ConsentDirectiveOut)
def create_directive(
    body: ConsentDirectiveCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_SIGN_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    directive = consent_service.create_directive(
        db, pid,
        permissions=body.permissions,
        restrictions=body.restrictions,
        guardian_rules=body.guardian_rules,
        signer=body.signer or current.full_name,
        witness=body.witness,
        training_opt_in=body.training_opt_in,
        post_death_policy=body.post_death_policy,
    )
    audit_service.log_action(db, current.id, "signed", "consent_directive", directive.id,
                             {"patient_id": pid, "version": directive.version})
    db.commit()
    return ConsentDirectiveOut.model_validate(directive)


@router.get("/third-parties")
def list_third_party(
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    records = consent_service.list_third_party(db, pid)
    return {"items": [_third_party_json(c) for c in records], "count": len(records)}


@router.post("/third-parties", status_code=status.HTTP_201_CREATED,
             response_model=ThirdPartyConsentOut)
def create_third_party(
    body: ThirdPartyConsentCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_MANAGE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    record = consent_service.create_third_party(
        db, pid,
        person_name=body.person_name,
        person_id=body.person_id,
        contact=body.contact,
        consent_given=body.consent_given,
        notes=body.notes,
    )
    audit_service.log_action(db, current.id, "created", "third_party_consent", record.id,
                             {"patient_id": pid, "person_name": record.person_name})
    db.commit()
    return ThirdPartyConsentOut.model_validate(record)


@router.patch("/third-parties/{record_id}", response_model=ThirdPartyConsentOut)
def update_third_party(
    record_id: str,
    body: ThirdPartyConsentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_MANAGE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    record = consent_service.get_third_party(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Consent record not found")
    if scope is not None and scope != record.patient_id:
        raise HTTPException(status_code=403, detail="Not your patient")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    consent_service.update_third_party(db, record, fields=fields)
    audit_service.log_action(db, current.id, "updated", "third_party_consent", record.id)
    db.commit()
    return ThirdPartyConsentOut.model_validate(record)


@router.delete("/third-parties/{record_id}")
def delete_third_party(
    record_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_MANAGE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    record = consent_service.get_third_party(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Consent record not found")
    if scope is not None and scope != record.patient_id:
        raise HTTPException(status_code=403, detail="Not your patient")
    db.delete(record)
    audit_service.log_action(db, current.id, "deleted", "third_party_consent", record_id)
    db.commit()
    return {"ok": True}
