"""Private storage protocol and authorization, using no external credentials."""

from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.memory import Source
from app.services import storage_service
from tests.conftest import auth
from tests.test_sources_upload import _upload


@pytest.fixture
def remote_store(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://test.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", SecretStr("server-only-test-key"))
    monkeypatch.setattr(settings, "supabase_storage_bucket", "remind-sources")
    state = {"public": False, "objects": {}, "requests": [], "fail": False}
    def handle(request):
        state["requests"].append((request.method, request.url.path))
        assert request.headers["authorization"] == "Bearer server-only-test-key"
        assert request.url.host == "test.supabase.co"
        if state["fail"]:
            return httpx.Response(503, text="server-only-test-key")
        if request.url.path == "/storage/v1/bucket/remind-sources":
            return httpx.Response(200, json={"id": "remind-sources", "public": state["public"]})
        if request.method == "POST":
            assert request.headers["x-upsert"] == "false"
            state["objects"][request.url.path] = request.content
            return httpx.Response(200, json={"Key": request.url.path})
        if request.method == "DELETE":
            import json
            for key in json.loads(request.content)["prefixes"]:
                state["objects"].pop("/storage/v1/object/remind-sources/" + key, None)
            return httpx.Response(200, json=[])
        path = request.url.path.replace("/object/authenticated/", "/object/")
        if path not in state["objects"]:
            return httpx.Response(404, json={"code": "NoSuchKey"})
        return httpx.Response(200, content=state["objects"][path])
    original = httpx.Client
    monkeypatch.setattr(storage_service.httpx, "Client", lambda **kwargs: original(
        transport=httpx.MockTransport(handle), **kwargs))
    return state


def test_remote_upload_download_and_isolation(client, tokens, remote_store):
    response = _upload(client, tokens["contributor"], "holiday.jpg", b"synthetic-photo")
    assert response.status_code == 201
    source = response.json()
    assert source["storage_path"].startswith("supabase://remind-sources/")
    path = f"/sources/{source['id']}/file"
    for role in ("contributor2", "patient", "admin"):
        before = len(remote_store["requests"])
        assert client.get(path, headers=auth(tokens[role])).status_code == 403
        assert len(remote_store["requests"]) == before
    response = client.get(path, headers=auth(tokens["reviewer"]))
    assert response.status_code == 200
    assert response.content == b"synthetic-photo"
    assert response.headers["cache-control"] == "private, no-store"
    assert "server-only-test-key" not in response.text
    # Rehydrate only persisted metadata, as a new API process would after restart.
    stored = SimpleNamespace(id=source["id"], patient_id=source["patient_id"],
                             file_name=source["file_name"], storage_path=source["storage_path"])
    assert storage_service.read_source(stored) == b"synthetic-photo"
    assert client.delete(f"/sources/{source['id']}", headers=auth(tokens["reviewer"])).status_code == 200
    before = len(remote_store["requests"])
    assert client.get(path, headers=auth(tokens["reviewer"])).status_code == 404
    assert len(remote_store["requests"]) == before


def test_public_bucket_and_provider_failure_block_upload(client, tokens, remote_store):
    remote_store["public"] = True
    assert _upload(client, tokens["contributor"], "public.jpg").status_code == 503
    assert remote_store["objects"] == {}
    remote_store["fail"] = True
    response = _upload(client, tokens["contributor"], "offline.jpg")
    assert response.status_code == 503
    assert "server-only-test-key" not in response.text
    with SessionLocal() as db:
        assert db.query(Source).filter(Source.file_name.in_(["public.jpg", "offline.jpg"])).count() == 0


def test_remote_reference_cannot_target_another_source(client, tokens, remote_store):
    first = _upload(client, tokens["contributor"], "first.jpg").json()
    second = _upload(client, tokens["contributor"], "second.jpg").json()
    with SessionLocal() as db:
        db.get(Source, first["id"]).storage_path = second["storage_path"]
        db.commit()
    before = len(remote_store["requests"])
    response = client.get(f"/sources/{first['id']}/file", headers=auth(tokens["reviewer"]))
    assert response.status_code == 404
    assert len(remote_store["requests"]) == before


def test_missing_remote_file_returns_404(client, tokens, remote_store):
    source = _upload(client, tokens["contributor"], "missing.jpg").json()
    remote_store["objects"].clear()
    assert client.get(f"/sources/{source['id']}/file", headers=auth(tokens["reviewer"])).status_code == 404


def test_upload_size_and_empty_files_are_rejected(client, tokens, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    assert _upload(client, tokens["contributor"], "large.jpg", b"12345").status_code == 413
    assert _upload(client, tokens["contributor"], "empty.jpg", b"").status_code == 400


def test_failed_transaction_removes_new_remote_object(client, tokens, remote_store, monkeypatch):
    from sqlalchemy.orm import Session

    original = Session.commit
    def fail_upload(session):
        # Authentication commits first. Fail only after bytes have been uploaded.
        if remote_store["objects"]:
            raise RuntimeError("synthetic commit failure")
        return original(session)
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_upload)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            _upload(client, tokens["contributor"], "rollback.jpg")
    assert remote_store["objects"] == {}
    assert any(method == "DELETE" for method, _ in remote_store["requests"])
    with SessionLocal() as db:
        assert db.query(Source).filter_by(file_name="rollback.jpg").count() == 0


def test_changed_bucket_privacy_and_consent_block_download(client, tokens, remote_store):
    from tests.test_consent_enforcement import _current_policy

    source = _upload(client, tokens["contributor"], "private.jpg").json()
    path = f"/sources/{source['id']}/file"
    remote_store["public"] = True
    assert client.get(path, headers=auth(tokens["reviewer"])).status_code == 503
    remote_store["public"] = False
    policy = _current_policy(client, tokens["patient"])
    actions = policy["permissions"]["role_actions"]["family_reviewer"]
    policy["permissions"]["role_actions"]["family_reviewer"] = [a for a in actions if a != "sources:view"]
    assert client.post("/consent/directives", json=policy, headers=auth(tokens["patient"])).status_code == 201
    before = len(remote_store["requests"])
    assert client.get(path, headers=auth(tokens["reviewer"])).status_code == 403
    assert len(remote_store["requests"]) == before
