"""Focused tests for terminal Marketplace activity persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.modules.marketplace.activity_repository import (
    MarketplaceActivityRepository,
)

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
        provider="codex",
        package_id="github",
        operation_id="operation-1",
        workspace_id=None,
        marketplace_id="private-marketplace",
        error_code="marketplace.install.cli_failed",
        now=NOW,
    )

    assert row.status == "failed"
    assert row.operation_id == "operation-1"
    assert row.marketplace_id == "private-marketplace"
    assert not hasattr(row, "installation_id")
    assert not hasattr(row, "resolved_commit")
    assert not hasattr(row, "content_digest")


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
            provider="codex" if package_id == "github" else "claude-code",
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
