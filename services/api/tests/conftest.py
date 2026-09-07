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
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models.base import new_id
from app.models.clinical import EngagementLog, Notification
from app.models.constants import Role, SafetyLevel
from app.models.consent import ConsentDirective
from app.models.conversation import ConversationMessage, ConversationSession, SafetyEvent
from app.models.graph import GraphEdge, GraphNode
from app.models.memory import Evidence, MemoryCard, MemoryRevision, Source
from app.models.people import FaceMatch, Person
from app.models.user import AuditLog, PatientProfile, ThirdPartyConsent, User

PASSWORD = "testpass123"
TEST_DOMAIN = "@remind.dev"


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
    db.query(Person).filter(Person.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(ThirdPartyConsent).filter(ThirdPartyConsent.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(ConsentDirective).filter(ConsentDirective.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(Notification).filter(Notification.user_id.in_(user_ids)).delete(
        synchronize_session=False)
    memory_ids = db.query(MemoryCard.id).filter(MemoryCard.patient_id.in_(user_ids))
    db.query(MemoryRevision).filter(MemoryRevision.memory_id.in_(memory_ids)).delete(
        synchronize_session=False)
    db.query(Evidence).filter(Evidence.memory_id.in_(memory_ids)).delete(
        synchronize_session=False)
    db.query(EngagementLog).filter(EngagementLog.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(MemoryCard).filter(MemoryCard.patient_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(Source).filter(Source.patient_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


def delete_users(db: Session, user_ids: list[str]) -> None:
    """Wipe resources, detach family links, then drop the users themselves."""
    db.query(User).filter(User.patient_id.in_(user_ids)).update(
        {"patient_id": None}, synchronize_session=False)
    wipe(db, user_ids)
    db.query(PatientProfile).filter(PatientProfile.user_id.in_(user_ids)).delete(
        synchronize_session=False)
    db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


def _make_user(db: Session, email: str, role: str, patient_id: str | None = None) -> User:
    user = User(email=email, password_hash=hash_password(PASSWORD),
                full_name=role, role=role, patient_id=patient_id)
    db.add(user)
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
    db.add(PatientProfile(user_id=patient.id, safety_level=SafetyLevel.NORMAL.value))
    db.add(PatientProfile(user_id=patient2.id, safety_level=SafetyLevel.NORMAL.value))
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
    """Access token per role, minted once per session (JWTs are stateless)."""
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
    db.close()
    yield


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
