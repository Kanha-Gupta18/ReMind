"""Source upload + AI pipeline routes (spec §5, §18)."""

from tests.conftest import auth


def test_upload_process_reconstruct(client, tokens):
    body = {"file_name": "holiday_1985.jpg", "file_type": "photo",
            "context_tags": ["Goa", "the 1980s"]}
    r = client.post("/sources", json=body, headers=auth(tokens["contributor"]))
    assert r.status_code == 201
    src_id = r.json()["id"]

    r = client.post(f"/sources/{src_id}/process", headers=auth(tokens["contributor"]))
    assert r.status_code == 200

    r = client.post(f"/sources/{src_id}/reconstruct", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200 and r.json()["count"] >= 1

    r = client.get("/sources", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200 and r.json()["count"] >= 1
    r = client.get("/sources", headers=auth(tokens["admin"]))
    assert r.status_code == 200


def test_upload_rbac(client, tokens):
    body = {"file_name": "x.jpg", "file_type": "photo"}
    r = client.post("/sources", json=body, headers=auth(tokens["patient"]))
    assert r.status_code == 403
    r = client.post("/sources", json=body, headers=auth(tokens["caregiver"]))
    assert r.status_code == 403


def test_soft_delete_source(client, tokens):
    r = client.post("/sources", json={"file_name": "a.jpg", "file_type": "photo"},
                    headers=auth(tokens["contributor"]))
    src_id = r.json()["id"]
    r = client.delete(f"/sources/{src_id}", headers=auth(tokens["contributor"]))
    assert r.status_code == 200
    r = client.get(f"/sources/{src_id}", headers=auth(tokens["reviewer"]))
    assert r.status_code == 404
