"""Administrator-only routes (spec §23)."""

from tests.conftest import auth

PASSWORD = "password123"


def _create_user(client, token, email, role, patient_id):
    return client.post("/admin/users", json={
        "email": email, "full_name": "New User", "role": role,
        "password": PASSWORD, "patient_id": patient_id,
    }, headers=auth(token))


def test_admin_only(client, tokens):
    r = client.get("/admin/users", headers=auth(tokens["admin"]))
    assert r.status_code == 200 and r.json()["count"] >= 8
    r = client.get("/admin/stats", headers=auth(tokens["admin"]))
    assert r.status_code == 200

    for role in ("patient", "clinician", "caregiver", "guardian"):
        r = client.get("/admin/users", headers=auth(tokens[role]))
        assert r.status_code == 403, role
        r = client.get("/admin/stats", headers=auth(tokens[role]))
        assert r.status_code == 403, role
        r = _create_user(client, tokens[role], f"x.{role}@admin.test", "reviewer",
                         tokens["patient"])
        assert r.status_code == 403, role


def test_stats_shape(client, tokens):
    r = client.get("/admin/stats", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    body = r.json()
    assert "users_by_role" in body and "total_sources" in body and "total_memories" in body
    assert body["users_by_role"]["administrator"] == 1


def test_create_user_and_login(client, tokens, users):
    email = "new.contributor@admin.test"
    r = _create_user(client, tokens["admin"], email, "family_contributor",
                     users["patient"].id)
    assert r.status_code == 201
    assert r.json()["role"] == "family_contributor"
    assert r.json()["is_active"] is True

    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    access = r.json()["access_token"]
    r = client.get("/auth/me", headers=auth(access))
    assert r.status_code == 200 and r.json()["email"] == email


def test_create_user_validation(client, tokens, users):
    r = _create_user(client, tokens["admin"], "dup@admin.test", "family_reviewer",
                     users["patient"].id)
    assert r.status_code == 201
    r = _create_user(client, tokens["admin"], "dup@admin.test", "family_reviewer",
                     users["patient"].id)
    assert r.status_code == 409

    r = _create_user(client, tokens["admin"], "bad.role@admin.test", "superuser",
                     users["patient"].id)
    assert r.status_code == 400

    r = _create_user(client, tokens["admin"], "no.patient@admin.test", "family_reviewer", None)
    assert r.status_code == 400

    r = _create_user(client, tokens["admin"], "bad.patient@admin.test", "family_reviewer",
                     users["reviewer"].id)
    assert r.status_code == 400

    r = _create_user(client, tokens["admin"], "patient.link@admin.test", "patient",
                     users["patient"].id)
    assert r.status_code == 400


def test_deactivate_and_reactivate(client, tokens, users):
    email = "toggle@admin.test"
    r = _create_user(client, tokens["admin"], email, "family_contributor",
                     users["patient"].id)
    user_id = r.json()["id"]
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    old_token = r.json()["access_token"]

    r = client.patch(f"/admin/users/{user_id}", json={"is_active": False},
                     headers=auth(tokens["admin"]))
    assert r.status_code == 200 and r.json()["is_active"] is False

    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 403  # account disabled
    r = client.get("/auth/me", headers=auth(old_token))
    assert r.status_code == 401  # existing token now rejected

    r = client.patch(f"/admin/users/{user_id}", json={"is_active": True},
                     headers=auth(tokens["admin"]))
    assert r.status_code == 200
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200


def test_admin_cannot_deactivate_self(client, tokens):
    me = client.get("/auth/me", headers=auth(tokens["admin"])).json()
    r = client.patch(f"/admin/users/{me['id']}", json={"is_active": False},
                     headers=auth(tokens["admin"]))
    assert r.status_code == 400
    r = client.patch(f"/admin/users/{me['id']}", json={"role": "caregiver"},
                     headers=auth(tokens["admin"]))
    assert r.status_code == 400


def test_admin_reset_password_and_role(client, tokens, users):
    email = "reset@admin.test"
    r = _create_user(client, tokens["admin"], email, "family_contributor",
                     users["patient"].id)
    user_id = r.json()["id"]

    r = client.patch(f"/admin/users/{user_id}",
                     json={"password": "brandnewpass1", "role": "family_reviewer"},
                     headers=auth(tokens["admin"]))
    assert r.status_code == 200
    assert r.json()["role"] == "family_reviewer"

    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 401
    r = client.post("/auth/login", json={"email": email, "password": "brandnewpass1"})
    assert r.status_code == 200


def test_admin_patch_unknown_user(client, tokens):
    r = client.patch("/admin/users/does-not-exist", json={"is_active": False},
                     headers=auth(tokens["admin"]))
    assert r.status_code == 404


def test_stats_shape(client, tokens):
    r = client.get("/admin/stats", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    body = r.json()
    assert "users_by_role" in body and "total_sources" in body and "total_memories" in body
    assert body["users_by_role"]["administrator"] == 1
