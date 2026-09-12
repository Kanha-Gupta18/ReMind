"""Canonical memory revisions, review records, and structured context."""

from app.core.database import SessionLocal
from app.models.constants import IdentityStatus
from app.models.knowledge import MemoryEventLink, MemoryPersonLink, MemoryPlaceLink
from app.models.memory import Evidence, MemoryCard, MemoryReviewRecord, MemoryRevision
from app.services import evidence_service
from tests.conftest import auth


def _approved(client, tokens, **overrides):
    body = {"title": "Original memory", "narrative": "The published account."}
    body.update(overrides)
    created = client.post("/memories", json=body, headers=auth(tokens["reviewer"]))
    assert created.status_code == 201
    memory_id = created.json()["id"]
    assert client.post(
        f"/memories/{memory_id}/submit", headers=auth(tokens["reviewer"])
    ).status_code == 200
    assert client.post(
        f"/memories/{memory_id}/approve", headers=auth(tokens["reviewer"])
    ).status_code == 200
    return memory_id


def test_candidate_edit_keeps_published_content_until_approval(client, tokens):
    memory_id = _approved(client, tokens)
    original = client.get(
        f"/memories/{memory_id}", headers=auth(tokens["patient"])
    ).json()

    edited = client.patch(
        f"/memories/{memory_id}",
        json={
            "title": "Corrected memory",
            "narrative": "A candidate account.",
            "memory_date": "1999-07-01",
            "date_accuracy": "month",
            "note": "Family corrected the date",
        },
        headers=auth(tokens["reviewer"]),
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "DRAFT"
    assert edited.json()["title"] == "Corrected memory"
    assert edited.json()["has_pending_revision"] is True

    patient_during_edit = client.get(
        f"/memories/{memory_id}", headers=auth(tokens["patient"])
    ).json()
    assert patient_during_edit["title"] == original["title"]
    assert patient_during_edit["narrative"] == original["narrative"]
    assert patient_during_edit["status"] == "APPROVED"

    submitted = client.post(
        f"/memories/{memory_id}/submit", headers=auth(tokens["reviewer"])
    )
    assert submitted.status_code == 200
    assert client.get(
        f"/memories/{memory_id}", headers=auth(tokens["patient"])
    ).json()["title"] == "Original memory"

    approved = client.post(
        f"/memories/{memory_id}/approve", headers=auth(tokens["reviewer"])
    )
    assert approved.status_code == 200
    patient_after_approval = client.get(
        f"/memories/{memory_id}", headers=auth(tokens["patient"])
    ).json()
    assert patient_after_approval["title"] == "Corrected memory"
    assert patient_after_approval["memory_date"] == "1999-07-01"

    history = client.get(
        f"/memories/{memory_id}/revisions", headers=auth(tokens["reviewer"])
    ).json()["items"]
    assert [item["status"] for item in history] == ["superseded", "approved"]
    assert history[0]["content"]["title"] == "Original memory"
    assert history[1]["content"]["title"] == "Corrected memory"
    assert history[1]["change_note"] == "Family corrected the date"
    assert history[1]["is_approved"] is True
    assert history[1]["authored_by_name"] == "family_reviewer"
    assert history[1]["structured_context"] == {
        "people": [], "places": [], "events": [],
    }
    assert [item["decision"] for item in history[1]["reviews"]] == [
        "submitted", "approved"
    ]
    assert all(
        item["actor_name"] == "family_reviewer"
        for item in history[1]["reviews"]
    )


def test_rejected_candidate_does_not_replace_approved_revision(client, tokens):
    memory_id = _approved(client, tokens)
    client.patch(
        f"/memories/{memory_id}", json={"title": "Unverified replacement"},
        headers=auth(tokens["reviewer"]),
    )
    client.post(f"/memories/{memory_id}/submit", headers=auth(tokens["reviewer"]))
    rejected = client.post(
        f"/memories/{memory_id}/reject",
        json={"reason": "The date could not be confirmed"},
        headers=auth(tokens["reviewer"]),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "APPROVED"
    assert rejected.json()["title"] == "Original memory"
    assert rejected.json()["has_pending_revision"] is False
    assert client.get(
        f"/memories/{memory_id}", headers=auth(tokens["patient"])
    ).json()["title"] == "Original memory"

    history = client.get(
        f"/memories/{memory_id}/revisions", headers=auth(tokens["reviewer"])
    ).json()["items"]
    assert [item["status"] for item in history] == ["approved", "rejected"]
    rejected_review = history[1]["reviews"][-1]
    assert rejected_review["decision"] == "rejected"
    assert rejected_review["reason"] == "The date could not be confirmed"


def test_submitted_candidate_cannot_be_replaced_or_approved_twice(client, tokens):
    memory_id = _approved(client, tokens)
    client.patch(
        f"/memories/{memory_id}", json={"title": "Pending candidate"},
        headers=auth(tokens["reviewer"]),
    )
    client.post(f"/memories/{memory_id}/submit", headers=auth(tokens["reviewer"]))
    conflict = client.patch(
        f"/memories/{memory_id}", json={"title": "Second candidate"},
        headers=auth(tokens["reviewer"]),
    )
    assert conflict.status_code == 409
    assert "must be reviewed" in conflict.json()["detail"]
    assert client.post(
        f"/memories/{memory_id}/approve", headers=auth(tokens["reviewer"])
    ).status_code == 200
    assert client.post(
        f"/memories/{memory_id}/approve", headers=auth(tokens["reviewer"])
    ).status_code == 409


def test_structured_people_places_events_and_dates_publish_together(client, tokens):
    person = client.post(
        "/people", json={"name": "Asha", "relationship_to_patient": "sister"},
        headers=auth(tokens["reviewer"]),
    ).json()
    client.patch(
        f"/people/{person['id']}", json={"identity_status": IdentityStatus.FAMILY_CONFIRMED.value},
        headers=auth(tokens["reviewer"]),
    )
    place = client.post(
        "/knowledge/places", json={"name": "Goa", "aliases": ["Panaji"]},
        headers=auth(tokens["reviewer"]),
    ).json()
    event = client.post(
        "/knowledge/events",
        json={
            "name": "Family holiday", "start_date": "1985-07-01",
            "end_date": "1985-07-14", "date_accuracy": "month",
        },
        headers=auth(tokens["reviewer"]),
    ).json()

    memory_id = _approved(
        client, tokens, title="Goa holiday", memory_date="1985-07-14",
        date_accuracy="day", people_ids=[person["id"]], place_ids=[place["id"]],
        event_ids=[event["id"]],
    )
    patient = client.get(
        f"/memories/{memory_id}", headers=auth(tokens["patient"])
    ).json()
    assert patient["structured_context"] == {
        "people": [{"id": person["id"], "name": "Asha"}],
        "places": [{"id": place["id"], "name": "Goa"}],
        "events": [{"id": event["id"], "name": "Family holiday"}],
    }
    assert patient["memory_date"] == "1985-07-14"
    assert patient["date_accuracy"] == "day"
    places = client.get("/timeline/places", headers=auth(tokens["patient"])).json()["items"]
    assert [(item["place"], item["count"]) for item in places] == [("Goa", 1)]

    with SessionLocal() as db:
        assert db.query(MemoryPersonLink).filter_by(memory_id=memory_id).count() == 1
        assert db.query(MemoryPlaceLink).filter_by(memory_id=memory_id).count() == 1
        assert db.query(MemoryEventLink).filter_by(memory_id=memory_id).count() == 1


def test_structured_context_rejects_cross_patient_ids(client, tokens):
    other_place = client.post(
        "/knowledge/places", json={"name": "Private place"},
        headers=auth(tokens["contributor2"]),
    ).json()
    response = client.post(
        "/memories", json={"title": "Invalid link", "place_ids": [other_place["id"]]},
        headers=auth(tokens["reviewer"]),
    )
    assert response.status_code == 400
    assert "Unknown places" in response.json()["detail"]


def test_evidence_is_revision_scoped_and_review_attributed(client, tokens):
    memory_id = _approved(client, tokens)
    with SessionLocal() as db:
        memory = db.get(MemoryCard, memory_id)
        evidence = evidence_service.add_evidence(
            db, memory_id, None, "family_statement", "Asha confirmed the account."
        )
        evidence_id = evidence.id
        assert evidence.revision_id == memory.approved_revision_id
        db.commit()

    reviewed = client.post(
        f"/memories/{memory_id}/evidence/{evidence_id}/review",
        json={"status": "ACCEPTED"}, headers=auth(tokens["reviewer"]),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewed_by"] is not None
    assert reviewed.json()["reviewed_by_name"] == "family_reviewer"
    assert reviewed.json()["reviewed_at"] is not None

    item = client.get(
        f"/memories/{memory_id}/evidence", headers=auth(tokens["reviewer"])
    ).json()["items"][0]
    assert item["revision_id"] is not None
    assert item["review_status"] == "ACCEPTED"
    assert item["reviewed_by"] == reviewed.json()["reviewed_by"]
    assert item["reviewed_by_name"] == "family_reviewer"


def test_review_records_are_append_only(client, tokens):
    memory_id = _approved(client, tokens)
    with SessionLocal() as db:
        memory = db.get(MemoryCard, memory_id)
        revision_count = db.query(MemoryRevision).filter_by(memory_id=memory_id).count()
        records = db.query(MemoryReviewRecord).filter_by(memory_id=memory_id).all()
        assert revision_count == 1
        assert [record.decision for record in records] == ["submitted", "approved"]
        assert all(record.revision_id == memory.approved_revision_id for record in records)
