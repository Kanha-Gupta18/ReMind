"""Shared fixtures for the API test suite.

Tests run against a dedicated PostgreSQL database (`remind_test`) so the
development data is never touched. A unique schema is migrated and removed
once per pytest session, and each test wipes the rows its own users own,
so tests stay independent.

Run from `services/api`:
    venv\\Scripts\\python.exe -m pytest

The test DB is chosen by TEST_DATABASE_URL (defaults to the local
`remind_test` database, owned by the `remind` role).
"""

import os
import shutil
from tests import runtime

# Point the app at the dedicated test database BEFORE any app module is
# imported, because `app.core.config.Settings` reads DATABASE_URL once at
# import time (real env vars win over the .env file).
TEST_DATABASE_URL = runtime.SCOPED_DATABASE_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Uploaded files must land in a throwaway temp directory, never the dev
# storage folder. Same rule as the DB: set before the app is imported.
# conftest.py is imported twice (as a pytest plugin and as `tests.conftest`
# via `from tests.conftest import ...`), so reuse the env value if present
# rather than creating two different temp dirs.
TEST_STORAGE_DIR = runtime.STORAGE_DIR
os.environ["STORAGE_DIR"] = TEST_STORAGE_DIR

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models.base import new_id
from app.models.clinical import EngagementLog, Notification
from app.models.constants import ConsentAction, Role, SafetyLevel, SourceType
from app.models.consent import ConsentDirective
from app.models.conversation import ConversationMessage, ConversationSession, SafetyEvent
from app.models.graph import GraphEdge, GraphNode
from app.models.knowledge import Event, MemoryEventLink, MemoryPersonLink, MemoryPlaceLink, Place
from app.models.memory import Evidence, MemoryCard, MemoryReviewRecord, MemoryRevision, Source
from app.models.people import FaceMatch, Person
from app.models.user import AuthSession, AuditLog, PatientAccessGrant, PatientProfile, ThirdPartyConsent, User

PASSWORD = "testpass123"
TEST_DOMAIN = "@remind.dev"

DEFAULT_ROLE_ACTIONS = {
    Role.FAMILY_CONTRIBUTOR.value: [
        ConsentAction.CONSENT_VIEW.value,
        ConsentAction.SOURCES_VIEW.value,
        ConsentAction.SOURCES_UPLOAD.value,
        ConsentAction.SOURCES_PROCESS.value,
        ConsentAction.SOURCES_DELETE.value,
        ConsentAction.MEMORIES_VIEW.value,
        ConsentAction.MEMORIES_CREATE.value,
        ConsentAction.PEOPLE_VIEW.value,
        ConsentAction.PEOPLE_CREATE.value,
        ConsentAction.GRAPH_VIEW.value,
        ConsentAction.GRAPH_EDIT.value,
    ],
    Role.FAMILY_REVIEWER.value: [action.value for action in ConsentAction],
    Role.CAREGIVER.value: [
        ConsentAction.CONSENT_VIEW.value,
        ConsentAction.SOURCES_VIEW.value,
        ConsentAction.MEMORIES_VIEW.value,
        ConsentAction.PEOPLE_VIEW.value,
        ConsentAction.GRAPH_VIEW.value,
        ConsentAction.CONVERSATIONS_VIEW.value,
        ConsentAction.SAFETY_VIEW.value,
        ConsentAction.SAFETY_MANAGE.value,
        ConsentAction.ENGAGEMENT_VIEW.value,
    ],
    Role.GUARDIAN.value: [action.value for action in ConsentAction],
    Role.CLINICIAN.value: [
        ConsentAction.PROFILE_VIEW.value,
        ConsentAction.CONSENT_VIEW.value,
        ConsentAction.MEMORIES_VIEW.value,
        ConsentAction.PEOPLE_VIEW.value,
        ConsentAction.GRAPH_VIEW.value,
        ConsentAction.CONVERSATIONS_VIEW.value,
        ConsentAction.SAFETY_VIEW.value,
        ConsentAction.ENGAGEMENT_VIEW.value,
    ],
}


@pytest.fixture(scope="session", autouse=True)
def _test_db_schema():
    """Migrate an isolated schema, then remove only resources this run owns."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import close_all_sessions

    control = create_engine(runtime.DATABASE_URL)
    try:
        with control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{runtime.SCHEMA}"'))
        command.upgrade(Config("alembic.ini"), "head")
        command.check(Config("alembic.ini"))
        yield
    finally:
        close_all_sessions()
        engine.dispose()
        with control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{runtime.SCHEMA}" CASCADE'))
        control.dispose()
        shutil.rmtree(runtime.STORAGE_DIR)


def wipe(db: Session, user_ids: list[str]) -> None:
    """Delete resources owned by the given user ids, keeping the users.

    Order matters: children first, parents last (FK constraints).
    """
    if not user_ids:
        return
    db.query(ConversationMessage).delete(synchronize_session=False)
    for c in [SafetyEvent, ConversationSession, GraphEdge, GraphNode, FaceMatch]:
        db.query(c).filter(c.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(ThirdPartyConsent).filter(ThirdPartyConsent.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(ConsentDirective).filter(ConsentDirective.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(Notification).filter(or_(
        Notification.user_id.in_(user_ids),
        Notification.patient_id.in_(user_ids),
    )).delete(
        synchronize_session=False)
    memory_ids = db.query(MemoryCard.id).filter(MemoryCard.patient_id.in_(user_ids))
    db.query(Evidence).filter(Evidence.memory_id.in_(memory_ids)).delete(
        synchronize_session=False)
    db.query(MemoryReviewRecord).filter(MemoryReviewRecord.memory_id.in_(memory_ids)).delete(
        synchronize_session=False)
    for link in (MemoryPersonLink, MemoryPlaceLink, MemoryEventLink):
        db.query(link).filter(link.memory_id.in_(memory_ids)).delete(synchronize_session=False)
    db.query(EngagementLog).filter(EngagementLog.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(MemoryCard).filter(MemoryCard.patient_id.in_(user_ids)).update(
        {MemoryCard.approved_revision_id: None, MemoryCard.candidate_revision_id: None},
        synchronize_session=False,
    )
    db.query(MemoryRevision).filter(MemoryRevision.memory_id.in_(memory_ids)).delete(
        synchronize_session=False)
    db.query(MemoryCard).filter(MemoryCard.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(Place).filter(Place.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(Event).filter(Event.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(Person).filter(Person.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(Source).filter(Source.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


def delete_users(db: Session, user_ids: list[str]) -> None:
    """Wipe resources, detach family links, then drop the users themselves."""
    db.query(AuthSession).filter(AuthSession.user_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(PatientAccessGrant).filter(or_(
        PatientAccessGrant.user_id.in_(user_ids),
        PatientAccessGrant.patient_id.in_(user_ids),
        PatientAccessGrant.granted_by.in_(user_ids),
    )).delete(synchronize_session=False)
    wipe(db, user_ids)
    db.query(PatientProfile).filter(PatientProfile.user_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


def _make_user(db: Session, email: str, role: str, patient_id: str | None = None) -> User:
    user = User(email=email, password_hash=hash_password(PASSWORD),
                full_name=role, role=role)
    db.add(user)
    db.flush()
    if patient_id:
        db.add(PatientAccessGrant(
            user_id=user.id,
            patient_id=patient_id,
            relationship=role,
        ))
        db.flush()
    return user


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def users(_test_db_schema) -> dict[str, User]:
    """Seed one user per role (plus a second patient for §24 isolation tests)."""
    db: Session = SessionLocal()
    delete_users(db, [u.id for u in db.query(User).filter(User.email.like(f"%{TEST_DOMAIN}")).all()])
    suffix = new_id()[:8]
    em = lambda role: f"{role}.{suffix}{TEST_DOMAIN}"

    patient = _make_user(db, em("patient"), Role.PATIENT.value)
    patient2 = _make_user(db, em("patient2"), Role.PATIENT.value)
    contributor = _make_user(db, em("contributor"), Role.FAMILY_CONTRIBUTOR.value, patient.id)
    reviewer = _make_user(db, em("reviewer"), Role.FAMILY_REVIEWER.value, patient.id)
    caregiver = _make_user(db, em("caregiver"), Role.CAREGIVER.value, patient.id)
    clinician = _make_user(db, em("clinician"), Role.CLINICIAN.value, patient.id)
    guardian = _make_user(db, em("guardian"), Role.GUARDIAN.value, patient.id)
    admin = _make_user(db, em("admin"), Role.ADMINISTRATOR.value)
    contributor2 = _make_user(db, em("contributor2"), Role.FAMILY_CONTRIBUTOR.value, patient2.id)
    db.add(PatientProfile(user_id=patient.id, preferred_name=patient.full_name,
                          safety_level=SafetyLevel.NORMAL.value))
    db.add(PatientProfile(user_id=patient2.id, preferred_name=patient2.full_name,
                          safety_level=SafetyLevel.NORMAL.value))
    db.commit()

    result = {
        "patient": patient, "patient2": patient2,
        "contributor": contributor, "reviewer": reviewer,
        "caregiver": caregiver, "clinician": clinician,
        "guardian": guardian, "admin": admin, "contributor2": contributor2,
    }
    yield result

    db = SessionLocal()
    delete_users(db, [u.id for u in result.values()])
    db.close()


@pytest.fixture(scope="session")
def tokens(client: TestClient, users: dict[str, User]) -> dict[str, str]:
    """Access token per role, minted once per server-backed session."""
    out = {}
    for name, user in users.items():
        r = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
        assert r.status_code == 200, f"login failed for {name}: {r.text}"
        out[name] = r.json()["access_token"]
    return out


@pytest.fixture(autouse=True)
def _clean_slate(users: dict[str, User]):
    """Wipe all test-owned resources before each test."""
    db = SessionLocal()
    wipe(db, [u.id for u in users.values()])
    for patient_key, guardian_key in (("patient", "guardian"), ("patient2", None)):
        patient = users[patient_key]
        guardian = users[guardian_key] if guardian_key else None
        profile = db.query(PatientProfile).filter(PatientProfile.user_id == patient.id).first()
        profile.preferred_name = patient.full_name
        profile.preferred_language = "en"
        profile.accessibility_profile = {}
        profile.date_of_birth = None
        profile.diagnosis = None
        profile.diagnosis_date = None
        profile.cognition_level = None
        profile.safety_level = SafetyLevel.NORMAL.value
        profile.status = "active"
        guardian_actions = DEFAULT_ROLE_ACTIONS[Role.GUARDIAN.value] if guardian else []
        db.add(ConsentDirective(
            patient_id=patient.id,
            version=1,
            permissions={
                "allowed_data_sources": [source.value for source in SourceType],
                "role_actions": DEFAULT_ROLE_ACTIONS,
                "third_party_visibility": "family_reviewed",
            },
            restrictions={
                "prohibited_data_categories": [],
                "blocked_person_ids": [],
            },
            guardian_rules={
                "guardian_id": guardian.id if guardian else None,
                "authority": "shared" if guardian else "none",
                "allowed_actions": guardian_actions,
            },
            signer=patient.full_name,
            signed_by_user_id=patient.id,
            post_death_policy={"mode": "keep_private"},
        ))
    db.commit()
    db.close()
    yield


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
