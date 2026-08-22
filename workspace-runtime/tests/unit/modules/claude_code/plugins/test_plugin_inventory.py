"""Claude provider discovery cache tests."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.modules.claude_code.plugins import loader as loader_module
from app.modules.claude_code.plugins import plugin_inventory as inventory_module
from app.modules.claude_code.plugins import catalog as service_module
from app.modules.claude_code.plugins.loader import PluginComponentsLoader
from app.modules.claude_code.plugins.plugin_inventory import (
    build_claude_plugin_inventory_snapshot,
)
from app.modules.claude_code.plugins.catalog import ClaudePluginsService


def test_plugin_list_success_is_shared_until_manual_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = Event()
    release = Event()
    calls: list[tuple[object, ...]] = []
    completed = SimpleNamespace(
        returncode=0,
        stdout='[{"id":"demo@registry"}]',
        stderr="",
    )

    def fake_run(*args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append(args)
        entered.set()
        assert release.wait(timeout=2)
        return completed

    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)
    monkeypatch.setattr(service_module, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(loader_module, "workspace_root", lambda: tmp_path)
    service = ClaudePluginsService(settings_service=Mock())
    loader = PluginComponentsLoader(Mock())

    with ThreadPoolExecutor(max_workers=2) as executor:
        service_future = executor.submit(service._plugin_rows, "workspace-1")
        assert entered.wait(timeout=2)
        loader_future = executor.submit(loader._plugin_rows)
        release.set()
        assert service_future.result() == [{"id": "demo@registry"}]
        assert loader_future.result() == [{"id": "demo@registry"}]

    assert len(calls) == 1
    assert service._plugin_rows("workspace-1") == [{"id": "demo@registry"}]
    assert len(calls) == 1
    inventory_module.clear_claude_plugin_inventory_cache(tmp_path)
    assert service._plugin_rows("workspace-1") == [{"id": "demo@registry"}]
    assert len(calls) == 2


def test_plugin_list_concurrent_failure_keeps_caller_error_contracts_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = Event()
    release = Event()
    calls = 0

    def fake_run(*_args: object, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=2)
        raise FileNotFoundError("claude")

    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)
    monkeypatch.setattr(service_module, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(loader_module, "workspace_root", lambda: tmp_path)
    service = ClaudePluginsService(settings_service=Mock())
    loader = PluginComponentsLoader(Mock())

    with ThreadPoolExecutor(max_workers=2) as executor:
        service_future = executor.submit(service._plugin_rows, "workspace-1")
        assert entered.wait(timeout=2)
        loader_future = executor.submit(loader._plugin_rows)
        release.set()
        with pytest.raises(HTTPException) as service_error:
            service_future.result()
        with pytest.raises(RuntimeError, match="inventory is unavailable"):
            loader_future.result()

    assert service_error.value.status_code == 503
    assert service_error.value.detail == {"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"}
    assert calls == 1

    with pytest.raises(RuntimeError, match="inventory is unavailable"):
        loader._plugin_rows()
    assert calls == 2


def test_plugin_list_timeout_exception_is_not_translated_by_single_flight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        inventory_module.subprocess,
        "run",
        Mock(side_effect=subprocess.TimeoutExpired("claude", 10)),
    )
    monkeypatch.setattr(service_module, "workspace_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as error:
        ClaudePluginsService(settings_service=Mock())._plugin_rows("workspace-1")

    assert error.value.status_code == 504
    assert error.value.detail == {"error": "CLAUDE_PLUGIN_CLI_TIMEOUT"}


@pytest.mark.parametrize(
    ("completed", "expected_error"),
    [
        (
            SimpleNamespace(
                returncode=1,
                stdout="unknown command",
                stderr="",
            ),
            "CLAUDE_PLUGIN_CLI_UNSUPPORTED",
        ),
        (
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="provider failed",
            ),
            "CLAUDE_PLUGIN_CLI_FAILED",
        ),
        (
            SimpleNamespace(
                returncode=0,
                stdout="{",
                stderr="",
            ),
            "CLAUDE_PLUGIN_CLI_INVALID_JSON",
        ),
    ],
)
def test_service_keeps_provider_cli_error_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    completed: SimpleNamespace,
    expected_error: str,
) -> None:
    monkeypatch.setattr(
        inventory_module.subprocess,
        "run",
        Mock(return_value=completed),
    )
    monkeypatch.setattr(service_module, "workspace_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as error:
        ClaudePluginsService(settings_service=Mock())._plugin_rows("workspace-1")

    assert error.value.status_code == 502
    assert error.value.detail == {"error": expected_error}


def test_internal_inventory_keeps_provider_reported_symlink_root(
    tmp_path: Path,
) -> None:
    installed_root = tmp_path / "installed"
    manifest = installed_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"name":"demo"}', encoding="utf-8")
    reported_root = tmp_path / "reported-root"
    reported_root.symlink_to(installed_root, target_is_directory=True)

    snapshot = build_claude_plugin_inventory_snapshot(
        [
            {
                "id": "demo@registry",
                "scope": "user",
                "enabled": True,
                "installPath": str(reported_root),
            }
        ]
    )

    assert snapshot.enabled_roots() == (reported_root,)


def test_internal_inventory_rejects_nonstandard_path_fallback(
    tmp_path: Path,
) -> None:
    installed_root = tmp_path / "installed"
    installed_root.mkdir()

    snapshot = build_claude_plugin_inventory_snapshot(
        [
            {
                "id": "demo@registry",
                "scope": "user",
                "enabled": True,
                "path": str(installed_root),
            }
        ]
    )

    assert snapshot.resource_projections == ()
    with pytest.raises(ValueError, match="inventory is incomplete"):
        snapshot.enabled_roots()


def test_internal_inventory_rejects_missing_selected_root_when_disabled() -> None:
    snapshot = build_claude_plugin_inventory_snapshot(
        [
            {
                "id": "demo@registry",
                "scope": "user",
                "enabled": False,
                "installPath": None,
            }
        ]
    )

    with pytest.raises(ValueError, match="inventory is incomplete"):
        snapshot.enabled_roots()


def test_internal_inventory_validates_effectively_disabled_selected_root(
    tmp_path: Path,
) -> None:
    user_root = tmp_path / "user-install"
    user_root.mkdir()
    project_root = tmp_path / "project-install"
    manifest = project_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"demo","commands":"../outside"}',
        encoding="utf-8",
    )

    snapshot = build_claude_plugin_inventory_snapshot(
        [
            {
                "id": "demo@registry",
                "scope": "user",
                "enabled": True,
                "installPath": str(user_root),
            },
            {
                "id": "demo@registry",
                "scope": "project",
                "enabled": False,
                "installPath": str(project_root),
            },
        ]
    )

    projection = snapshot.resource_projection("demo@registry")
    assert projection is not None
    assert projection.install_root == project_root
    assert projection.resources.diagnostics[0].code == "source-reference-invalid"
    with pytest.raises(ValueError, match="inventory is incomplete"):
        snapshot.enabled_roots()
