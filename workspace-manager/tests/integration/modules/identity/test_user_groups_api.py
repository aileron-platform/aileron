"""User group API contract tests."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.db import models as db_models
from app.modules.identity.admin_authorization import require_admin_user
from tests.helpers.manager_session import authenticate_client_as


def _authorize(client, admin: db_models.User) -> None:
    authenticate_client_as(client, admin)


def _create_group(
    client, *, name: str = "Support", description: str | None = None
) -> str:
    payload: dict[str, str | None] = {"name": name}
    if description is not None:
        payload["description"] = description
    response = client.post("/api/v1/admin/user-groups", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_group_crud_detail_list_counts_and_audit(test_app, create_user) -> None:
    client, session_factory = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    member = create_user(
        id="member-1",
        username="amelia",
        platform_role="member",
        role_status="valid",
    )
    _authorize(client, admin)

    group_id = _create_group(
        client,
        name=" Support ",
        description=" Customer support ",
    )
    _create_group(client, name="Empty")
    add_response = client.post(
        f"/api/v1/admin/user-groups/{group_id}/members",
        json={"userIds": [member.id]},
    )
    assert add_response.status_code == 200

    with session_factory() as session:
        session.add(
            db_models.KnowledgeBase(
                id="kb-1",
                slug="kb-1",
                name="KB 1",
                owner_id=admin.id,
            )
        )
        session.flush()
        session.add(
            db_models.KnowledgeBaseShare(
                id="share-1",
                kb_id="kb-1",
                target_type="user_group",
                target_id=group_id,
                role="reader",
                granted_by_id=admin.id,
            )
        )
        session.commit()

    detail = client.get(f"/api/v1/admin/user-groups/{group_id}")
    assert detail.status_code == 200
    assert detail.json() == {
        "id": group_id,
        "name": "Support",
        "description": "Customer support",
        "memberCount": 1,
        "knowledgeBaseShareCount": 1,
        "createdAt": detail.json()["createdAt"],
        "updatedAt": detail.json()["updatedAt"],
    }

    listed = client.get(
        "/api/v1/admin/user-groups"
        "?q=supp&memberCountRange=1_10&hasDescription=true"
        "&updatedWithinDays=7&page=1&pageSize=1"
        "&sortBy=memberCount&sortDirection=desc"
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["page"] == 1
    assert listed.json()["pageSize"] == 1
    assert [item["id"] for item in listed.json()["items"]] == [group_id]

    beyond_end = client.get("/api/v1/admin/user-groups?page=99&pageSize=1&sortBy=name")
    assert beyond_end.status_code == 200
    assert beyond_end.json()["items"] == []
    assert beyond_end.json()["total"] == 2

    blank_query = client.get("/api/v1/admin/user-groups?q=%20%20")
    assert blank_query.status_code == 200
    assert blank_query.json()["total"] == 2

    patched = client.patch(
        f"/api/v1/admin/user-groups/{group_id}",
        json={"description": None},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] is None

    deleted = client.delete(f"/api/v1/admin/user-groups/{group_id}")
    assert deleted.status_code == 204
    with session_factory() as session:
        events = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(db_models.AuditEvent.target_type == "user_group")
                .order_by(db_models.AuditEvent.created_at, db_models.AuditEvent.id)
            ).all()
        )
        event_types = [event.event_type for event in events]
        assert event_types.count("user_group.created") == 2
        assert event_types[-2:] == ["user_group.updated", "user_group.deleted"]
        assert all(event.actor_user_id == admin.id for event in events)


def test_group_duplicate_name_and_not_found_errors(test_app, create_user) -> None:
    client, _ = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    _authorize(client, admin)
    _create_group(client, name="Support")

    duplicate = client.post(
        "/api/v1/admin/user-groups",
        json={"name": "Support"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["errorCode"] == "KB_GROUP_ADMIN_DUPLICATE_NAME"

    missing = client.get("/api/v1/admin/user-groups/missing")
    assert missing.status_code == 404
    assert missing.json()["errorCode"] == "KB_GROUP_ADMIN_NOT_FOUND"


def test_group_admin_forbidden_uses_shared_user_admin_code(
    test_app,
    create_user,
) -> None:
    client, _ = test_app
    member = create_user(
        id="member-1",
        platform_role="member",
        role_status="valid",
    )
    _authorize(client, member)

    def deny_group_admin() -> None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="USER_ADMIN_FORBIDDEN",
        )

    client.app.dependency_overrides[require_admin_user] = deny_group_admin
    response = client.get("/api/v1/admin/user-groups")

    assert response.status_code == 403
    assert response.json()["errorCode"] == "USER_ADMIN_FORBIDDEN"
    assert response.json()["correlationId"]


def test_member_and_candidate_queries_are_flattened_server_pages(
    test_app,
    create_user,
) -> None:
    client, _ = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    member = create_user(
        id="member-1",
        username="bravo",
        first_name="Brenda",
        last_name="Member",
        platform_role="member",
        role_status="valid",
    )
    create_user(
        id="candidate-1",
        username="alpha",
        first_name="Alice",
        last_name="Candidate",
        platform_role="member",
        role_status="valid",
    )
    create_user(
        id="candidate-2",
        username="charlie",
        platform_role=None,
        role_status="missing",
    )
    create_user(
        id="display-only",
        username="delta",
        first_name="Nope",
        last_name="Nope",
        email="delta@example.com",
        display_name="display-secret",
        platform_role=None,
        role_status="missing",
    )
    _authorize(client, admin)
    group_id = _create_group(client)
    client.post(
        f"/api/v1/admin/user-groups/{group_id}/members",
        json={"userIds": [member.id]},
    )

    members = client.get(
        f"/api/v1/admin/user-groups/{group_id}/members"
        "?q=brenda&role=member&accountState=active&source=manual"
        "&page=1&pageSize=10&sortBy=username&sortDirection=asc"
    )
    assert members.status_code == 200
    assert members.json()["total"] == 1
    member_payload = members.json()["items"][0]
    assert member_payload["userId"] == member.id
    assert member_payload["source"] == "manual"
    assert member_payload["firstName"] == "Brenda"
    assert "joinedAt" in member_payload
    assert "user" not in member_payload
    assert "groupId" not in member_payload

    member_beyond_end = client.get(
        f"/api/v1/admin/user-groups/{group_id}/members?page=99&pageSize=1"
    )
    assert member_beyond_end.status_code == 200
    assert member_beyond_end.json()["items"] == []
    assert member_beyond_end.json()["total"] == 1

    candidates = client.get(
        f"/api/v1/admin/user-groups/{group_id}/member-candidates"
        "?roleStatus=valid&page=1&pageSize=1"
        "&sortBy=username&sortDirection=asc"
    )
    assert candidates.status_code == 200
    assert candidates.json()["total"] == 2
    assert candidates.json()["items"][0]["userId"] == "candidate-1"
    assert candidates.json()["items"][0]["membershipStatus"] == "not_member"
    assert "issuer" not in candidates.json()["items"][0]
    assert "subject" not in candidates.json()["items"][0]

    candidates_beyond_end = client.get(
        f"/api/v1/admin/user-groups/{group_id}/member-candidates"
        "?roleStatus=valid&page=99&pageSize=1"
    )
    assert candidates_beyond_end.status_code == 200
    assert candidates_beyond_end.json()["items"] == []
    assert candidates_beyond_end.json()["total"] == 2

    all_membership = client.get(
        f"/api/v1/admin/user-groups/{group_id}/member-candidates"
        "?membership=all&q=bravo"
    )
    assert all_membership.status_code == 200
    assert all_membership.json()["items"][0]["membershipStatus"] == "member"

    display_name_is_not_searchable = client.get(
        f"/api/v1/admin/user-groups/{group_id}/member-candidates"
        "?membership=all&q=display-secret"
    )
    assert display_name_is_not_searchable.status_code == 200
    assert display_name_is_not_searchable.json()["total"] == 0


def test_batch_mutations_return_skipped_and_structured_failures(
    test_app,
    create_user,
) -> None:
    client, _ = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    valid = create_user(
        id="valid-1",
        platform_role="member",
        role_status="valid",
        sync_status="local_shadow_imported",
    )
    disabled = create_user(
        id="disabled-1",
        platform_role="member",
        role_status="valid",
        is_active=False,
    )
    invalid_role = create_user(
        id="invalid-role-1",
        platform_role=None,
        role_status="missing",
    )
    _authorize(client, admin)
    group_id = _create_group(client)

    added = client.post(
        f"/api/v1/admin/user-groups/{group_id}/members",
        json={"userIds": [valid.id, disabled.id, invalid_role.id, "missing-user"]},
    )
    assert added.status_code == 200
    assert added.json() == {
        "addedUserIds": [valid.id],
        "skippedUserIds": [],
        "failedUsers": [
            {
                "userId": disabled.id,
                "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE",
            },
            {
                "userId": invalid_role.id,
                "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE",
            },
            {
                "userId": "missing-user",
                "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_FOUND",
            },
        ],
    }

    idempotent = client.post(
        f"/api/v1/admin/user-groups/{group_id}/members",
        json={"userIds": [valid.id]},
    )
    assert idempotent.status_code == 200
    assert idempotent.json()["skippedUserIds"] == [valid.id]

    removed = client.post(
        f"/api/v1/admin/user-groups/{group_id}/members/batch-remove",
        json={"userIds": [valid.id, disabled.id, "missing-user"]},
    )
    assert removed.status_code == 200
    assert removed.json()["removedUserIds"] == [valid.id]
    assert removed.json()["skippedUserIds"] == [disabled.id]
    assert removed.json()["failedUsers"] == [
        {
            "userId": "missing-user",
            "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_FOUND",
        }
    ]


def test_single_member_delete_and_missing_member_error(test_app, create_user) -> None:
    client, _ = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    member = create_user(id="member-1", platform_role="member", role_status="valid")
    _authorize(client, admin)
    group_id = _create_group(client)
    client.post(
        f"/api/v1/admin/user-groups/{group_id}/members",
        json={"userIds": [member.id]},
    )

    deleted = client.delete(f"/api/v1/admin/user-groups/{group_id}/members/{member.id}")
    assert deleted.status_code == 204
    missing = client.delete(f"/api/v1/admin/user-groups/{group_id}/members/{member.id}")
    assert missing.status_code == 404
    assert missing.json()["errorCode"] == "KB_GROUP_ADMIN_MEMBER_NOT_FOUND"


def test_invalid_group_body_and_query_use_stable_codes(test_app, create_user) -> None:
    client, _ = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    _authorize(client, admin)
    group_id = _create_group(client)

    for payload in (
        {"userIds": []},
        {"userIds": ["user-1", "user-1"]},
        {"userIds": [" user-1"]},
        {"userIds": [f"user-{index}" for index in range(101)]},
        {"userIds": ["user-1"], "unexpected": True},
    ):
        response = client.post(
            f"/api/v1/admin/user-groups/{group_id}/members",
            json=payload,
        )
        assert response.status_code == 400
        assert response.json()["errorCode"] == "KB_GROUP_ADMIN_INVALID_REQUEST"

    invalid_create = client.post(
        "/api/v1/admin/user-groups",
        json={"name": "Invalid", "unexpected": True},
    )
    assert invalid_create.status_code == 400
    assert invalid_create.json()["errorCode"] == "KB_GROUP_ADMIN_INVALID_REQUEST"

    invalid_patch = client.patch(
        f"/api/v1/admin/user-groups/{group_id}",
        json={"name": "Invalid", "unexpected": True},
    )
    assert invalid_patch.status_code == 400
    assert invalid_patch.json()["errorCode"] == "KB_GROUP_ADMIN_INVALID_REQUEST"

    empty_patch = client.patch(
        f"/api/v1/admin/user-groups/{group_id}",
        json={},
    )
    assert empty_patch.status_code == 400
    assert empty_patch.json()["errorCode"] == "KB_GROUP_ADMIN_INVALID_REQUEST"

    invalid_queries = (
        "/api/v1/admin/user-groups?page=0",
        "/api/v1/admin/user-groups?page=1&page=2",
        "/api/v1/admin/user-groups?unknown=value",
        "/api/v1/admin/user-groups?hasDescription=True",
        "/api/v1/admin/user-groups?hasDescription=",
        "/api/v1/admin/user-groups?hasDescription=null",
        "/api/v1/admin/user-groups?memberCountRange=EMPTY",
        "/api/v1/admin/user-groups?memberCountRange=",
        "/api/v1/admin/user-groups?updatedWithinDays=0",
        "/api/v1/admin/user-groups?updatedWithinDays=null",
        "/api/v1/admin/user-groups?sortBy=username",
        "/api/v1/admin/user-groups?sortDirection=ASC",
        f"/api/v1/admin/user-groups?q={'x' * 201}",
        f"/api/v1/admin/user-groups/{group_id}/members?accountState=active,bogus",
        f"/api/v1/admin/user-groups/{group_id}/members?accountState=active,%20identity_disabled",
        f"/api/v1/admin/user-groups/{group_id}/members?accountState=",
        f"/api/v1/admin/user-groups/{group_id}/members?role=VIEWER",
        f"/api/v1/admin/user-groups/{group_id}/members?source=sync",
        f"/api/v1/admin/user-groups/{group_id}/member-candidates?roleStatus=valid,bogus",
        f"/api/v1/admin/user-groups/{group_id}/member-candidates?membership=ALL",
    )
    for path in invalid_queries:
        response = client.get(path)
        assert response.status_code == 400
        assert response.json()["errorCode"] == "KB_GROUP_ADMIN_INVALID_PAGE_REQUEST"


def test_group_delete_cascades_without_runtime_or_mount_side_effects(
    test_app,
    create_user,
) -> None:
    client, session_factory = test_app
    admin = create_user(id="admin-1", platform_role="admin", role_status="valid")
    member = create_user(id="member-1", platform_role="member", role_status="valid")
    _authorize(client, admin)
    group_id = _create_group(client)
    client.post(
        f"/api/v1/admin/user-groups/{group_id}/members",
        json={"userIds": [member.id]},
    )
    with session_factory() as session:
        session.add_all(
            [
                db_models.Workspace(
                    id="workspace-1",
                    owner_id=admin.id,
                    name="Workspace",
                    knowledge_base_mount_desired_revision=7,
                    knowledge_base_mount_observed_revision=7,
                    runtime_access_revision=4,
                    runtime_access_observed_revision=4,
                ),
                db_models.KnowledgeBase(
                    id="kb-1",
                    slug="kb-1",
                    name="KB 1",
                    owner_id=admin.id,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                db_models.KnowledgeBaseShare(
                    id="share-1",
                    kb_id="kb-1",
                    target_type="user_group",
                    target_id=group_id,
                    role="reader",
                    granted_by_id=admin.id,
                ),
                db_models.WorkspaceKnowledgeBaseAttachment(
                    id="attachment-1",
                    workspace_id="workspace-1",
                    kb_id="kb-1",
                    mount_alias="shared-kb",
                    attached_by_id=admin.id,
                ),
            ]
        )
        session.commit()

    response = client.delete(f"/api/v1/admin/user-groups/{group_id}")
    assert response.status_code == 204
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, "workspace-1")
        assert workspace is not None
        assert workspace.knowledge_base_mount_desired_revision == 7
        assert workspace.runtime_access_revision == 4
        assert (
            session.get(db_models.WorkspaceKnowledgeBaseAttachment, "attachment-1")
            is not None
        )
        assert session.get(db_models.KnowledgeBaseShare, "share-1") is None
        assert (
            session.scalar(
                select(func.count(db_models.UserGroupMember.id)).where(
                    db_models.UserGroupMember.group_id == group_id
                )
            )
            or 0
        ) == 0
        assert (
            session.scalar(select(func.count(db_models.WorkspaceRuntimeJob.id))) or 0
        ) == 0
