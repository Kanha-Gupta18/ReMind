"""Conversation guardrails, sessions, caregiver stop, safety events (§16, §21)."""

from tests.conftest import auth


def _start_session(client, tokens):
    r = client.post("/conversations/sessions", json={"session_type": "chat"},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 201
    return r.json()["id"]


def test_session_rbac_and_history(client, tokens):
    r = client.post("/conversations/sessions", json={}, headers=auth(tokens["reviewer"]))
    assert r.status_code == 403
    sess = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess}/messages",
                    json={"content": "Tell me about our holiday in Goa"},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 200 and "reply" in r.json()
    r = client.get(f"/conversations/sessions/{sess}/messages", headers=auth(tokens["patient"]))
    assert r.status_code == 200 and r.json()["count"] >= 2
    r = client.get(f"/conversations/sessions/{sess}/messages", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200


def test_list_sessions(client, tokens):
    _start_session(client, tokens)
    _start_session(client, tokens)
    r = client.get("/conversations/sessions", headers=auth(tokens["patient"]))
    assert r.status_code == 200 and r.json()["count"] == 2
    assert all("started_at" in s for s in r.json()["items"])
    r = client.get("/conversations/sessions", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["count"] == 2
    r = client.get("/conversations/sessions", headers=auth(tokens["contributor"]))
    assert r.status_code == 403


def test_medical_question_declined(client, tokens):
    sess = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess}/messages",
                    json={"content": "Do I have diabetes?"}, headers=auth(tokens["patient"]))
    assert r.status_code == 200
    assert "question for your doctor" in r.json()["reply"]


def test_restricted_topic_blocked(client, tokens):
    sess = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess}/messages",
                    json={"content": "Tell me about grandpa's funeral"},
                    headers=auth(tokens["patient"]))
    assert r.status_code == 200
    assert r.json()["safety_flag"] is True


def test_caregiver_stop_and_acknowledge(client, tokens):
    sess = _start_session(client, tokens)
    r = client.post(f"/conversations/sessions/{sess}/stop", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and "safety_event" in r.json()

    r = client.get("/safety/events", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and r.json()["count"] >= 1
    ev = next(e for e in r.json()["items"] if e["event_type"] == "caregiver_stop")

    r = client.post(f"/safety/events/{ev['id']}/acknowledge", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200
    r = client.get("/safety/events?unacknowledged_only=true", headers=auth(tokens["caregiver"]))
    assert all(e["event_type"] != "caregiver_stop" for e in r.json()["items"])


def test_safety_level(client, tokens, users):
    r = client.get("/safety/level", headers=auth(tokens["patient"]))
    assert r.status_code == 200 and r.json()["safety_level"] == "NORMAL"
    r = client.get("/safety/level", headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.get(f"/safety/level?patient_id={users['patient'].id}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    r = client.get("/safety/events", headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.get(f"/safety/events?patient_id={users['patient'].id}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
