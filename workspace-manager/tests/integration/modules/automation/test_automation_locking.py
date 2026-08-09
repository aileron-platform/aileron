"""PostgreSQL transaction ownership regression tests for Automation Job writes."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.repository import AutomationRepository
from app.modules.automation.authorization import AutomationAuthorizationService


@pytest.mark.integration
def test_authorization_does_not_release_locked_job_row() -> None:
    suffix = uuid4().hex
    schema = f"automation_lock_{suffix}"
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(engine)
    user_id = f"lock-user-{suffix}"
    workspace_id = f"lock-workspace-{suffix}"
    job_id = f"lock-job-{suffix}"
    with Session(engine) as setup:
        setup.add(
            db_models.User(
                id=user_id,
                username=user_id,
                display_name="Lock User",
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        setup.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=user_id,
                name="Lock Workspace",
                provisioner="kubernetes",
            )
        )
        setup.add(
            db_models.AutomationJob(
                id=job_id,
                workspace_id=workspace_id,
                creator_user_id=user_id,
                name="Lock Job",
                prompt="hold lock",
                status="active",
                trigger="manual",
                schedule="",
                exact=False,
                agentic_tool="claude",
                model="claude-sonnet",
                agent_config={
                    "mode": "execute",
                    "permission_mode": "bypassPermissions",
                },
                worktree_key=f"automation/{job_id}",
                worktree_branch=f"automation/{job_id}",
                notification_config={},
            )
        )
        setup.commit()

    first = Session(engine)
    second = Session(engine)
    try:
        assert AutomationRepository(first).lock_job(job_id) is not None

        AutomationAuthorizationService(first).require_execute(
            actor=AuthorizationActor(user_id, "member"),
            workspace_id=workspace_id,
        )

        with pytest.raises(OperationalError):
            second.scalar(
                select(db_models.AutomationJob)
                .where(db_models.AutomationJob.id == job_id)
                .with_for_update(nowait=True)
            )
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()
        with Session(engine) as cleanup:
            cleanup.execute(
                delete(db_models.AutomationJob).where(
                    db_models.AutomationJob.id == job_id
                )
            )
            cleanup.execute(
                delete(db_models.Workspace).where(
                    db_models.Workspace.id == workspace_id
                )
            )
            cleanup.execute(delete(db_models.User).where(db_models.User.id == user_id))
            cleanup.commit()
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
