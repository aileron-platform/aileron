"""Managed Marketplace package resolution tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.modules.marketplace.workflows.installation import (
    MarketplaceInstallationWorkflow,
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
            registry_path="codex/plugins/codex-native/github",
            package_format="codex-native",
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


def test_resolve_managed_package_uses_registry_branch_without_remote_preflight(
    tmp_path: Path,
) -> None:
    workflow, root = _workflow(tmp_path)
    workflow._git_output.side_effect = [
        "git@gitlab.example:team/marketplace.git",
        "develop",
    ]

    resolved = workflow.resolve_managed_package_for_install(
        "user-1",
        "codex",
        "codex-native",
        "github",
        "1.2.3",
    )

    assert resolved.marketplace_id == "private-marketplace"
    assert resolved.remote_url == "git@gitlab.example:team/marketplace.git"
    assert resolved.registry_ref == "develop"
    assert [item.args for item in workflow._git_output.call_args_list] == [
        (root, ["remote", "get-url", "origin"]),
        (root, ["branch", "--show-current"]),
    ]


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
