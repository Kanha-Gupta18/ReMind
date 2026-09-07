"""Knowledge graph, people, face-match confirmation (spec §9, §18.2)."""

from app.core.database import SessionLocal
from app.models.constants import FaceMatchState
from app.models.memory import Source
from app.models.people import FaceMatch

from tests.conftest import auth


def test_graph_edge_review_flow(client, tokens):
    r = client.post("/graph/nodes", json={"node_type": "person", "name": "Ramesh"},
                    headers=auth(tokens["reviewer"]))
    assert r.status_code == 201
    n1 = r.json()["id"]
    r = client.post("/graph/nodes", json={"node_type": "place", "name": "Goa"},
                    headers=auth(tokens["reviewer"]))
    n2 = r.json()["id"]

    r = client.post("/graph/edges", json={"source_node_id": n1, "target_node_id": n2,
                                          "relation_type": "visited"},
                    headers=auth(tokens["contributor"]))
    assert r.status_code == 201 and r.json()["status"] == "SUGGESTED"
    eid = r.json()["id"]

    r = client.post(f"/graph/edges/{eid}/review", json={"status": "CONFIRMED", "disputed": False},
                    headers=auth(tokens["contributor"]))
    assert r.status_code == 403
    r = client.post(f"/graph/edges/{eid}/review", json={"status": "CONFIRMED", "disputed": False},
                    headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"

    r = client.get("/graph", headers=auth(tokens["patient"]))
    assert r.status_code == 403
    r = client.get("/graph", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and len(r.json()["nodes"]) >= 2
    r = client.get(f"/graph/edges/{eid}/trace", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    r = client.get(f"/graph/people/{n1}/relations", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200


def test_person_crud_and_face_match(client, tokens, users):
    r = client.post("/people", json={"name": "Ramesh", "relationship_to_patient": "brother",
                                     "aliases": ["Ram"]}, headers=auth(tokens["contributor"]))
    assert r.status_code == 201
    person_id = r.json()["id"]
    r = client.post("/people", json={"name": "X"}, headers=auth(tokens["patient"]))
    assert r.status_code == 403
    r = client.patch(f"/people/{person_id}", json={"identity_status": "FAMILY_CONFIRMED"},
                     headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["identity_status"] == "FAMILY_CONFIRMED"

    db = SessionLocal()
    src = Source(patient_id=users["patient"].id, uploaded_by=users["contributor"].id,
                 file_name="photo.jpg", file_type="photo")
    db.add(src)
    db.flush()
    fm = FaceMatch(patient_id=users["patient"].id, source_id=src.id,
                   face_match_state=FaceMatchState.POSSIBLE_MATCH.value,
                   confidence=0.92, model_version="test-v1")
    db.add(fm)
    db.commit()
    fm_id, src_id = fm.id, src.id
    db.close()
    try:
        r = client.post(f"/people/face-matches/{fm_id}/confirm", json={"person_id": person_id},
                        headers=auth(tokens["reviewer"]))
        assert r.status_code == 200
        r = client.get("/people/face-matches", headers=auth(tokens["patient"]))
        assert r.status_code == 200 and r.json()["count"] >= 1
    finally:
        db = SessionLocal()
        db.query(FaceMatch).filter(FaceMatch.id == fm_id).delete(synchronize_session=False)
        db.query(Source).filter(Source.id == src_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_people_admin_patient_scope(client, tokens, users):
    pid = users["patient"].id
    r = client.get("/people", headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.get(f"/people?patient_id={pid}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    r = client.get("/people/face-matches", headers=auth(tokens["admin"]))
    assert r.status_code == 403
    r = client.get(f"/people/face-matches?patient_id={pid}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    r = client.get("/people", headers=auth(tokens["contributor"]))
    assert r.status_code == 200


def test_graph_admin_patient_scope(client, tokens, users):
    r = client.post("/graph/nodes", json={"node_type": "person", "name": "Sunita"},
                    headers=auth(tokens["reviewer"]))
    assert r.status_code == 201
    pid = users["patient"].id
    r = client.get("/graph", headers=auth(tokens["patient"]))
    assert r.status_code == 403
    r = client.get(f"/graph?patient_id={pid}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    assert any(n["name"] == "Sunita" for n in r.json()["nodes"])
    r = client.get(f"/graph/nodes?patient_id={pid}&node_type=person", headers=auth(tokens["admin"]))
    assert r.status_code == 200 and r.json()["count"] >= 1
    r = client.get(f"/graph/nodes?patient_id={pid}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
