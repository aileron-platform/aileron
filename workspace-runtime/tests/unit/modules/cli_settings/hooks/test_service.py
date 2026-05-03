from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.modules.cli_settings.hooks.config import CliHookScope, CliHookToolConfig, HookTool
from app.modules.cli_settings.hooks.models import (
    CliHookImportMode,
    CliHookImportRequest,
    CliHookScopeDocument,
    CliHookScopeUpsertRequest,
    HookAction,
    HookActionType,
    HookRule,
)
from app.modules.cli_settings.hooks.service import CliHookService
from app.modules.cli_settings.mcp.config_strategies import JsonConfigStrategy


def _make_config(tmp_path: Path) -> CliHookToolConfig:
    return CliHookToolConfig(
        tool=HookTool.GEMINI,
        project_file=".gemini/settings.json",
        user_file_path=tmp_path / "user" / "settings.json",
        hooks_key="hooks",
        strategy=JsonConfigStrategy(),
        supported_scopes=[CliHookScope.PROJECT, CliHookScope.USER],
    )


def _sample_rule(command: str = "echo hi") -> HookRule:
    return HookRule(
        matcher="*",
        hooks=[HookAction(type=HookActionType.COMMAND, command=command, timeout=10)],
    )


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliHookService:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr("app.modules.cli_settings.hooks.service.get_workspace_path", lambda: str(workspace))
    return CliHookService(_make_config(tmp_path))


def test_list_get_update_and_delete_scope(service: CliHookService) -> None:
    scopes = service.list_scopes("ws-1")
    assert len(scopes.scopes) == 2
    assert all(scope.hooks == {} for scope in scopes.scopes)

    updated = service.update_scope(
        "ws-1",
        CliHookScope.PROJECT,
        CliHookScopeUpsertRequest(
            hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]}
        ),
    )
    assert updated.scope == CliHookScope.PROJECT
    assert updated.hooks["PreToolUse"][0].hooks[0].command == "echo hi"

    fetched = service.get_scope("ws-1", CliHookScope.PROJECT)
    assert fetched.hooks["PreToolUse"][0].matcher == "*"

    deleted = service.delete_scope("ws-1", CliHookScope.PROJECT)
    assert deleted.deleted is True
    assert service.get_scope("ws-1", CliHookScope.PROJECT).hooks == {}


def test_gemini_hook_metadata_round_trip_persistence(service: CliHookService) -> None:
    updated = service.update_scope(
        "ws-1",
        CliHookScope.PROJECT,
        CliHookScopeUpsertRequest(
            hooks={
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "name": "security-check",
                                "description": "Check commands before execution",
                                "command": "echo hi",
                                "timeout": 10,
                            }
                        ],
                    }
                ]
            }
        ),
    )

    action = updated.hooks["PreToolUse"][0].hooks[0]
    assert action.name == "security-check"
    assert action.description == "Check commands before execution"

    fetched_action = service.get_scope("ws-1", CliHookScope.PROJECT).hooks["PreToolUse"][0].hooks[0]
    assert fetched_action.name == "security-check"
    assert fetched_action.description == "Check commands before execution"

    file_path = service._scope_file("ws-1", CliHookScope.PROJECT)
    stored_action = json.loads(file_path.read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["hooks"][0]
    assert stored_action["name"] == "security-check"
    assert stored_action["description"] == "Check commands before execution"


def test_gemini_hook_metadata_is_optional(service: CliHookService) -> None:
    updated = service.update_scope(
        "ws-1",
        CliHookScope.PROJECT,
        CliHookScopeUpsertRequest(
            hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]}
        ),
    )

    action = updated.hooks["PreToolUse"][0].hooks[0]
    assert action.name is None
    assert action.description is None


def test_delete_scope_handles_existing_file_without_hooks(service: CliHookService) -> None:
    file_path = service._scope_file("ws-1", CliHookScope.USER)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps({"other": True}), encoding="utf-8")

    result = service.delete_scope("ws-1", CliHookScope.USER)

    assert result.deleted is True
    assert file_path.exists() is True
    assert json.loads(file_path.read_text(encoding="utf-8")) == {"other": True}


def test_export_and_import_scopes_merge_and_replace(service: CliHookService) -> None:
    service.update_scope(
        "ws-1",
        CliHookScope.USER,
        CliHookScopeUpsertRequest(hooks={"PreToolUse": [_sample_rule("echo old")]}),
    )

    exported = service.export_scopes("ws-1", [CliHookScope.USER])
    assert len(exported.scopes) == 1
    assert exported.scopes[0].hooks["PreToolUse"][0].hooks[0].command == "echo old"

    merge_result = service.import_scopes(
        "ws-1",
        CliHookImportRequest(
            mode=CliHookImportMode.MERGE,
            scopes=[
                CliHookScopeDocument(
                    scope=CliHookScope.USER,
                    hooks={"PostToolUse": [_sample_rule("echo merged")]},
                )
            ],
        ),
    )
    merged_scope = service.get_scope("ws-1", CliHookScope.USER)
    assert merge_result.updated == 1
    assert "PreToolUse" in merged_scope.hooks
    assert "PostToolUse" in merged_scope.hooks

    replace_result = service.import_scopes(
        "ws-1",
        CliHookImportRequest(
            mode=CliHookImportMode.REPLACE,
            scopes=[
                CliHookScopeDocument(
                    scope=CliHookScope.USER,
                    hooks={"Stop": [_sample_rule("echo replaced")]},
                )
            ],
        ),
    )
    replaced_scope = service.get_scope("ws-1", CliHookScope.USER)
    assert replace_result.updated == 1
    assert list(replaced_scope.hooks) == ["Stop"]


def test_import_merge_skips_when_no_change(service: CliHookService) -> None:
    doc = CliHookScopeDocument(scope=CliHookScope.USER, hooks={"PreToolUse": [_sample_rule("echo same")]})
    service.import_scopes("ws-1", CliHookImportRequest(mode=CliHookImportMode.REPLACE, scopes=[doc]))

    result = service.import_scopes(
        "ws-1",
        CliHookImportRequest(mode=CliHookImportMode.MERGE, scopes=[doc]),
    )

    assert result.skipped == 1
    assert result.imported == 0
    assert result.updated == 0


def test_validate_scope_and_load_scope_document_defensive_paths(
    service: CliHookService,
) -> None:
    bad_config = CliHookToolConfig(
        tool=HookTool.GEMINI,
        project_file=".gemini/settings.json",
        user_file_path=service._config.user_file_path,
        hooks_key="hooks",
        strategy=service._config.strategy,
        supported_scopes=[CliHookScope.USER],
    )
    bad_service = CliHookService(bad_config)

    with pytest.raises(HTTPException) as exc_info:
        bad_service.get_scope("ws-1", CliHookScope.PROJECT)
    assert exc_info.value.status_code == 400

    file_path = service._scope_file("ws-1", CliHookScope.USER)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps({"hooks": ["invalid"]}), encoding="utf-8")
    assert service.get_scope("ws-1", CliHookScope.USER).hooks == {}
