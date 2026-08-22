"""Focused tests for terminal Marketplace activity persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db import models as db_models
from app.modules.marketplace.activity_repository import (
    MarketplaceActivityRepository,
)
from app.modules.marketplace.models import MarketplacePluginCliCommand

NOW = datetime(2026, 7, 26, tzinfo=timezone.utc)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_append_persists_only_terminal_audit_fields(db_session: Session) -> None:
    repository = MarketplaceActivityRepository(db_session)

    row = repository.append(
        actor_user_id="user-1",
        action="install",
        status="failed",
        package_format="agent-plugin/1.0.0",
        target_client="codex",
        package_id="github",
        operation_id="operation-1",
        workspace_id=None,
        marketplace_id="private-marketplace",
        source_id="codex:private-marketplace:repository",
        error_code="marketplace.install.cli_failed",
        now=NOW,
    )

    assert row.status == "failed"
    assert row.operation_id == "operation-1"
    assert row.marketplace_id == "private-marketplace"
    assert row.source_id == "codex:private-marketplace:repository"
    assert row.package_format == "agent-plugin/1.0.0"
    assert row.target_client == "codex"
    assert not hasattr(row, "installation_id")
    assert not hasattr(row, "resolved_commit")
    assert not hasattr(row, "content_digest")


def test_append_persists_workspace_snapshot_and_command_children(
    db_session: Session,
) -> None:
    repository = MarketplaceActivityRepository(db_session)
    row = repository.append(
        actor_user_id="user-1",
        action="install",
        status="succeeded",
        target_client="codex",
        package_id="github",
        operation_id="operation-1",
        workspace_id="workspace-1",
        commands=[
            MarketplacePluginCliCommand(
                sequence=0,
                stage="plugin-install",
                argvDisplay="codex plugin add github@team",
                exitCode=0,
                startedAt=NOW,
                endedAt=NOW,
                stdout="installed",
                stderr=None,
                stdoutOriginalByteCount=9,
                stderrOriginalByteCount=0,
                truncated=False,
            )
        ],
        now=NOW,
    )
    db_session.flush()

    command = db_session.query(db_models.MarketplaceCommandResult).one()
    assert row.workspace_id_snapshot == "workspace-1"
    assert command.activity_id == row.id
    assert command.argv_display == "codex plugin add github@team"


def test_orphaned_workspace_audit_is_hidden_from_actor_but_visible_to_admin(
    db_session: Session,
) -> None:
    repository = MarketplaceActivityRepository(db_session)
    row = repository.append(
        actor_user_id="user-1",
        action="install",
        status="succeeded",
        workspace_id="deleted-workspace",
        now=NOW,
    )
    row.workspace_id = None
    db_session.add(
        db_models.User(
            id="admin-1",
            username="admin",
            platform_role="admin",
        )
    )
    db_session.flush()

    assert repository.get_detail(user_id="user-1", activity_id=row.id) is None
    assert repository.get_detail(user_id="admin-1", activity_id=row.id) is not None
    rows, total = repository.list(user_id="user-1", page=1, page_size=50)
    assert rows == []
    assert total == 0


def test_list_returns_actor_owned_registry_audits(db_session: Session) -> None:
    repository = MarketplaceActivityRepository(db_session)
    for actor_user_id, package_id in (
        ("user-1", "github"),
        ("user-2", "frontend-design"),
    ):
        repository.append(
            actor_user_id=actor_user_id,
            action="import",
            status="succeeded",
            package_format=(
                "codex-native" if package_id == "github" else "claude-native"
            ),
            package_id=package_id,
            now=NOW,
        )
    db_session.flush()

    rows, total = repository.list(
        user_id="user-1",
        page=1,
        page_size=50,
    )

    assert total == 1
    assert [row.package_id for row in rows] == ["github"]


def test_list_successful_source_installations_is_visible_and_distinct(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.modules.marketplace.activity_repository.visible_workspace_ids",
        lambda user_id: ["workspace-1"] if user_id == "user-1" else [],
    )
    repository = MarketplaceActivityRepository(db_session)
    for workspace_id, status in (
        ("workspace-1", "succeeded"),
        ("workspace-1", "succeeded"),
        ("workspace-2", "succeeded"),
        ("workspace-1", "failed"),
    ):
        repository.append(
            actor_user_id="user-1",
            action="install",
            status=status,
            package_format="agent-plugin/1.0.0",
            target_client="codex",
            package_id="superpowers",
            workspace_id=workspace_id,
            marketplace_id="openai-curated",
            source_id="codex:openai-curated:repository-a",
            now=NOW,
        )
    repository.append(
        actor_user_id="user-1",
        action="install",
        status="succeeded",
        package_format="agent-plugin/1.0.0",
        target_client="codex",
        package_id="removed-from-current-catalog",
        workspace_id="workspace-1",
        marketplace_id="openai-curated",
        source_id="codex:openai-curated:repository-b",
        now=NOW,
    )
    db_session.flush()

    rows = repository.list_successful_source_installations(
        user_id="user-1",
        source_id="codex:openai-curated:repository-a",
    )

    assert rows == [("workspace-1", "codex", "superpowers")]
