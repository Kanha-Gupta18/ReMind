"""Deployment settings and readiness must fail closed without exposing secrets."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app import main
from app.services import storage_service


def _production(**changes):
    values = dict(environment="production", jwt_secret="random-for-tests-only-" + "a" * 32,
                  cookie_secure=True, cors_origins=["https://remind.example.com"],
                  storage_backend="supabase", supabase_url="https://test.supabase.co",
                  supabase_service_role_key="server-only-test-key",
                  database_url="postgresql+psycopg://user:pass@db.example.com/remind?sslmode=require")
    values.update(changes)
    return Settings(_env_file=None, **values)


def test_production_accepts_explicit_secure_configuration():
    assert _production().storage_backend == "supabase"


@pytest.mark.parametrize("changes", [
    {"jwt_secret": "dev-secret-change-in-production-0123456789abcdef"},
    {"jwt_secret": "short"}, {"cookie_secure": False}, {"cors_origins": ["*"]},
    {"cors_origins": ["http://localhost:3000"]},
    {"cors_origins": ["https://web.example.com/path"]},
    {"storage_backend": "local"}, {"supabase_service_role_key": ""},
    {"supabase_url": "http://test.supabase.co"},
    {"supabase_url": "https://user:secret@test.supabase.co"},
    {"supabase_storage_bucket": "../other"},
    {"database_url": "postgresql+psycopg://user:pass@db.example.com/remind"},
])
def test_production_rejects_unsafe_settings(changes):
    with pytest.raises(ValidationError) as error:
        _production(**changes)
    assert "server-only-test-key" not in str(error.value)


def test_ready_checks_real_test_database_and_migrations(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == dict(database="ready", migrations="ready", storage="ready")


def test_storage_failure_makes_ready_unavailable(client, monkeypatch):
    def fail():
        raise storage_service.StorageUnavailable("private-provider-detail")
    monkeypatch.setattr(storage_service, "check_storage", fail)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["storage"] == "unavailable"
    assert "private-provider-detail" not in response.text


def test_database_failure_makes_health_and_ready_unavailable(client, monkeypatch):
    def fail():
        raise RuntimeError("secret-database-url")
    monkeypatch.setattr(main.engine, "connect", fail)
    for route in ("/health", "/ready"):
        response = client.get(route)
        assert response.status_code == 503
        assert "secret-database-url" not in response.text


def test_stale_schema_is_not_ready(client, monkeypatch):
    monkeypatch.setattr(main.ScriptDirectory, "get_heads", lambda self: ["future-migration"])
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["migrations"] == "unavailable"
