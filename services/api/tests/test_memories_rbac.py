"""Memory lifecycle, RBAC, safety gate, revisions (spec §7, §16, §39, §23)."""

from tests.conftest import auth


def _create_memory(client, token, **overrides):
    body = {"title": "Summer 1985 in Goa", "narrative": "Beach holiday with the family.",
            "memory_date": "1985-07-14", "tags": ["goa", "summer"]}
    body.update(overrides)
    return client.post("/memories", json=body, headers=auth(token))


def test_memory_lifecycle_and_rbac(client, tokens):
    r = _create_memory(client, tokens["patient"])
    assert r.status_code == 201
    mem_id = r.json()["id"]
    assert r.json()["status"] == "DRAFT"

    for role in ("patient", "contributor"):
        r = client.post(f"/memories/{mem_id}/submit", headers=auth(tokens[role]))
        assert r.status_code == 403, role

    r = client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "AWAITING_REVIEW"

    r = client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["contributor"]))
    assert r.status_code == 403
    r = client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"

    r = client.get("/memories", headers=auth(tokens["patient"]))
    assert any(i["id"] == mem_id for i in r.json()["items"])


def test_admin_without_scope(client, tokens):
    r = client.get("/memories", headers=auth(tokens["admin"]))
    assert r.status_code == 200 and r.json()["count"] == 0
    r = client.get("/timeline", headers=auth(tokens["admin"]))
    assert r.status_code == 403


def test_timeline_grouping(client, tokens):
    mem_id = _create_memory(client, tokens["patient"]).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["reviewer"]))
    assert client.get("/timeline", headers=auth(tokens["patient"])).status_code == 200
    assert client.get("/timeline/decades", headers=auth(tokens["patient"])).status_code == 200
    assert client.get("/timeline/places", headers=auth(tokens["patient"])).status_code == 200
    assert client.get("/timeline/engagement", headers=auth(tokens["caregiver"])).status_code == 200


def test_sensitive_memory_safety_gate(client, tokens, users):
    r = _create_memory(client, tokens["contributor"],
                       title="Grandfather's passing", sensitivity_flags=["DEATH"])
    assert r.status_code == 201
    s_id = r.json()["id"]
    client.post(f"/memories/{s_id}/submit", headers=auth(tokens["reviewer"]))
    r = client.post(f"/memories/{s_id}/approve", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200

    # NORMAL safety level: sensitive content is allowed (display "full").
    r = client.get(f"/memories/{s_id}", headers=auth(tokens["patient"]))
    assert r.status_code == 200

    # HIDDEN level: patient blocked; support roles still see it.
    from app.core.database import SessionLocal
    from app.models.constants import SafetyLevel
    from app.models.user import PatientProfile
    db = SessionLocal()
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == users["patient"].id).first()
    profile.safety_level = SafetyLevel.HIDDEN.value
    db.commit()
    db.close()
    try:
        r = client.get(f"/memories/{s_id}", headers=auth(tokens["patient"]))
        assert r.status_code == 403
        r = client.get(f"/memories/{s_id}", headers=auth(tokens["reviewer"]))
        assert r.status_code == 200
    finally:
        db = SessionLocal()
        profile = db.query(PatientProfile).filter(PatientProfile.user_id == users["patient"].id).first()
        profile.safety_level = SafetyLevel.NORMAL.value
        db.commit()
        db.close()


def test_edit_revisions_restrict_dispute_archive(client, tokens):
    mem_id = _create_memory(client, tokens["patient"]).json()["id"]

    r = client.patch(f"/memories/{mem_id}", json={"title": "edited", "note": "clarified"},
                     headers=auth(tokens["patient"]))
    assert r.status_code == 403
    r = client.patch(f"/memories/{mem_id}", json={"title": "Summer 1985 (edited)"},
                     headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    r = client.get(f"/memories/{mem_id}/revisions", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and len(r.json()["items"]) >= 2

    r = client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"

    r = client.post(f"/memories/{mem_id}/restrict", json={"reason": "upsetting"},
                    headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and r.json()["status"] == "RESTRICTED"
    r = client.post(f"/memories/{mem_id}/restrict", json={}, headers=auth(tokens["reviewer"]))
    assert r.status_code == 403

    # dispute + archive run on a separate APPROVED memory
    mem2 = _create_memory(client, tokens["contributor"], title="Ski trip 1990").json()["id"]
    client.post(f"/memories/{mem2}/submit", headers=auth(tokens["reviewer"]))
    r = client.post(f"/memories/{mem2}/approve", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    r = client.post(f"/memories/{mem2}/dispute", json={"reason": "wrong date"},
                    headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "DISPUTED"

    r = client.get(f"/memories/{mem2}/evidence", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200
    r = client.post(f"/memories/{mem2}/archive", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "ARCHIVED"


def test_cross_tenant_isolation(client, tokens):
    mem_id = _create_memory(client, tokens["patient"]).json()["id"]
    src = client.post("/sources", json={"file_name": "a.jpg", "file_type": "photo"},
                      headers=auth(tokens["contributor"])).json()["id"]

    for path in (f"/memories/{mem_id}/submit", f"/memories/{mem_id}", f"/sources/{src}"):
        method = client.post if path.endswith("/submit") else client.get
        r = method(path, headers=auth(tokens["contributor2"]))
        assert r.status_code == 403, path

    r = client.get("/memories", headers=auth(tokens["contributor2"]))
    assert all(i["patient_id"] != tokens["patient"] for i in r.json()["items"])


def test_engage(client, tokens):
    mem_id = _create_memory(client, tokens["patient"]).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["reviewer"]))
    r = client.post(f"/memories/{mem_id}/engage", json={"action": "viewed", "duration_ms": 5000},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 200
