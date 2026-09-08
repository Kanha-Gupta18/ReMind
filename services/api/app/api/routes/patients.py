"""Patient onboarding, profile management, and consent-scoped relationships."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_consent_action, require_roles
from app.core.database import get_db
from app.models.base import utcnow
from app.models.constants import AccessGrantStatus, ConsentAction, Role
from app.models.user import PatientAccessGrant, PatientProfile, User
from app.schemas.consent import ConsentDirectiveOut
from app.schemas.patient import (
    PatientOnboardingOut,
    PatientOnboardingRequest,
    PatientCapabilitiesOut,
    PatientProfileCreate,
    PatientProfileOut,
    PatientProfileUpdate,
    RelationshipCreate,
    RelationshipOut,
)
from app.services import audit_service, consent_service

router = APIRouter(prefix="/patients", tags=["patients"])


def _profile(db: Session, patient_id: str) -> PatientProfile | None:
    return db.query(PatientProfile).filter(PatientProfile.user_id == patient_id).first()


def _apply_profile(profile: PatientProfile, fields: dict) -> None:
    for key, value in fields.items():
        setattr(profile, key, value)


def _profile_fields(body, *, exclude_unset: bool = False) -> dict:
    fields = body.model_dump(exclude_unset=exclude_unset)
    accessibility = fields.get("accessibility_profile")
    if accessibility is not None and hasattr(accessibility, "model_dump"):
        fields["accessibility_profile"] = accessibility.model_dump(mode="json")
    return fields


def _relationship_out(grant: PatientAccessGrant, user: User) -> RelationshipOut:
    return RelationshipOut(
        id=grant.id,
        user_id=user.id,
        patient_id=grant.patient_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        relationship=grant.relationship,
        status=grant.status,
        granted_by=grant.granted_by,
        created_at=grant.created_at,
        revoked_at=grant.revoked_at,
    )


@router.get("/available")
def available_patients(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    """Return only the patient identities attached to this account."""
    if current.role == Role.ADMINISTRATOR.value:
        return {"items": [], "count": 0}
    if current.role == Role.PATIENT.value:
        profile = _profile(db, current.id)
        items = [{
            "id": current.id,
            "preferred_name": profile.preferred_name if profile else current.full_name,
        }]
        return {"items": items, "count": 1}
    rows = (
        db.query(PatientAccessGrant, User, PatientProfile)
        .join(User, User.id == PatientAccessGrant.patient_id)
        .outerjoin(PatientProfile, PatientProfile.user_id == User.id)
        .filter(
            PatientAccessGrant.user_id == current.id,
            PatientAccessGrant.status == AccessGrantStatus.ACTIVE.value,
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    items = [{
        "id": patient.id,
        "preferred_name": profile.preferred_name if profile else patient.full_name,
    } for _, patient, profile in rows]
    return {"items": items, "count": len(items)}


@router.get("/capabilities", response_model=PatientCapabilitiesOut)
def patient_capabilities(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    """Return the actions currently allowed for this account and patient."""
    return PatientCapabilitiesOut(actions=[
        action for action in ConsentAction
        if consent_service.action_is_allowed(db, current, scope, action)
    ])


@router.post("/onboarding", response_model=PatientOnboardingOut,
             status_code=status.HTTP_201_CREATED)
def complete_onboarding(
    body: PatientOnboardingRequest,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(Role.PATIENT.value))],
):
    """Atomically establish the patient's profile and first signed directive."""
    if consent_service.current_directive(db, current.id) is not None:
        raise HTTPException(status_code=409, detail="Patient onboarding is already complete")
    if not consent_service.guardian_nomination_is_valid(
        db, current.id, body.consent.guardian_rules.guardian_id
    ):
        raise HTTPException(status_code=422, detail="guardian_id must identify an active guardian")

    profile = _profile(db, current.id)
    fields = _profile_fields(body.profile)
    if profile is None:
        profile = PatientProfile(user_id=current.id, **fields)
        db.add(profile)
    else:
        _apply_profile(profile, fields)

    consent = body.consent
    directive = consent_service.create_directive(
        db,
        current.id,
        permissions=consent.permissions.model_dump(mode="json"),
        restrictions=consent.restrictions.model_dump(mode="json"),
        guardian_rules=consent.guardian_rules.model_dump(mode="json"),
        signer=consent.signer or current.full_name,
        signed_by_user_id=current.id,
        witness=consent.witness,
        training_opt_in=consent.training_opt_in,
        post_death_policy=consent.post_death_policy.model_dump(mode="json"),
    )
    db.flush()
    audit_service.log_action(
        db, current.id, "completed", "patient_onboarding", current.id,
        {"consent_version": directive.version},
    )
    db.commit()
    db.refresh(profile)
    db.refresh(directive)
    return PatientOnboardingOut(
        profile=PatientProfileOut.model_validate(profile),
        consent=ConsentDirectiveOut.model_validate(directive),
    )


@router.get("/profile", response_model=PatientProfileOut)
def get_profile(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    require_consent_action(db, current, scope, ConsentAction.PROFILE_VIEW)
    profile = _profile(db, scope)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient profile has not been created")
    return PatientProfileOut.model_validate(profile)


@router.put("/profile", response_model=PatientProfileOut,
            status_code=status.HTTP_201_CREATED)
def create_profile(
    body: PatientProfileCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    require_consent_action(db, current, scope, ConsentAction.PROFILE_EDIT)
    if _profile(db, scope) is not None:
        raise HTTPException(status_code=409, detail="Patient profile already exists")
    profile = PatientProfile(user_id=scope, **_profile_fields(body))
    db.add(profile)
    audit_service.log_action(db, current.id, "created", "patient_profile", scope)
    db.commit()
    db.refresh(profile)
    return PatientProfileOut.model_validate(profile)


@router.patch("/profile", response_model=PatientProfileOut)
def update_profile(
    body: PatientProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    require_consent_action(db, current, scope, ConsentAction.PROFILE_EDIT)
    profile = _profile(db, scope)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient profile has not been created")
    fields = _profile_fields(body, exclude_unset=True)
    proposed_diagnosis = fields.get("diagnosis", profile.diagnosis)
    proposed_diagnosis_date = fields.get("diagnosis_date", profile.diagnosis_date)
    if proposed_diagnosis_date is not None and not proposed_diagnosis:
        raise HTTPException(status_code=422, detail="diagnosis_date requires a diagnosis")
    _apply_profile(profile, fields)
    audit_service.log_action(
        db, current.id, "updated", "patient_profile", scope,
        {"fields": sorted(fields)},
    )
    db.commit()
    db.refresh(profile)
    return PatientProfileOut.model_validate(profile)


@router.get("/relationships")
def list_relationships(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    require_consent_action(db, current, scope, ConsentAction.RELATIONSHIPS_VIEW)
    rows = (
        db.query(PatientAccessGrant, User)
        .join(User, User.id == PatientAccessGrant.user_id)
        .filter(PatientAccessGrant.patient_id == scope)
        .order_by(PatientAccessGrant.created_at.desc())
        .all()
    )
    items = [_relationship_out(grant, user) for grant, user in rows]
    return {"items": items, "count": len(items)}


@router.post("/relationships", response_model=RelationshipOut,
             status_code=status.HTTP_201_CREATED)
def grant_relationship(
    body: RelationshipCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    require_consent_action(db, current, scope, ConsentAction.RELATIONSHIPS_MANAGE)
    target = db.query(User).filter(User.email == body.user_email).first()
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="Active account not found")
    if target.id == scope or target.role in {Role.PATIENT.value, Role.ADMINISTRATOR.value}:
        raise HTTPException(status_code=422, detail="This account cannot receive a patient relationship")

    grant = db.query(PatientAccessGrant).filter(
        PatientAccessGrant.user_id == target.id,
        PatientAccessGrant.patient_id == scope,
    ).first()
    if grant is None:
        grant = PatientAccessGrant(
            user_id=target.id,
            patient_id=scope,
            relationship=body.relationship,
            granted_by=current.id,
        )
        db.add(grant)
    else:
        grant.relationship = body.relationship
        grant.status = AccessGrantStatus.ACTIVE.value
        grant.granted_by = current.id
        grant.revoked_at = None
    db.flush()
    audit_service.log_action(
        db, current.id, "granted", "patient_relationship", grant.id,
        {"patient_id": scope, "user_id": target.id, "role": target.role},
    )
    db.commit()
    db.refresh(grant)
    return _relationship_out(grant, target)


@router.delete("/relationships/{grant_id}")
def revoke_relationship(
    grant_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    scope: Annotated[str, Depends(get_patient_scope)],
):
    require_consent_action(db, current, scope, ConsentAction.RELATIONSHIPS_MANAGE)
    grant = db.get(PatientAccessGrant, grant_id)
    if grant is None or grant.patient_id != scope:
        raise HTTPException(status_code=404, detail="Patient relationship not found")
    if grant.status == AccessGrantStatus.ACTIVE.value:
        grant.status = AccessGrantStatus.REVOKED.value
        grant.revoked_at = utcnow()
        audit_service.log_action(
            db, current.id, "revoked", "patient_relationship", grant.id,
            {"patient_id": scope, "user_id": grant.user_id},
        )
        db.commit()
    return {"ok": True}
