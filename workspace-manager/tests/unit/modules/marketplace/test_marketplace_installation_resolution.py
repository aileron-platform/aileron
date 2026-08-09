"""Published Marketplace package resolution tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aileron_git_core import GitCommandResult

import app.modules.marketplace.workflows.installation as installation_module
from app.modules.marketplace.workflows.installation import (
    MarketplaceInstallationWorkflow,
)
from app.modules.marketplace.workflows.registry_operations import (
    MarketplaceImportSourceError,
)


def _workflow(tmp_path: Path) -> tuple[MarketplaceInstallationWorkflow, Path]:
    root = tmp_path / "registry"
    (root / ".git").mkdir(parents=True)
    workflow = object.__new__(MarketplaceInstallationWorkflow)
    object.__setattr__(workflow, "_context", SimpleNamespace(db=None))
    workflow._package_reads = Mock()
    workflow._package_reads.get_package_operation_summary.return_value = (
        SimpleNamespace(
            revision="a" * 64,
            lifecycle_status="ready",
            registry_path="codex/plugins/github",
        )
    )
    workflow._get_registry_root = Mock(return_value=root)
    workflow._read_catalog = Mock(
        return_value=SimpleNamespace(
            marketplace_id="private-marketplace",
            publish_branch="main",
        )
    )
    workflow._git_output = Mock(return_value="git@gitlab.example:team/marketplace.git")
    workflow._validate_registry_remote = Mock()
    workflow._codex_manifest_path = Mock(
        return_value=root / "codex/.agents/plugins/marketplace.json"
    )
    return workflow, root


def _result(
    args: tuple[str, ...],
    *,
    returncode: int = 0,
    stdout: str = "",
) -> GitCommandResult:
    return GitCommandResult(
        args=["git", *args],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_resolve_published_package_uses_only_remote_tracking_reads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workflow, root = _workflow(tmp_path)
    commands: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *args: str) -> GitCommandResult:
        commands.append(args)
        if args[0] == "show":
            return _result(
                args,
                stdout=json.dumps(
                    {
                        "name": "private-marketplace",
                        "plugins": [{"name": "github"}],
                    }
                ),
            )
        return _result(args)

    monkeypatch.setattr(installation_module, "git_allow_failure", fake_git)

    resolved = workflow.resolve_published_package_for_install(
        "user-1",
        "codex",
        "github",
        "a" * 64,
    )

    assert resolved.marketplace_id == "private-marketplace"
    assert resolved.remote_url == "git@gitlab.example:team/marketplace.git"
    assert resolved.publish_ref == "main"
    assert {args[0] for args in commands} == {
        "rev-parse",
        "cat-file",
        "diff",
        "ls-files",
        "show",
    }
    assert all(
        command[0] not in {"add", "commit", "push", "rm"} for command in commands
    )
    workflow._git_output.assert_called_once_with(root, ["remote", "get-url", "origin"])


def test_resolve_published_package_rejects_revision_absent_from_remote_tracking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workflow, _root = _workflow(tmp_path)

    def fake_git(_root: Path, *args: str) -> GitCommandResult:
        if args[0] == "diff":
            return _result(args, returncode=1)
        return _result(args)

    monkeypatch.setattr(installation_module, "git_allow_failure", fake_git)

    with pytest.raises(MarketplaceImportSourceError) as exc_info:
        workflow.resolve_published_package_for_install(
            "user-1",
            "codex",
            "github",
            "a" * 64,
        )

    assert exc_info.value.code == "marketplace.install.package_not_published"


def test_old_publish_for_install_operation_is_removed() -> None:
    assert not hasattr(MarketplaceInstallationWorkflow, "publish_package_for_install")


def test_install_runtime_requires_internal_url(tmp_path: Path) -> None:
    workflow, _ = _workflow(tmp_path)
    workspace = SimpleNamespace(
        runtime_status="running",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        runtime_internal_url=None,
    )
    query = Mock()
    query.filter.return_value.first.return_value = workspace
    workflow.db = Mock(query=Mock(return_value=query))

    result = workflow.resolve_install_runtime("workspace-1")

    assert result == {
        "runtimeUrl": None,
        "errorCode": "marketplace.install.runtime_url_missing",
    }


def test_install_runtime_uses_internal_url(tmp_path: Path) -> None:
    workflow, _ = _workflow(tmp_path)
    workspace = SimpleNamespace(
        runtime_status="running",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        runtime_internal_url="http://workspace-runtime:3002/",
    )
    query = Mock()
    query.filter.return_value.first.return_value = workspace
    workflow.db = Mock(query=Mock(return_value=query))

    result = workflow.resolve_install_runtime("workspace-1")

    assert result == {
        "runtimeUrl": "http://workspace-runtime:3002",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "errorCode": None,
    }
