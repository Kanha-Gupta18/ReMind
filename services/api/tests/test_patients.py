"""Patient onboarding, profile, and relationship authorization."""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.base import new_id
from app.models.constants import ConsentAction, Role, SourceType
from app.models.user import User
from tests.conftest import PASSWORD, auth, delete_users


def _profile_payload(name="Kanha"):
    return {
        "preferred_name": name,
        "preferred_language": "en-IN",
        "accessibility_profile": {
            "text_size": "large",
            "high_contrast": True,
            "reduced_motion": True,
            "narration_auto_start": False,
            "simplified_navigation": True,
        },
        "date_of_birth": "1950-01-02",
        "diagnosis": "Mild cognitive impairment",
        "diagnosis_date": "2025-02-03",
        "cognition_level": "early",
        "safety_level": "NORMAL",
        "status": "active",
    }


def _initial_consent():
    return {
        "permissions": {
            "allowed_data_sources": [source.value for source in SourceType],
            "role_actions": {
                Role.FAMILY_CONTRIBUTOR.value: [
                    ConsentAction.SOURCES_VIEW.value,
                    ConsentAction.SOURCES_UPLOAD.value,
                ],
            },
            "third_party_visibility": "consented_only",
        },
        "restrictions": {
            "prohibited_data_categories": [],
            "blocked_person_ids": [],
        },
        "guardian_rules": {
            "guardian_id": None,
            "authority": "none",
            "allowed_actions": [],
        },
        "training_opt_in": False,
    }


def test_patient_completes_profile_and_first_consent_atomically(client):
    user_id = new_id()
    email = f"onboarding.{user_id}@remind.dev"
    with SessionLocal() as db:
        db.add(User(
            id=user_id,
            email=email,
            password_hash=hash_password(PASSWORD),
            full_name="Onboarding Patient",
            role=Role.PATIENT.value,
        ))
        db.commit()
    try:
        token = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
            "access_token"
        ]
        response = client.post(
            "/patients/onboarding",
            json={"profile": _profile_payload("Kanha"), "consent": _initial_consent()},
            headers=auth(token),
        )
        assert response.status_code == 201
        assert response.json()["profile"]["preferred_name"] == "Kanha"
        assert response.json()["consent"]["version"] == 1
        assert response.json()["consent"]["signed_by_user_id"] == user_id
        assert client.post(
            "/patients/onboarding",
            json={"profile": _profile_payload(), "consent": _initial_consent()},
            headers=auth(token),
        ).status_code == 409
    finally:
        with SessionLocal() as db:
            delete_users(db, [user_id])


def test_profile_access_follows_role_and_consent(client, tokens):
    patient_profile = client.get("/patients/profile", headers=auth(tokens["patient"]))
    assert patient_profile.status_code == 200

    clinician_profile = client.get("/patients/profile", headers=auth(tokens["clinician"]))
    assert clinician_profile.status_code == 200
    assert client.patch(
        "/patients/profile",
        json={"preferred_name": "Not allowed"},
        headers=auth(tokens["clinician"]),
    ).status_code == 403

    updated = client.patch(
        "/patients/profile",
        json={"preferred_name": "Preferred patient name"},
        headers=auth(tokens["patient"]),
    )
    assert updated.status_code == 200
    assert updated.json()["preferred_name"] == "Preferred patient name"


def test_relationship_grant_and_revocation_change_access_immediately(client, tokens, users):
    user_id = new_id()
    email = f"new-family.{user_id}@remind.dev"
    with SessionLocal() as db:
        db.add(User(
            id=user_id,
            email=email,
            password_hash=hash_password(PASSWORD),
            full_name="New Family Member",
            role=Role.FAMILY_CONTRIBUTOR.value,
        ))
        db.commit()
    try:
        granted = client.post(
            "/patients/relationships",
            json={"user_email": email, "relationship": "daughter"},
            headers=auth(tokens["patient"]),
        )
        assert granted.status_code == 201
        assert granted.json()["relationship"] == "daughter"

        family_token = client.post(
            "/auth/login", json={"email": email, "password": PASSWORD}
        ).json()["access_token"]
        assert client.get("/sources", headers=auth(family_token)).status_code == 200

        revoked = client.delete(
            f"/patients/relationships/{granted.json()['id']}",
            headers=auth(tokens["patient"]),
        )
        assert revoked.status_code == 200
        assert client.get("/sources", headers=auth(family_token)).status_code == 403

        history = client.get(
            "/patients/relationships", headers=auth(tokens["patient"])
        ).json()["items"]
        record = next(item for item in history if item["id"] == granted.json()["id"])
        assert record["status"] == "revoked"
    finally:
        with SessionLocal() as db:
            delete_users(db, [user_id])


def test_administrator_cannot_read_patient_profile(client, tokens, users):
    response = client.get(
        "/patients/profile",
        params={"patient_id": users["patient"].id},
        headers=auth(tokens["admin"]),
    )
    assert response.status_code == 403


def test_available_patients_contains_only_active_relationships(client, tokens, users):
    response = client.get("/patients/available", headers=auth(tokens["reviewer"]))
    assert response.status_code == 200
    assert response.json()["items"] == [{
        "id": users["patient"].id,
        "preferred_name": users["patient"].full_name,
    }]
    assert client.get(
        "/patients/available", headers=auth(tokens["admin"])
    ).json()["items"] == []
