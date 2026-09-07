"""Notification inbox: workflows that raise them, read/unread flow (§18.5)."""

from tests.conftest import auth


def test_review_needed_notification(client, tokens):
    mem_id = client.post("/memories",
                         json={"title": "Holiday 1985", "narrative": "x"},
                         headers=auth(tokens["patient"])).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))

    r = client.get("/notifications", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    types = [n["type"] for n in r.json()["items"]]
    assert "review_needed" in types

    r = client.get("/notifications", headers=auth(tokens["contributor"]))
    assert all(n["type"] != "review_needed" for n in r.json()["items"])


def test_upload_complete_notification(client, tokens):
    src = client.post("/sources", json={"file_name": "a.jpg", "file_type": "photo"},
                      headers=auth(tokens["contributor"])).json()["id"]
    client.post(f"/sources/{src}/process", headers=auth(tokens["contributor"]))
    r = client.get("/notifications", headers=auth(tokens["contributor"]))
    assert any(n["type"] == "upload_complete" for n in r.json()["items"])


def test_dispute_notifies_reviewers(client, tokens):
    mem_id = client.post("/memories",
                         json={"title": "Ski trip", "narrative": "x"},
                         headers=auth(tokens["patient"])).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{mem_id}/dispute", json={"reason": "wrong"},
                headers=auth(tokens["reviewer"]))
    r = client.get("/notifications", headers=auth(tokens["reviewer"]))
    assert any(n["type"] == "dispute_flagged" for n in r.json()["items"])


def test_mark_read_and_unread_filter(client, tokens):
    mem_id = client.post("/memories",
                         json={"title": "Holiday 1985", "narrative": "x"},
                         headers=auth(tokens["patient"])).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))

    r = client.get("/notifications?unread=true", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["count"] >= 1
    n_id = r.json()["items"][0]["id"]

    assert client.post(f"/notifications/{n_id}/read",
                       headers=auth(tokens["reviewer"])).status_code == 200
    r = client.get("/notifications?unread=true", headers=auth(tokens["reviewer"]))
    assert all(n["id"] != n_id for n in r.json()["items"])
    r = client.get("/notifications", headers=auth(tokens["reviewer"]))
    assert next(n for n in r.json()["items"] if n["id"] == n_id)["read"] is True


def test_mark_all_read(client, tokens):
    for title in ("One", "Two"):
        mem_id = client.post("/memories", json={"title": title, "narrative": "x"},
                             headers=auth(tokens["patient"])).json()["id"]
        client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    r = client.post("/notifications/read-all", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["updated"] >= 1
    r = client.get("/notifications?unread=true", headers=auth(tokens["reviewer"]))
    assert r.json()["count"] == 0


def test_cannot_mark_others_notification(client, tokens):
    mem_id = client.post("/memories",
                         json={"title": "Holiday 1985", "narrative": "x"},
                         headers=auth(tokens["patient"])).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    n_id = client.get("/notifications", headers=auth(tokens["reviewer"])).json()["items"][0]["id"]

    r = client.post(f"/notifications/{n_id}/read", headers=auth(tokens["contributor2"]))
    assert r.status_code == 404
