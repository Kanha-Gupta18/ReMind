"""Authentication: login, refresh, logout, /me (spec §22)."""

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


def test_logout_requires_auth_and_succeeds(client, tokens):
    assert client.post("/auth/logout").status_code == 401
    r = client.post("/auth/logout", headers=auth(tokens["patient"]))
    assert r.status_code == 200 and r.json()["ok"] is True


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
