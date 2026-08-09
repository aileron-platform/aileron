"""Workspace share candidate contract tests."""

from __future__ import annotations

from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.workspace.catalog import WorkspaceService


def test_share_candidates_are_member_safe_and_exclude_existing_targets(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="candidate-owner",
        platform_role="member",
        role_status="valid",
    )
    candidate = create_user(
        id="candidate-user",
        display_name="Candidate User",
        platform_role="member",
        role_status="valid",
    )
    shared = create_user(
        id="shared-user",
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as session:
        session.add_all(
            [
                db_models.UserGroup(id="candidate-group", name="Candidate Group"),
                db_models.UserGroup(id="shared-group", name="Shared Group"),
                db_models.Workspace(
                    id="workspace-candidates",
                    owner_id=owner.id,
                    name="Candidates",
                    runtime="universal",
                    provisioner="docker",
                ),
                db_models.WorkspaceShare(
                    id="share-user",
                    workspace_id="workspace-candidates",
                    target_type="user",
                    target_id=shared.id,
                    role="reader",
                    granted_by_user_id=owner.id,
                ),
                db_models.WorkspaceShare(
                    id="share-group",
                    workspace_id="workspace-candidates",
                    target_type="user_group",
                    target_id="shared-group",
                    role="reader",
                    granted_by_user_id=owner.id,
                ),
            ]
        )
        session.commit()
        service = WorkspaceService(session)

        users = service.list_share_candidate_users(
            actor=actor_from_valid_user(owner),
            workspace_id="workspace-candidates",
            query="Candidate",
            limit=8,
        )
        groups = service.list_share_candidate_groups(
            actor=actor_from_valid_user(owner),
            workspace_id="workspace-candidates",
            query="Candidate",
            limit=8,
        )

        assert [(item[0], item[1]) for item in users] == [
            (candidate.id, "Candidate User")
        ]
        assert [(item[0], item[1]) for item in groups] == [
            ("candidate-group", "Candidate Group")
        ]
