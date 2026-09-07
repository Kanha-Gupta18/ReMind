"""Real media upload + file serving (spec §5 provenance: checksum, size, path)."""

import hashlib
import os

from tests.conftest import TEST_STORAGE_DIR, auth


def _upload(client, token, file_name, content=b"fake-jpeg-bytes",
            context_tags=None, media_type="image/jpeg"):
    data = None
    if context_tags:
        data = {"context_tags": context_tags}
    return client.post(
        "/sources/upload",
        files={"file": (file_name, content, media_type)},
        data=data,
        headers=auth(token),
    )


def test_upload_persists_file_and_metadata(client, tokens):
    content = b"fake-jpeg-bytes"
    r = _upload(client, tokens["contributor"], "holiday_1985.jpg", content,
                context_tags=["Goa", "the 1980s"])
    assert r.status_code == 201
    body = r.json()
    assert body["file_type"] == "photo"
    assert body["file_size"] == len(content)
    assert body["checksum"] == hashlib.sha256(content).hexdigest()
    assert body["context_tags"] == ["Goa", "the 1980s"]
    assert body["storage_path"].startswith(TEST_STORAGE_DIR)
    assert os.path.exists(body["storage_path"])

    with open(body["storage_path"], "rb") as f:
        assert f.read() == content

    r = client.get(f"/sources/{body['id']}/file", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    assert r.content == content
    assert r.headers["content-type"].startswith("image/jpeg")


def test_upload_infers_file_type_from_extension(client, tokens):
    cases = {
        "clip.mp4": "video",
        "voice.m4a": "audio",
        "letter.pdf": "document",
        "chat_export.zip": "message_export",
        "photo.PNG": "photo",
    }
    for file_name, expected in cases.items():
        r = _upload(client, tokens["contributor"], file_name, content=b"x")
        assert r.status_code == 201, file_name
        assert r.json()["file_type"] == expected, file_name


def test_upload_rejects_unknown_extension(client, tokens):
    r = _upload(client, tokens["contributor"], "notes.xyz", content=b"x")
    assert r.status_code == 400


def test_upload_rbac(client, tokens):
    for role in ("patient", "caregiver", "clinician"):
        r = _upload(client, tokens[role], "photo.jpg", content=b"x")
        assert r.status_code == 403, role


def test_file_isolation_between_patients(client, tokens):
    r = _upload(client, tokens["contributor"], "photo.jpg", content=b"secret")
    assert r.status_code == 201
    src_id = r.json()["id"]

    r = client.get(f"/sources/{src_id}/file", headers=auth(tokens["contributor2"]))
    assert r.status_code == 403
    r = client.get(f"/sources/{src_id}/file", headers=auth(tokens["caregiver"]))
    assert r.status_code == 200


def test_file_missing_on_disk_is_404(client, tokens):
    body = {"file_name": "metadata_only.jpg", "file_type": "photo"}
    r = client.post("/sources", json=body, headers=auth(tokens["contributor"]))
    assert r.status_code == 201
    src_id = r.json()["id"]
    r = client.get(f"/sources/{src_id}/file", headers=auth(tokens["reviewer"]))
    assert r.status_code == 404
