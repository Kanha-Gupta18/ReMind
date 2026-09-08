"""Safety events and caregiver stop RBAC (§16, §18.5)."""

from tests.conftest import auth


def _start_session(client, tokens):
    r = client.post("/conversations/sessions", json={"session_type": "chat"},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 201
    return r.json()["id"]


def test_restricted_query_records_event(client, tokens):
    sess = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess}/messages",
                    json={"content": "Tell me about grandpa's funeral"},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 200 and r.json()["safety_flag"] is True

    r = client.get("/safety/events?unacknowledged_only=true", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200
    assert any(e["event_type"] == "restricted_query" for e in r.json()["items"])


def test_acknowledge_requires_support_role(client, tokens):
    sess = _start_session(client, tokens)
    ev = client.post(f"/conversations/sessions/{sess}/stop",
                     headers=auth(tokens["caregiver"])).json()["safety_event"]
    r = client.post(f"/safety/events/{ev}/acknowledge", headers=auth(tokens["patient"]))
    assert r.status_code == 403
    r = client.post(f"/safety/events/{ev}/acknowledge", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200


def test_stop_session_rbac(client, tokens):
    sess = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess}/stop", headers=auth(tokens["reviewer"]))
    assert r.status_code == 403

    r = client.post(f"/conversations/sessions/{sess}/stop", headers=auth(tokens["patient"]))
    assert r.status_code == 200 and r.json()["status"] == "ended"
    assert "safety_event" not in r.json()

    sess2 = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess2}/stop", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and "safety_event" in r.json()


def test_admin_cannot_stop_patient_session(client, tokens):
    sess = _start_session(client, tokens)
    r = client.post(f"/safety/sessions/{sess}/stop", headers=auth(tokens["admin"]))
    assert r.status_code == 403


def test_list_events_requires_support_role(client, tokens):
    for role in ("patient", "contributor", "reviewer"):
        r = client.get("/safety/events", headers=auth(tokens[role]))
        assert r.status_code == 403, role
    assert client.get("/safety/events", headers=auth(tokens["caregiver"])).status_code == 200


def test_list_events_admin_requires_scope(client, tokens):
    assert client.get("/safety/events", headers=auth(tokens["admin"])).status_code == 403


def test_cannot_stop_another_patients_session(client, tokens):
    r = client.post("/conversations/sessions", json={"session_type": "chat"},
                    headers=auth(tokens["patient2"]))
    other = r.json()["id"]
    r = client.post(f"/safety/sessions/{other}/stop", headers=auth(tokens["caregiver"]))
    assert r.status_code == 403
