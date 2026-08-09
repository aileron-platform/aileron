"""PostgreSQL concurrency tests for polymorphic knowledge base targets."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.knowledge_base.access import (
    KnowledgeBaseNotFoundError,
    KnowledgeBaseSharingService,
)
from app.modules.identity.groups import UserGroupService
from app.modules.workspace.catalog import WorkspaceNotFoundError, WorkspaceService
from app.modules.workspace.models import WorkspaceShareCreateRequest

_OWNER_ACTOR = AuthorizationActor(
    user_id="owner-1",
    platform_role="admin",
)


@pytest.fixture()
def knowledge_base_share_database():
    schema = f"knowledge_base_share_{uuid4().hex}"
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def test_group_delete_wins_against_concurrent_share_grant_without_orphan(
    knowledge_base_share_database,
) -> None:
    with Session(knowledge_base_share_database) as session:
        session.add_all(
            [
                db_models.User(
                    id="owner-1",
                    username="owner",
                    email="owner@example.com",
                    identity_enabled=True,
                    sync_status="synced",
                    platform_role="admin",
                    role_status="valid",
                ),
                db_models.UserGroup(id="group-1", name="Group 1"),
            ]
        )
        session.flush()
        session.add(
            db_models.KnowledgeBase(
                id="kb-1",
                slug="kb-1",
                name="KB 1",
                owner_id="owner-1",
            )
        )
        session.commit()

    target_locked = Barrier(2)

    class CoordinatedUserGroupService(UserGroupService):
        def _get_group(self, group_id: str, *, for_update: bool = False):
            group = super()._get_group(group_id, for_update=for_update)
            if for_update:
                target_locked.wait(timeout=10)
            return group

    def delete_group() -> None:
        with Session(knowledge_base_share_database) as session:
            CoordinatedUserGroupService(session).delete_group(
                group_id="group-1",
                actor_user_id="owner-1",
            )

    def grant_share() -> None:
        target_locked.wait(timeout=10)
        with Session(knowledge_base_share_database) as session:
            KnowledgeBaseSharingService(session).grant_share(
                actor=_OWNER_ACTOR,
                kb_id="kb-1",
                target_type="user_group",
                target_id="group-1",
                role="reader",
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(delete_group)
        grant_future = executor.submit(grant_share)
        delete_future.result(timeout=20)
        with pytest.raises(KnowledgeBaseNotFoundError) as exc_info:
            grant_future.result(timeout=20)

    assert exc_info.value.code == "KB_SHARE_TARGET_NOT_FOUND"
    with Session(knowledge_base_share_database) as session:
        assert session.get(db_models.UserGroup, "group-1") is None
        assert (
            session.scalars(
                select(db_models.KnowledgeBaseShare).where(
                    db_models.KnowledgeBaseShare.target_type == "user_group",
                    db_models.KnowledgeBaseShare.target_id == "group-1",
                )
            ).all()
            == []
        )


def test_group_delete_wins_against_concurrent_workspace_share_without_orphan(
    knowledge_base_share_database,
) -> None:
    with Session(knowledge_base_share_database) as session:
        session.add_all(
            [
                db_models.User(
                    id="workspace-owner",
                    username="workspace-owner",
                    email="workspace-owner@example.com",
                    identity_enabled=True,
                    sync_status="synced",
                    platform_role="admin",
                    role_status="valid",
                ),
                db_models.UserGroup(id="workspace-group", name="Workspace Group"),
            ]
        )
        session.flush()
        session.add(
            db_models.Workspace(
                id="workspace-1",
                owner_id="workspace-owner",
                name="Workspace 1",
                provisioner="docker",
                runtime_status="stopped",
            )
        )
        session.commit()

    target_locked = Barrier(2)

    class CoordinatedUserGroupService(UserGroupService):
        def _get_group(self, group_id: str, *, for_update: bool = False):
            group = super()._get_group(group_id, for_update=for_update)
            if for_update:
                target_locked.wait(timeout=10)
            return group

    def delete_group() -> None:
        with Session(knowledge_base_share_database) as session:
            CoordinatedUserGroupService(session).delete_group(
                group_id="workspace-group",
                actor_user_id="workspace-owner",
            )

    def grant_share() -> None:
        target_locked.wait(timeout=10)
        with Session(knowledge_base_share_database) as session:
            WorkspaceService(session).create_share(
                "workspace-1",
                WorkspaceShareCreateRequest(
                    targetType="user_group",
                    targetId="workspace-group",
                    role="reader",
                ),
                actor=AuthorizationActor("workspace-owner", "admin"),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(delete_group)
        grant_future = executor.submit(grant_share)
        delete_future.result(timeout=20)
        with pytest.raises(WorkspaceNotFoundError) as exc_info:
            grant_future.result(timeout=20)

    assert exc_info.value.code == "WORKSPACE_SHARE_TARGET_NOT_FOUND"
    with Session(knowledge_base_share_database) as session:
        assert session.get(db_models.UserGroup, "workspace-group") is None
        assert (
            session.scalars(
                select(db_models.WorkspaceShare).where(
                    db_models.WorkspaceShare.target_type == "user_group",
                    db_models.WorkspaceShare.target_id == "workspace-group",
                )
            ).all()
            == []
        )
