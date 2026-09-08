"""Consent directives + third-party consent (spec §17, §24)."""

from tests.conftest import auth


def _guardian_policy(users, allowed_sources=None):
    view = ["consent:view"]
    guardian = ["consent:view", "consent:manage"]
    return {
        "permissions": {
            "allowed_data_sources": allowed_sources or ["photo", "video"],
            "role_actions": {
                "family_contributor": view,
                "family_reviewer": view,
                "caregiver": view,
                "guardian": guardian,
                "clinician": view,
            },
            "third_party_visibility": "family_reviewed",
        },
        "restrictions": {
            "prohibited_data_categories": [],
            "blocked_person_ids": [],
        },
        "guardian_rules": {
            "guardian_id": users["guardian"].id,
            "authority": "shared",
            "allowed_actions": guardian,
        },
    }


def test_directive_versioning(client, tokens, users):
    r = client.post("/consent/directives", json={
        **_guardian_policy(users), "signer": "Patient Self",
    }, headers=auth(tokens["patient"]))
    assert r.status_code == 201
    v2 = r.json()
    assert v2["version"] == 2 and v2["supersedes_id"] is not None

    r = client.post("/consent/directives", json={
        **_guardian_policy(users, ["photo"]), "training_opt_in": False,
    }, headers=auth(tokens["guardian"]))
    assert r.status_code == 201
    v3 = r.json()
    assert v3["version"] == 3 and v3["supersedes_id"] == v2["id"]

    r = client.get("/consent/directives", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    versions = [d["version"] for d in r.json()["items"]]
    assert versions == [3, 2, 1]

    r = client.get(f"/consent/directives/{v2['id']}", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and r.json()["version"] == 2


def test_directive_sign_rbac(client, tokens, users):
    for role in ("contributor", "reviewer", "caregiver", "clinician"):
        r = client.post("/consent/directives", json={"permissions": {}},
                        headers=auth(tokens[role]))
        assert r.status_code == 403, role

    r = client.post("/consent/directives", json=_guardian_policy(users),
                    headers=auth(tokens["patient"]))
    assert r.status_code == 201
    r = client.post("/consent/directives", json=_guardian_policy(users, ["photo"]),
                    headers=auth(tokens["guardian"]))
    assert r.status_code == 201

    r = client.post("/consent/directives", json={"permissions": {}},
                    params={"patient_id": users["patient"].id},
                    headers=auth(tokens["admin"]))
    assert r.status_code == 403


def test_directive_view_open_to_all_in_scope(client, tokens):
    for role in ("patient", "contributor", "reviewer", "caregiver", "clinician", "guardian"):
        r = client.get("/consent/directives", headers=auth(tokens[role]))
        assert r.status_code == 200 and r.json()["count"] >= 1, role


def test_third_party_crud(client, tokens):
    r = client.post("/consent/third-parties", json={
        "person_name": "Ramesh", "consent_given": True, "contact": "ramesh@example.com",
    }, headers=auth(tokens["guardian"]))
    assert r.status_code == 201
    rec = r.json()
    assert rec["person_name"] == "Ramesh" and rec["consent_given"] is True

    r = client.patch(f"/consent/third-parties/{rec['id']}",
                     json={"consent_given": False, "notes": "requested removal"},
                     headers=auth(tokens["guardian"]))
    assert r.status_code == 200
    assert r.json()["consent_given"] is False
    assert r.json()["notes"] == "requested removal"

    r = client.delete(f"/consent/third-parties/{rec['id']}", headers=auth(tokens["guardian"]))
    assert r.status_code == 200
    r = client.get("/consent/third-parties", headers=auth(tokens["guardian"]))
    assert r.json()["count"] == 0


def test_third_party_manage_rbac(client, tokens):
    r = client.post("/consent/third-parties", json={"person_name": "X"},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 201
    for role in ("contributor", "reviewer", "caregiver", "clinician"):
        r = client.post("/consent/third-parties", json={"person_name": "X"},
                        headers=auth(tokens[role]))
        assert r.status_code == 403, role


def test_consent_patient_isolation(client, tokens):
    r = client.post("/consent/third-parties", json={"person_name": "Ramesh"},
                    headers=auth(tokens["guardian"]))
    assert r.status_code == 201
    rec = r.json()

    r = client.get("/consent/third-parties", headers=auth(tokens["contributor2"]))
    assert r.status_code == 200
    assert all(item["patient_id"] != rec["patient_id"] for item in r.json()["items"])

    r = client.patch(f"/consent/third-parties/{rec['id']}", json={"consent_given": True},
                     headers=auth(tokens["contributor2"]))
    assert r.status_code == 403

    client.post("/consent/directives", json={"permissions": {}},
                headers=auth(tokens["patient"]))
    r = client.get("/consent/directives", headers=auth(tokens["contributor2"]))
    assert all(item["patient_id"] != rec["patient_id"] for item in r.json()["items"])


def test_admin_must_pick_patient(client, tokens, users):
    r = client.get("/consent/directives", headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.get("/consent/directives",
                   params={"patient_id": users["patient"].id},
                   headers=auth(tokens["admin"]))
    assert r.status_code == 403

    r = client.post("/consent/third-parties", json={"person_name": "X"},
                    headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.post("/consent/third-parties", json={"person_name": "X"},
                    params={"patient_id": users["patient"].id},
                    headers=auth(tokens["admin"]))
    assert r.status_code == 403
