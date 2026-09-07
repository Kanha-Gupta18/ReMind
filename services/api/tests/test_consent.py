"""Consent directives + third-party consent (spec §17, §24)."""

from tests.conftest import auth


def test_directive_versioning(client, tokens):
    r = client.post("/consent/directives", json={
        "permissions": {"photos": True}, "signer": "Patient Self",
    }, headers=auth(tokens["patient"]))
    assert r.status_code == 201
    v1 = r.json()
    assert v1["version"] == 1 and v1["supersedes_id"] is None

    r = client.post("/consent/directives", json={
        "permissions": {"photos": False}, "training_opt_in": True,
    }, headers=auth(tokens["guardian"]))
    assert r.status_code == 201
    v2 = r.json()
    assert v2["version"] == 2 and v2["supersedes_id"] == v1["id"]

    r = client.get("/consent/directives", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    versions = [d["version"] for d in r.json()["items"]]
    assert versions == [2, 1]

    r = client.get(f"/consent/directives/{v1['id']}", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and r.json()["version"] == 1


def test_directive_sign_rbac(client, tokens, users):
    for role in ("contributor", "reviewer", "caregiver", "clinician"):
        r = client.post("/consent/directives", json={"permissions": {}},
                        headers=auth(tokens[role]))
        assert r.status_code == 403, role

    for role in ("patient", "guardian"):
        r = client.post("/consent/directives", json={"permissions": {}},
                        headers=auth(tokens[role]))
        assert r.status_code == 201, role

    r = client.post("/consent/directives", json={"permissions": {}},
                    params={"patient_id": users["patient"].id},
                    headers=auth(tokens["admin"]))
    assert r.status_code == 201


def test_directive_view_open_to_all_in_scope(client, tokens):
    client.post("/consent/directives", json={"permissions": {"photos": True}},
                headers=auth(tokens["guardian"]))
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
    for role in ("patient", "contributor", "reviewer", "caregiver", "clinician"):
        r = client.post("/consent/third-parties", json={"person_name": "X"},
                        headers=auth(tokens[role]))
        assert r.status_code == 403, role


def test_consent_patient_isolation(client, tokens):
    r = client.post("/consent/third-parties", json={"person_name": "Ramesh"},
                    headers=auth(tokens["guardian"]))
    assert r.status_code == 201
    rec = r.json()

    r = client.get("/consent/third-parties", headers=auth(tokens["contributor2"]))
    assert r.status_code == 200 and r.json()["count"] == 0

    r = client.patch(f"/consent/third-parties/{rec['id']}", json={"consent_given": True},
                     headers=auth(tokens["contributor2"]))
    assert r.status_code == 403

    client.post("/consent/directives", json={"permissions": {}},
                headers=auth(tokens["patient"]))
    r = client.get("/consent/directives", headers=auth(tokens["contributor2"]))
    assert r.json()["count"] == 0


def test_admin_must_pick_patient(client, tokens, users):
    r = client.get("/consent/directives", headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.get("/consent/directives",
                   params={"patient_id": users["patient"].id},
                   headers=auth(tokens["admin"]))
    assert r.status_code == 200

    r = client.post("/consent/third-parties", json={"person_name": "X"},
                    headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.post("/consent/third-parties", json={"person_name": "X"},
                    params={"patient_id": users["patient"].id},
                    headers=auth(tokens["admin"]))
    assert r.status_code == 201
