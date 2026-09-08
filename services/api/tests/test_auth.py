"""Authentication: login, refresh, logout, /me (spec §22)."""

from datetime import timedelta

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.base import utcnow
from app.models.user import AuthSession

from tests.conftest import PASSWORD, auth


def test_login_success(client, users):
    r = client.post("/auth/login", json={"email": users["patient"].email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == users["patient"].email
    assert body["user"]["role"] == "patient"


def test_login_wrong_password(client, users):
    r = client.post("/auth/login", json={"email": users["patient"].email, "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/auth/login", json={"email": "ghost@remind.dev", "password": PASSWORD})
    assert r.status_code == 401


def test_refresh_flow(client, users):
    login = client.post("/auth/login",
                        json={"email": users["patient"].email, "password": PASSWORD}).json()
    r = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    r = client.get("/auth/me", headers=auth(body["access_token"]))
    assert r.status_code == 200 and r.json()["email"] == users["patient"].email


def test_refresh_rejects_access_token(client, users):
    login = client.post("/auth/login",
                        json={"email": users["patient"].email, "password": PASSWORD}).json()
    r = client.post("/auth/refresh", json={"refresh_token": login["access_token"]})
    assert r.status_code == 401


def test_refresh_rejects_garbage(client):
    r = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert r.status_code == 401


def test_me_returns_current_user(client, tokens):
    r = client.get("/auth/me", headers=auth(tokens["reviewer"]))
    assert r.status_code == 200
    assert r.json()["role"] == "family_reviewer"


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_bad_tokens(client, tokens):
    assert client.get("/auth/me", headers=auth("garbage")).status_code == 401
    assert client.get("/auth/me", headers=auth(tokens["patient"])).status_code == 200


def test_logout_requires_auth_and_revokes_session(client, users):
    assert client.post("/auth/logout").status_code == 401
    login = client.post("/auth/login", json={
        "email": users["patient"].email,
        "password": PASSWORD,
    }).json()
    headers = auth(login["access_token"])
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    ).status_code == 401


def test_refresh_token_is_single_use(client, users):
    login = client.post("/auth/login", json={
        "email": users["patient"].email,
        "password": PASSWORD,
    }).json()
    first = client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert first.status_code == 200
    replay = client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert replay.status_code == 401


def test_idle_session_expiry_invalidates_access_and_refresh(client, users):
    login = client.post("/auth/login", json={
        "email": users["patient"].email,
        "password": PASSWORD,
    }).json()
    session_id = decode_token(login["access_token"])["sid"]
    with SessionLocal() as db:
        session = db.get(AuthSession, session_id)
        session.idle_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()

    assert client.get("/auth/me", headers=auth(login["access_token"])).status_code == 401
    assert client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    ).status_code == 401


def test_disabled_account_cannot_login(client, users):
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models.base import new_id
    from app.models.user import AuditLog, User

    db = SessionLocal()
    temp = User(email=f"disabled.{new_id()[:8]}@remind.dev",
                password_hash=hash_password(PASSWORD), full_name="Disabled",
                role="caregiver", is_active=False)
    db.add(temp)
    db.commit()
    temp_id = temp.id
    db.close()
    try:
        r = client.post("/auth/login", json={"email": temp.email, "password": PASSWORD})
        assert r.status_code == 403
    finally:
        db = SessionLocal()
        db.query(AuditLog).filter(AuditLog.user_id == temp_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == temp_id).delete(synchronize_session=False)
        db.commit()
        db.close()
