"""Consent directives and third-party consent (spec §17, §24).

Every new directive supersedes the previous one, forming an auditable
version chain (supersedes_id + version) so consent history is never lost.
Third-party consent records who appears in the patient's data and whether
that person has been informed / asked for removal (ethical framework §1).
"""

from sqlalchemy.orm import Session

from app.models.consent import ConsentDirective as Directive
from app.models.user import ThirdPartyConsent


def list_directives(db: Session, patient_id: str) -> list[Directive]:
    return (db.query(Directive)
            .filter(Directive.patient_id == patient_id)
            .order_by(Directive.version.desc())
            .all())


def get_directive(db: Session, directive_id: str) -> Directive | None:
    return db.get(Directive, directive_id)


def create_directive(
    db: Session,
    patient_id: str,
    *,
    permissions: dict | None = None,
    restrictions: dict | None = None,
    guardian_rules: dict | None = None,
    signer: str | None = None,
    witness: str | None = None,
    training_opt_in: bool = False,
    post_death_policy: dict | None = None,
) -> Directive:
    """Sign a new consent directive, superseding the current one."""
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
        witness=witness,
        training_opt_in=training_opt_in,
        post_death_policy=post_death_policy,
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
