"""Workspace agentic tools schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON

from app.db import models
from app.modules.workspace.models import WorkspaceCreateRequest, WorkspaceUpdateRequest


def test_workspace_agentic_tools_column_is_json_list() -> None:
    column = models.Workspace.__table__.columns["agentic_tools"]

    assert isinstance(column.type, JSON)
    assert column.default is not None
    assert callable(column.default.arg)


def test_workspace_agentic_tools_reject_empty_list() -> None:
    with pytest.raises(ValidationError) as exc:
        WorkspaceCreateRequest(name="Invalid", runtime="python", agenticTools=[])

    assert "agenticTools" in str(exc.value)


def test_workspace_agentic_tools_reject_unknown_tool() -> None:
    with pytest.raises(ValidationError) as exc:
        WorkspaceCreateRequest(
            name="Invalid", runtime="python", agenticTools=["unknown"]
        )

    assert "agenticTools" in str(exc.value)


def test_workspace_agentic_tools_reject_duplicates() -> None:
    with pytest.raises(ValidationError) as exc:
        WorkspaceCreateRequest(
            name="Invalid",
            runtime="python",
            agenticTools=["codex", "codex"],
        )

    assert "agenticTools" in str(exc.value)


def test_workspace_agentic_tools_use_canonical_order() -> None:
    payload = WorkspaceCreateRequest(
        name="Tools",
        runtime="python",
        agenticTools=["opencode", "claude-code", "codex"],
    )

    assert payload.agentic_tools == ["claude-code", "codex", "opencode"]


def test_workspace_update_accepts_agentic_tools() -> None:
    payload = WorkspaceUpdateRequest(
        agenticTools=["opencode", "claude-code", "codex"],
    )

    assert "agentic_tools" in payload.model_fields_set
    assert payload.agentic_tools == ["claude-code", "codex", "opencode"]


def test_workspace_update_rejects_empty_agentic_tools() -> None:
    with pytest.raises(ValidationError) as exc:
        WorkspaceUpdateRequest(agenticTools=[])

    assert "agenticTools" in str(exc.value)
