"""Consent directives and third-party consent (spec §17, §24).

Every new directive supersedes the previous one, forming an auditable
version chain (supersedes_id + version) so consent history is never lost.
Third-party consent records who appears in the patient's data and whether
that person has been informed / asked for removal (ethical framework §1).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.constants import AccessGrantStatus, ConsentAction, Role
from app.models.consent import ConsentDirective as Directive
from app.models.user import PatientAccessGrant, ThirdPartyConsent, User


def list_directives(db: Session, patient_id: str) -> list[Directive]:
    return (db.query(Directive)
            .filter(Directive.patient_id == patient_id)
            .order_by(Directive.version.desc())
            .all())


def get_directive(db: Session, directive_id: str) -> Directive | None:
    return db.get(Directive, directive_id)


def current_directive(db: Session, patient_id: str) -> Directive | None:
    return (
        db.query(Directive)
        .filter(Directive.patient_id == patient_id)
        .order_by(Directive.version.desc())
        .first()
    )


def active_grant(db: Session, user_id: str, patient_id: str) -> PatientAccessGrant | None:
    return db.query(PatientAccessGrant).filter(
        PatientAccessGrant.user_id == user_id,
        PatientAccessGrant.patient_id == patient_id,
        PatientAccessGrant.status == AccessGrantStatus.ACTIVE.value,
    ).first()


def action_is_allowed(
    db: Session,
    user: User,
    patient_id: str,
    action: str | ConsentAction,
) -> bool:
    """Apply account role, active relationship, and the latest directive."""
    action_value = action.value if isinstance(action, ConsentAction) else action
    if user.role == Role.PATIENT.value:
        return user.id == patient_id
    if user.role == Role.ADMINISTRATOR.value:
        return False
    if active_grant(db, user.id, patient_id) is None:
        return False
    directive = current_directive(db, patient_id)
    if directive is None:
        return False
    role_actions = (directive.permissions or {}).get("role_actions", {})
    if action_value not in role_actions.get(user.role, []):
        return False
    if user.role != Role.GUARDIAN.value:
        return True
    rules = directive.guardian_rules or {}
    return (
        rules.get("guardian_id") == user.id
        and rules.get("authority") in {"shared", "delegated"}
        and action_value in rules.get("allowed_actions", [])
    )


def source_type_is_allowed(
    db: Session,
    user: User,
    patient_id: str,
    source_type: str,
) -> bool:
    if user.role == Role.PATIENT.value:
        return user.id == patient_id
    directive = current_directive(db, patient_id)
    return bool(
        directive
        and source_type in (directive.permissions or {}).get("allowed_data_sources", [])
    )


def content_categories_are_allowed(
    db: Session,
    patient_id: str,
    categories: list[str] | None,
) -> bool:
    directive = current_directive(db, patient_id)
    if directive is None:
        return False
    prohibited = set((directive.restrictions or {}).get("prohibited_data_categories", []))
    return prohibited.isdisjoint(categories or [])


def person_visibility_is_allowed(db: Session, person) -> bool:
    directive = current_directive(db, person.patient_id)
    if directive is None:
        return False
    restrictions = directive.restrictions or {}
    if person.id in restrictions.get("blocked_person_ids", []):
        return False
    mode = (directive.permissions or {}).get("third_party_visibility", "consented_only")
    if mode == "family_reviewed":
        return True
    return db.query(ThirdPartyConsent).filter(
        ThirdPartyConsent.patient_id == person.patient_id,
        ThirdPartyConsent.person_id == person.id,
        ThirdPartyConsent.consent_given.is_(True),
    ).first() is not None


def guardian_revision_is_restrictive(previous: Directive, body) -> bool:
    """Guardians may narrow a directive but cannot expand their own authority."""
    old_permissions = previous.permissions or {}
    new_permissions = body.permissions.model_dump(mode="json")
    if not set(new_permissions["allowed_data_sources"]).issubset(
        old_permissions.get("allowed_data_sources", [])
    ):
        return False
    if new_permissions["third_party_visibility"] != old_permissions.get(
        "third_party_visibility", "consented_only"
    ):
        return False
    old_role_actions = old_permissions.get("role_actions", {})
    for role, actions in new_permissions["role_actions"].items():
        if not set(actions).issubset(old_role_actions.get(role, [])):
            return False

    old_restrictions = previous.restrictions or {}
    new_restrictions = body.restrictions.model_dump(mode="json")
    for field in ("prohibited_data_categories", "blocked_person_ids"):
        if not set(old_restrictions.get(field, [])).issubset(new_restrictions[field]):
            return False

    if body.guardian_rules.model_dump(mode="json") != (previous.guardian_rules or {}):
        return False
    if body.training_opt_in and not previous.training_opt_in:
        return False
    if body.post_death_policy.model_dump(mode="json") != previous.post_death_policy:
        return False
    return True


def guardian_nomination_is_valid(
    db: Session,
    patient_id: str,
    guardian_id: str | None,
) -> bool:
    if guardian_id is None:
        return True
    guardian = db.get(User, guardian_id)
    return bool(
        guardian
        and guardian.role == Role.GUARDIAN.value
        and guardian.is_active
        and active_grant(db, guardian.id, patient_id)
    )


def create_directive(
    db: Session,
    patient_id: str,
    *,
    permissions: dict | None = None,
    restrictions: dict | None = None,
    guardian_rules: dict | None = None,
    signer: str | None = None,
    signed_by_user_id: str | None = None,
    witness: str | None = None,
    training_opt_in: bool = False,
    post_death_policy: dict | None = None,
) -> Directive:
    """Sign a new consent directive, superseding the current one."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:patient_id))"),
        {"patient_id": patient_id},
    )
    previous = (db.query(Directive)
                .filter(Directive.patient_id == patient_id)
                .order_by(Directive.version.desc())
                .first())
    directive = Directive(
        patient_id=patient_id,
        version=(previous.version + 1) if previous else 1,
        supersedes_id=previous.id if previous else None,
        permissions=permissions or {},
        restrictions=restrictions or {},
        guardian_rules=guardian_rules or {},
        signer=signer,
        signed_by_user_id=signed_by_user_id,
        witness=witness,
        training_opt_in=training_opt_in,
        post_death_policy=post_death_policy or {"mode": "keep_private"},
    )
    db.add(directive)
    db.flush()
    return directive


def list_third_party(db: Session, patient_id: str) -> list[ThirdPartyConsent]:
    return (db.query(ThirdPartyConsent)
            .filter(ThirdPartyConsent.patient_id == patient_id)
            .order_by(ThirdPartyConsent.created_at.desc())
            .all())


def create_third_party(
    db: Session,
    patient_id: str,
    *,
    person_name: str,
    person_id: str | None = None,
    contact: str | None = None,
    consent_given: bool = False,
    notes: str | None = None,
) -> ThirdPartyConsent:
    record = ThirdPartyConsent(
        patient_id=patient_id,
        person_id=person_id,
        person_name=person_name,
        contact=contact,
        consent_given=consent_given,
        notes=notes,
    )
    db.add(record)
    db.flush()
    return record


def get_third_party(db: Session, record_id: str) -> ThirdPartyConsent | None:
    return db.get(ThirdPartyConsent, record_id)


def update_third_party(db: Session, record: ThirdPartyConsent, *, fields: dict) -> ThirdPartyConsent:
    for key, value in fields.items():
        if value is not None:
            setattr(record, key, value)
    db.flush()
    return record
