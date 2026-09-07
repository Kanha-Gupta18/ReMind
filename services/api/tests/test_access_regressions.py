"""Regression tests for the Section 2 access boundary repairs."""

import pytest
from fastapi import HTTPException

from app.api.deps import get_patient_scope
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models.base import new_id
from app.models.constants import (
    DeletionStatus,
    EdgeStatus,
    EvidenceReviewStatus,
    FaceMatchState,
    IdentityStatus,
    MemoryStatus,
    Role,
    Visibility,
)
from app.models.conversation import ConversationSession
from app.models.graph import GraphEdge, GraphNode
from app.models.memory import Evidence, MemoryCard, Source
from app.models.people import FaceMatch, Person
from app.models.user import User
from tests.conftest import auth
from tests.test_memories_rbac import _create_memory
from tests.test_sources_upload import _upload


@pytest.mark.parametrize("role", [r.value for r in Role
                                  if r not in {Role.PATIENT, Role.ADMINISTRATOR}])
def test_unlinked_role_never_receives_unrestricted_scope(role):
    with pytest.raises(HTTPException) as error:
        get_patient_scope(User(role=role, patient_id=None))
    assert error.value.status_code == 403


def test_unlinked_account_is_rejected_by_scoped_api(client):
    user_id = new_id()
    with SessionLocal() as db:
        db.add(User(
            id=user_id,
            email=f"unlinked.{user_id}@remind.dev",
            password_hash=hash_password("testpass123"),
            full_name="Unlinked caregiver",
            role=Role.CAREGIVER.value,
        ))
        db.commit()

    token = create_access_token(user_id, Role.CAREGIVER.value, None)
    try:
        response = client.get("/sources", headers=auth(token))
        assert response.status_code == 403
        assert response.json()["detail"] == "No patient relationship is configured"
    finally:
        with SessionLocal() as db:
            db.query(User).filter(User.id == user_id).delete()
            db.commit()


@pytest.mark.parametrize("state", [s.value for s in MemoryStatus if s != MemoryStatus.APPROVED])
def test_patient_cannot_read_nonapproved_memory_routes(client, tokens, state):
    mid = _create_memory(client, tokens["contributor"]).json()["id"]
    with SessionLocal() as db:
        db.get(MemoryCard, mid).status = state
        db.commit()
    headers = auth(tokens["patient"])
    assert client.get("/memories", headers=headers).json()["items"] == []
    for suffix in ("", "/evidence", "/revisions"):
        assert client.get(f"/memories/{mid}{suffix}", headers=headers).status_code in {403, 404}
    assert client.post(f"/memories/{mid}/engage", json={"action": "viewed"},
                       headers=headers).status_code == 403


def test_family_only_approved_memory_is_not_patient_visible(client, tokens):
    mid = _create_memory(
        client,
        tokens["contributor"],
        visibility="family_only",
        memory_date="1995-06-01",
        tags=["place:Delhi"],
    ).json()["id"]
    client.post(f"/memories/{mid}/submit", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{mid}/approve", headers=auth(tokens["reviewer"]))
    headers = auth(tokens["patient"])
    assert client.get(f"/memories/{mid}", headers=headers).status_code == 403
    assert client.get("/memories", headers=headers).json()["items"] == []
    assert client.get("/timeline", headers=headers).json()["items"] == []
    assert client.get("/timeline/decades", headers=headers).json()["items"] == []
    assert client.get("/timeline/places", headers=headers).json()["items"] == []


def test_patient_evidence_includes_only_accepted_active_sources(client, tokens):
    memory_id = _create_memory(client, tokens["contributor"]).json()["id"]
    client.post(f"/memories/{memory_id}/submit", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{memory_id}/approve", headers=auth(tokens["reviewer"]))
    source = _upload(client, tokens["contributor"], "evidence.jpg").json()
    with SessionLocal() as db:
        db.add_all([
            Evidence(
                memory_id=memory_id,
                source_id=source["id"],
                evidence_type="family_statement",
                claim="Accepted claim",
                review_status=EvidenceReviewStatus.ACCEPTED.value,
            ),
            Evidence(
                memory_id=memory_id,
                source_id=source["id"],
                evidence_type="family_statement",
                claim="Pending claim",
                review_status=EvidenceReviewStatus.PENDING.value,
            ),
        ])
        db.commit()

    headers = auth(tokens["patient"])
    items = client.get(f"/memories/{memory_id}/evidence", headers=headers).json()["items"]
    assert [item["claim"] for item in items] == ["Accepted claim"]

    with SessionLocal() as db:
        db.get(Source, source["id"]).deletion_status = DeletionStatus.DELETED.value
        db.commit()
    assert client.get(f"/memories/{memory_id}/evidence", headers=headers).json()["items"] == []


def test_source_registration_cannot_select_server_path(client, tokens):
    response = client.post("/sources", headers=auth(tokens["contributor"]), json={
        "file_name": "secret.txt", "file_type": "document", "storage_path": __file__,
    })
    assert response.status_code == 422


def test_legacy_external_and_other_source_paths_are_not_served(client, tokens):
    first = _upload(client, tokens["contributor"], "first.jpg").json()
    second = _upload(client, tokens["contributor"], "second.jpg").json()
    for path in (__file__, second["storage_path"]):
        with SessionLocal() as db:
            db.get(Source, first["id"]).storage_path = path
            db.commit()
        response = client.get(f"/sources/{first['id']}/file", headers=auth(tokens["reviewer"]))
        assert response.status_code == 404


def _approve_source_for_patient(source_id, patient_id):
    with SessionLocal() as db:
        memory = MemoryCard(
            patient_id=patient_id,
            title="Approved photo",
            narrative="A family day by the sea.",
            status=MemoryStatus.APPROVED.value,
            visibility=Visibility.BOTH.value,
        )
        db.add(memory)
        db.flush()
        db.add(Evidence(
            memory_id=memory.id,
            source_id=source_id,
            evidence_type="family_statement",
            claim="The family confirmed this photograph.",
            review_status=EvidenceReviewStatus.ACCEPTED.value,
        ))
        db.commit()
        return memory.id


def test_patient_source_access_follows_memory_release(client, tokens, users):
    source = _upload(client, tokens["contributor"], "family-day.jpg", b"photo-bytes").json()
    headers = auth(tokens["patient"])
    assert client.get("/sources", headers=headers).json()["count"] == 0
    assert client.get(f"/sources/{source['id']}", headers=headers).status_code == 403
    assert client.get(f"/sources/{source['id']}/file", headers=headers).status_code == 403

    memory_id = _approve_source_for_patient(source["id"], users["patient"].id)
    detail = client.get(f"/sources/{source['id']}", headers=headers)
    assert detail.status_code == 200
    assert "storage_path" not in detail.json()
    assert detail.json()["context_tags"] == []
    assert client.get(f"/sources/{source['id']}/file", headers=headers).content == b"photo-bytes"

    with SessionLocal() as db:
        memory = db.get(MemoryCard, memory_id)
        memory.visibility = Visibility.FAMILY_ONLY.value
        db.commit()
    assert client.get(f"/sources/{source['id']}", headers=headers).status_code == 403

    with SessionLocal() as db:
        memory = db.get(MemoryCard, memory_id)
        memory.visibility = Visibility.BOTH.value
        memory.status = MemoryStatus.DISPUTED.value
        db.commit()
    assert client.get(f"/sources/{source['id']}/file", headers=headers).status_code == 403


def test_patient_people_and_relations_require_confirmation(client, tokens, users):
    with SessionLocal() as db:
        hidden = Person(
            patient_id=users["patient"].id,
            name="Unconfirmed Person",
            identity_status=IdentityStatus.LIKELY_MATCH.value,
            notes="Private reviewer note",
        )
        visible = Person(
            patient_id=users["patient"].id,
            name="Confirmed Person",
            relationship_to_patient="friend",
            identity_status=IdentityStatus.FAMILY_CONFIRMED.value,
            notes="Private reviewer note",
        )
        other = Person(
            patient_id=users["patient"].id,
            name="Confirmed Relative",
            identity_status=IdentityStatus.FAMILY_CONFIRMED.value,
        )
        db.add_all([hidden, visible, other])
        db.flush()
        nodes = [GraphNode(patient_id=users["patient"].id, node_type="person", name=p.name)
                 for p in (visible, hidden, other)]
        place = GraphNode(patient_id=users["patient"].id, node_type="place", name="Goa")
        db.add_all(nodes + [place])
        db.flush()
        db.add_all([
            GraphEdge(patient_id=users["patient"].id, source_node_id=nodes[0].id,
                      target_node_id=place.id, relation_type="visited",
                      status=EdgeStatus.SUGGESTED.value),
            GraphEdge(patient_id=users["patient"].id, source_node_id=nodes[0].id,
                      target_node_id=nodes[1].id, relation_type="knows",
                      status=EdgeStatus.CONFIRMED.value),
            GraphEdge(patient_id=users["patient"].id, source_node_id=nodes[0].id,
                      target_node_id=nodes[2].id, relation_type="sibling_of",
                      status=EdgeStatus.CONFIRMED.value),
            GraphEdge(patient_id=users["patient"].id, source_node_id=nodes[0].id,
                      target_node_id=place.id, relation_type="lived_in",
                      status=EdgeStatus.CONFIRMED.value, disputed=True),
        ])
        db.commit()
        visible_id, hidden_id = visible.id, hidden.id

    headers = auth(tokens["patient"])
    people = client.get("/people", headers=headers).json()["items"]
    assert [p["name"] for p in people] == ["Confirmed Person", "Confirmed Relative"]
    assert all("notes" not in p for p in people)
    assert client.get(f"/people/{hidden_id}/relations", headers=headers).status_code == 404
    relations = client.get(f"/people/{visible_id}/relations", headers=headers).json()["items"]
    assert [(r["other_name"], r["status"]) for r in relations] == [
        ("Confirmed Relative", "CONFIRMED")
    ]


def test_patient_face_matches_require_visible_source_and_hide_review_metadata(
    client, tokens, users
):
    source = _upload(client, tokens["contributor"], "portrait.jpg").json()
    with SessionLocal() as db:
        person = Person(
            patient_id=users["patient"].id,
            name="Asha",
            identity_status=IdentityStatus.FAMILY_CONFIRMED.value,
        )
        db.add(person)
        db.flush()
        db.add_all([
            FaceMatch(
                patient_id=users["patient"].id,
                source_id=source["id"],
                person_id=person.id,
                face_match_state=FaceMatchState.FAMILY_CONFIRMED.value,
                confidence=0.99,
                model_version="private-model-version",
            ),
            FaceMatch(
                patient_id=users["patient"].id,
                source_id=source["id"],
                person_id=person.id,
                face_match_state=FaceMatchState.POSSIBLE_MATCH.value,
                confidence=0.45,
                model_version="private-model-version",
            ),
        ])
        db.commit()
    headers = auth(tokens["patient"])
    assert client.get("/people/face-matches", headers=headers).json()["count"] == 0
    _approve_source_for_patient(source["id"], users["patient"].id)
    items = client.get("/people/face-matches", headers=headers).json()["items"]
    assert len(items) == 1
    assert set(items[0]) == {"id", "source_id", "person_id", "face_match_state"}


def test_conversation_hides_unconfirmed_people_and_raw_photo_analysis(client, tokens, users):
    source = _upload(client, tokens["contributor"], "portrait.jpg").json()
    _approve_source_for_patient(source["id"], users["patient"].id)
    with SessionLocal() as db:
        person = Person(
            patient_id=users["patient"].id,
            name="Asha",
            identity_status=IdentityStatus.LIKELY_MATCH.value,
        )
        db.add(person)
        db.flush()
        db.add(FaceMatch(
            patient_id=users["patient"].id,
            source_id=source["id"],
            person_id=person.id,
            face_match_state=FaceMatchState.FAMILY_CONFIRMED.value,
            confidence=0.99,
            model_version="private-model-version",
        ))
        stored = db.get(Source, source["id"])
        stored.pipeline_results = {"vision": {"scene": "Private model description"}}
        db.commit()
        person_id = person.id

    session = client.post("/conversations/sessions", json={"session_type": "chat"},
                          headers=auth(tokens["patient"])).json()["id"]
    hidden_person = client.post(
        f"/conversations/sessions/{session}/messages",
        json={"content": "Who is Asha?"},
        headers=auth(tokens["patient"]),
    ).json()
    assert "Asha" not in hidden_person["reply"]

    hidden_photo = client.post(
        f"/conversations/sessions/{session}/messages",
        json={"content": "photo portrait.jpg"},
        headers=auth(tokens["patient"]),
    ).json()
    assert "Asha" not in hidden_photo["reply"]
    assert "Private model description" not in hidden_photo["reply"]

    with SessionLocal() as db:
        db.get(Person, person_id).identity_status = IdentityStatus.FAMILY_CONFIRMED.value
        db.commit()
    confirmed_photo = client.post(
        f"/conversations/sessions/{session}/messages",
        json={"content": "photo portrait.jpg"},
        headers=auth(tokens["patient"]),
    ).json()
    assert "Asha" in confirmed_photo["reply"]
    assert "Private model description" not in confirmed_photo["reply"]


def test_conversation_revalidates_history_and_ended_sessions(client, tokens, users):
    memory_id = _create_memory(client, tokens["contributor"],
                               title="Hill station holiday").json()["id"]
    client.post(f"/memories/{memory_id}/submit", headers=auth(tokens["reviewer"]))
    client.post(f"/memories/{memory_id}/approve", headers=auth(tokens["reviewer"]))
    session = client.post("/conversations/sessions", json={"session_type": "chat"},
                          headers=auth(tokens["patient"])).json()["id"]
    response = client.post(
        f"/conversations/sessions/{session}/messages",
        json={"content": "Tell me about the hill station holiday"},
        headers=auth(tokens["patient"]),
    )
    assert response.status_code == 200
    assert response.json()["tool_calls"] == [{"tool": "search_memories"}]
    history = client.get(f"/conversations/sessions/{session}/messages",
                         headers=auth(tokens["patient"])).json()["items"]
    assert all(item["role"] != "tool" and item["tool_calls"] is None for item in history)
    assert any("Hill station holiday" in item["content"] for item in history)

    with SessionLocal() as db:
        db.get(MemoryCard, memory_id).status = MemoryStatus.DISPUTED.value
        db.commit()
    history = client.get(f"/conversations/sessions/{session}/messages",
                         headers=auth(tokens["patient"])).json()["items"]
    assert any("no longer available" in item["content"] for item in history)
    assert all("Hill station holiday." not in item["content"] for item in history
               if item["role"] == "system")

    client.post(f"/conversations/sessions/{session}/stop", headers=auth(tokens["patient"]))
    response = client.post(
        f"/conversations/sessions/{session}/messages",
        json={"content": "Tell me again"},
        headers=auth(tokens["patient"]),
    )
    assert response.status_code == 409
