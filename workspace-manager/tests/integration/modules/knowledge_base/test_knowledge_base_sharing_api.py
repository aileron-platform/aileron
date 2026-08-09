"""Knowledge base sharing API contract tests."""

from __future__ import annotations

from sqlalchemy import select

from app.db import models as db_models
from tests.helpers.manager_session import authenticate_client_as


def _authenticate_as(client, _monkeypatch, user: db_models.User) -> None:
    authenticate_client_as(client, user)


def _create_groups(session_factory) -> None:
    with session_factory() as session:
        session.add_all(
            [
                db_models.UserGroup(id="group-1", name="SA Team", description=None),
                db_models.UserGroup(id="group-2", name="Ops Team", description=None),
                db_models.UserGroup(id="group-3", name="Finance", description=None),
            ]
        )
        session.commit()


def test_share_responses_include_target_label_and_candidate_groups_are_scoped(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    owner = create_user(
        id="owner-1", username="owner", platform_role="member", role_status="valid"
    )
    member = create_user(
        id="user-1",
        username="amelia",
        display_name="Amelia Chen",
        email="amelia@example.com",
    )
    outsider = create_user(
        id="user-2", username="outsider", platform_role="member", role_status="valid"
    )
    _create_groups(session_factory)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "API Docs", "slug": "api-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    user_share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        headers={"X-Correlation-ID": "11111111-1111-4111-8111-111111111111"},
        json={"targetType": "user", "targetId": member.id, "role": "reader"},
    )
    group_share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user_group", "targetId": "group-1", "role": "manager"},
    )
    list_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/shares")
    update_response = client.patch(
        f"/api/v1/knowledge-bases/{kb_id}/shares/{user_share_response.json()['id']}",
        headers={"X-Correlation-ID": "22222222-2222-4222-8222-222222222222"},
        json={"role": "manager"},
    )
    candidate_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/share-candidate-groups",
        params={"query": "team", "limit": 1},
    )
    delete_response = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/shares/{user_share_response.json()['id']}",
        headers={"X-Correlation-ID": "33333333-3333-4333-8333-333333333333"},
    )

    with session_factory() as session:
        user_share_audits = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(
                    db_models.AuditEvent.correlation_id.in_(
                        [
                            "11111111-1111-4111-8111-111111111111",
                            "22222222-2222-4222-8222-222222222222",
                            "33333333-3333-4333-8333-333333333333",
                        ]
                    )
                )
                .order_by(db_models.AuditEvent.created_at)
            ).all()
        )

    assert create_kb_response.status_code == 201
    assert user_share_response.status_code == 201
    assert user_share_response.json()["targetLabel"] == "Amelia Chen"
    assert group_share_response.status_code == 201
    assert group_share_response.json()["targetLabel"] == "SA Team"
    assert list_response.status_code == 200
    assert {
        item["targetId"]: item["targetLabel"] for item in list_response.json()["items"]
    } == {
        member.id: "Amelia Chen",
        "group-1": "SA Team",
    }
    assert update_response.status_code == 200
    assert update_response.json()["targetLabel"] == "Amelia Chen"
    assert candidate_response.status_code == 200
    assert candidate_response.json() == {
        "items": [{"id": "group-2", "name": "Ops Team"}]
    }
    assert delete_response.status_code == 204
    assert [event.event_type for event in user_share_audits] == [
        "knowledge_base.share_created",
        "knowledge_base.share_updated",
        "knowledge_base.share_deleted",
    ]

    _authenticate_as(client, monkeypatch, outsider)
    forbidden_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/share-candidate-groups"
    )
    assert forbidden_response.status_code == 404
    assert forbidden_response.json()["detail"]["errorCode"] == "KB_ACCESS_DENIED"


def test_share_target_validation_returns_design_error_codes(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, _ = test_app
    owner = create_user(
        id="owner-1", username="owner", platform_role="member", role_status="valid"
    )
    member = create_user(
        id="user-1", username="member", platform_role="member", role_status="valid"
    )
    outsider = create_user(
        id="outsider-1",
        username="outsider",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "API Docs", "slug": "api-docs"},
    ).json()["id"]

    invalid_type = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "team", "targetId": member.id, "role": "reader"},
    )
    missing_target = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": "missing", "role": "reader"},
    )
    owner_target = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": owner.id, "role": "reader"},
    )
    created = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": member.id, "role": "reader"},
    )
    duplicate = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": member.id, "role": "manager"},
    )
    _authenticate_as(client, monkeypatch, outsider)
    forbidden = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": outsider.id, "role": "reader"},
    )

    assert invalid_type.status_code == 400
    assert invalid_type.json()["detail"]["errorCode"] == "KB_SHARE_INVALID_TARGET_TYPE"
    assert missing_target.status_code == 404
    assert missing_target.json()["detail"]["errorCode"] == "KB_SHARE_TARGET_NOT_FOUND"
    assert owner_target.status_code == 409
    assert (
        owner_target.json()["detail"]["errorCode"] == "KB_SHARE_OWNER_TARGET_FORBIDDEN"
    )
    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["errorCode"] == "KB_SHARE_DUPLICATE_TARGET"
    assert forbidden.status_code == 404
    assert forbidden.json()["detail"]["errorCode"] == "KB_ACCESS_DENIED"
