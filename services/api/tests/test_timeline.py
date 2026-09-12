"""Timeline routes: approved-only stream, decades, places, engagement (spec §16)."""

from tests.conftest import auth


def _approved(client, tokens, **overrides):
    body = {"title": "Summer 1985 in Goa", "narrative": "Beach holiday.",
            "memory_date": "1985-07-14", "tags": ["goa", "summer"]}
    body.update(overrides)
    mem_id = client.post("/memories", json=body, headers=auth(tokens["patient"])).json()["id"]
    client.post(f"/memories/{mem_id}/submit", headers=auth(tokens["reviewer"]))
    r = client.post(f"/memories/{mem_id}/approve", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    return mem_id


def test_timeline_shows_only_approved(client, tokens):
    approved = _approved(client, tokens, title="Approved trip")
    draft_id = client.post("/memories", json={"title": "Still a draft", "narrative": "x"},
                           headers=auth(tokens["patient"])).json()["id"]
    r = client.get("/timeline", headers=auth(tokens["patient"]))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == approved for i in items)
    assert all(i["id"] != draft_id for i in items)


def test_timeline_newest_first_and_limit(client, tokens):
    older = _approved(client, tokens, title="Old memory", memory_date="1980-01-01")
    newer = _approved(client, tokens, title="New memory", memory_date="2000-01-01")
    r = client.get("/timeline", headers=auth(tokens["patient"]))
    ids = [i["id"] for i in r.json()["items"]]
    assert ids.index(newer) < ids.index(older)
    r = client.get("/timeline?limit=1", headers=auth(tokens["patient"]))
    assert r.json()["count"] == 1 and r.json()["items"][0]["id"] == newer


def test_timeline_decades_grouping(client, tokens):
    _approved(client, tokens, title="Eighty trip", memory_date="1985-07-14")
    _approved(client, tokens, title="Ninety trip", memory_date="1992-03-01")
    r = client.get("/timeline/decades", headers=auth(tokens["patient"]))
    assert r.status_code == 200
    decades = {g["decade"]: g["count"] for g in r.json()["items"]}
    assert decades == {1980: 1, 1990: 1}


def test_timeline_places_grouping(client, tokens):
    place = client.post(
        "/knowledge/places", json={"name": "Goa"},
        headers=auth(tokens["reviewer"]),
    ).json()
    _approved(client, tokens, title="Goa trip", place_ids=[place["id"]])
    _approved(client, tokens, title="No place", tags=["holiday"])
    r = client.get("/timeline/places", headers=auth(tokens["patient"]))
    assert r.status_code == 200
    places = {g["place"]: g["count"] for g in r.json()["items"]}
    assert places["Goa"] == 1 and "Unknown" in places


def test_timeline_admin_requires_scope(client, tokens):
    for path in ("/timeline", "/timeline/decades", "/timeline/places", "/timeline/engagement"):
        r = client.get(path, headers=auth(tokens["admin"]))
        assert r.status_code == 403, path


def test_timeline_engagement_stats(client, tokens):
    mem_id = _approved(client, tokens)
    for _ in range(3):
        r = client.post(f"/memories/{mem_id}/engage",
                        json={"action": "viewed", "duration_ms": 1000},
                        headers=auth(tokens["patient"]))
        assert r.status_code == 200
    r = client.get("/timeline/engagement", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200
    body = r.json()
    assert body["total_engagements"] == 3
    assert body["by_action"].get("viewed") == 3
    top = next(t for t in body["top_memories"] if t["memory_card_id"] == mem_id)
    assert top["views"] == 3

    r = client.get("/timeline/engagement", headers=auth(tokens["patient"]))
    assert r.status_code == 403


def test_timeline_hides_sensitive_at_hidden(client, tokens, users):
    from app.core.database import SessionLocal
    from app.models.constants import SafetyLevel
    from app.models.user import PatientProfile

    mem_id = _approved(client, tokens, title="Hard memory",
                       sensitivity_flags=["DEATH"])
    assert any(i["id"] == mem_id for i in
               client.get("/timeline", headers=auth(tokens["patient"])).json()["items"])

    db = SessionLocal()
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == users["patient"].id).first()
    profile.safety_level = SafetyLevel.HIDDEN.value
    db.commit()
    db.close()
    try:
        r = client.get("/timeline", headers=auth(tokens["patient"]))
        assert all(i["id"] != mem_id for i in r.json()["items"])
        r = client.get("/timeline", headers=auth(tokens["caregiver"]))
        assert any(i["id"] == mem_id for i in r.json()["items"])
    finally:
        db = SessionLocal()
        profile = db.query(PatientProfile).filter(PatientProfile.user_id == users["patient"].id).first()
        profile.safety_level = SafetyLevel.NORMAL.value
        db.commit()
        db.close()
