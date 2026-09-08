"""Relationship and consent authorization behavior introduced in Section 3."""

from app.core.database import SessionLocal
from app.models.clinical import Notification
from app.models.constants import AccessGrantStatus, Role
from app.models.user import PatientAccessGrant
from tests.conftest import auth


def _current_policy(client, token):
    directive = client.get("/consent/directives", headers=auth(token)).json()["items"][0]
    return {
        "permissions": directive["permissions"],
        "restrictions": directive["restrictions"],
        "guardian_rules": directive["guardian_rules"],
        "training_opt_in": directive["training_opt_in"],
        "post_death_policy": directive["post_death_policy"],
    }


def test_new_consent_version_changes_access_immediately(client, tokens):
    allowed = client.post(
        "/sources",
        json={"file_name": "before.jpg", "file_type": "photo"},
        headers=auth(tokens["contributor"]),
    )
    assert allowed.status_code == 201

    policy = _current_policy(client, tokens["patient"])
    contributor_actions = policy["permissions"]["role_actions"]["family_contributor"]
    policy["permissions"]["role_actions"]["family_contributor"] = [
        action for action in contributor_actions if action != "sources:upload"
    ]
    changed = client.post(
        "/consent/directives",
        json=policy,
        headers=auth(tokens["patient"]),
    )
    assert changed.status_code == 201

    denied = client.post(
        "/sources",
        json={"file_name": "after.jpg", "file_type": "photo"},
        headers=auth(tokens["contributor"]),
    )
    assert denied.status_code == 403


def test_consent_limits_source_types(client, tokens):
    policy = _current_policy(client, tokens["patient"])
    policy["permissions"]["allowed_data_sources"] = ["photo"]
    assert client.post(
        "/consent/directives",
        json=policy,
        headers=auth(tokens["patient"]),
    ).status_code == 201

    assert client.post(
        "/sources",
        json={"file_name": "allowed.jpg", "file_type": "photo"},
        headers=auth(tokens["contributor"]),
    ).status_code == 201
    assert client.post(
        "/sources",
        json={"file_name": "blocked.mp3", "file_type": "audio"},
        headers=auth(tokens["contributor"]),
    ).status_code == 403


def test_relationship_selection_and_revocation(client, tokens, users):
    with SessionLocal() as db:
        grant = PatientAccessGrant(
            user_id=users["reviewer"].id,
            patient_id=users["patient2"].id,
            relationship=Role.FAMILY_REVIEWER.value,
        )
        db.add(grant)
        db.commit()
        grant_id = grant.id

    try:
        assert client.get("/memories", headers=auth(tokens["reviewer"])).status_code == 400
        selected = client.get(
            "/memories",
            headers={**auth(tokens["reviewer"]), "X-Patient-ID": users["patient2"].id},
        )
        assert selected.status_code == 200

        with SessionLocal() as db:
            stored = db.get(PatientAccessGrant, grant_id)
            stored.status = AccessGrantStatus.REVOKED.value
            db.commit()
        assert client.get(
            "/memories",
            headers={**auth(tokens["reviewer"]), "X-Patient-ID": users["patient2"].id},
        ).status_code == 403
    finally:
        with SessionLocal() as db:
            db.query(PatientAccessGrant).filter(PatientAccessGrant.id == grant_id).delete()
            db.commit()


def test_guardian_cannot_expand_patient_directive(client, tokens):
    policy = _current_policy(client, tokens["guardian"])
    policy["training_opt_in"] = True
    response = client.post(
        "/consent/directives",
        json=policy,
        headers=auth(tokens["guardian"]),
    )
    assert response.status_code == 403


def test_administrator_cannot_select_patient_content(client, tokens, users):
    response = client.get(
        "/memories",
        params={"patient_id": users["patient"].id},
        headers=auth(tokens["admin"]),
    )
    assert response.status_code == 403


def test_consent_change_hides_existing_notification_content(client, tokens, users):
    with SessionLocal() as db:
        notification = Notification(
            user_id=users["reviewer"].id,
            patient_id=users["patient"].id,
            required_action="memories:review",
            type="review_needed",
            message="A private memory title",
        )
        db.add(notification)
        db.commit()
        notification_id = notification.id

    visible = client.get("/notifications", headers=auth(tokens["reviewer"]))
    assert any(item["id"] == notification_id for item in visible.json()["items"])

    policy = _current_policy(client, tokens["patient"])
    reviewer_actions = policy["permissions"]["role_actions"]["family_reviewer"]
    policy["permissions"]["role_actions"]["family_reviewer"] = [
        action for action in reviewer_actions if action != "memories:review"
    ]
    assert client.post(
        "/consent/directives", json=policy, headers=auth(tokens["patient"])
    ).status_code == 201

    hidden = client.get("/notifications", headers=auth(tokens["reviewer"]))
    assert all(item["id"] != notification_id for item in hidden.json()["items"])
    assert client.post(
        f"/notifications/{notification_id}/read", headers=auth(tokens["reviewer"])
    ).status_code == 404
