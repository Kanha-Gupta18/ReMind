"""RBAC matrix: each role against the key create/list routes (spec §23).

Each parametrized row runs with a freshly wiped DB. Expected codes encode
the declared role model; administrator often needs an explicit patient_id,
so admin rows may expect 400 (missing patient) instead of 200.
"""

import pytest

from tests.conftest import auth

# (role_key, method, path, json_body, expected_status)
ROWS = [
    # --- memories ---
    ("patient", "post", "/memories", {"title": "t", "narrative": "x"}, 201),
    ("contributor", "post", "/memories", {"title": "t", "narrative": "x"}, 201),
    ("reviewer", "post", "/memories", {"title": "t", "narrative": "x"}, 201),
    ("caregiver", "post", "/memories", {"title": "t", "narrative": "x"}, 403),
    ("clinician", "post", "/memories", {"title": "t", "narrative": "x"}, 403),
    ("admin", "post", "/memories", {"title": "t", "narrative": "x"}, 403),
    # --- sources ---
    ("contributor", "post", "/sources", {"file_name": "a.jpg", "file_type": "photo"}, 201),
    ("reviewer", "post", "/sources", {"file_name": "a.jpg", "file_type": "photo"}, 201),
    ("patient", "post", "/sources", {"file_name": "a.jpg", "file_type": "photo"}, 403),
    ("caregiver", "post", "/sources", {"file_name": "a.jpg", "file_type": "photo"}, 403),
    ("clinician", "post", "/sources", {"file_name": "a.jpg", "file_type": "photo"}, 403),
    ("admin", "post", "/sources", {"file_name": "a.jpg", "file_type": "photo"}, 400),
    # --- conversations ---
    ("patient", "post", "/conversations/sessions", {"session_type": "chat"}, 201),
    ("contributor", "post", "/conversations/sessions", {"session_type": "chat"}, 403),
    ("reviewer", "post", "/conversations/sessions", {"session_type": "chat"}, 403),
    ("caregiver", "post", "/conversations/sessions", {"session_type": "chat"}, 403),
    ("admin", "post", "/conversations/sessions", {"session_type": "chat"}, 403),
    # --- timeline ---
    ("admin", "get", "/timeline", None, 403),
    # --- admin only ---
    ("patient", "get", "/admin/stats", None, 403),
    ("caregiver", "get", "/admin/stats", None, 403),
    ("admin", "get", "/admin/stats", None, 200),
]


@pytest.mark.parametrize("role,method,path,body,expected", ROWS, ids=[
    f"{m}_{r}_{p}" for r, m, p, _, _ in ROWS])
def test_rbac_matrix(client, tokens, role, method, path, body, expected):
    fn = getattr(client, method)
    kwargs = {"headers": auth(tokens[role])}
    if body is not None:
        kwargs["json"] = body
    r = fn(path, **kwargs)
    assert r.status_code == expected, f"{role} {method.upper()} {path} -> {r.status_code}"
