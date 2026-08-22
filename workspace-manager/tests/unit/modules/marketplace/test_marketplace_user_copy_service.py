"""Focused tests for package-format-aware Marketplace User Copy orchestration."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.marketplace.models import (
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
)
from app.modules.marketplace.user_copy import (
    MarketplaceUserCopyError,
    MarketplaceUserCopyService,
)


def _service(registry: object) -> MarketplaceUserCopyService:
    return MarketplaceUserCopyService(object(), registry)  # type: ignore[arg-type]


def _request(
    *,
    package_format: str = "claude-native",
    target_client: str = "claude-code",
    catalog_plugin_id: str = "managed/document-skills",
) -> MarketplaceUserCopyRequest:
    return MarketplaceUserCopyRequest(
        packageFormat=package_format,
        targetClient=target_client,
        catalogPluginId=catalog_plugin_id,
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
    )


def _apply_request(**updates: Any) -> MarketplaceUserCopyApplyRequest:
    return MarketplaceUserCopyApplyRequest.model_validate(
        {
            **_request().model_dump(by_alias=True),
            "expectedProfileDigest": "c" * 64,
            "expectedSourceDigest": "b" * 64,
            "expectedProjectionDigest": "c" * 64,
            "expectedMaterializationDigest": "d" * 64,
            "acceptPartialCopy": False,
            "overwriteApprovals": [],
            **updates,
        }
    )


def _summary(**updates: Any) -> SimpleNamespace:
    values = {
        "revision": "a" * 64,
        "lifecycle_status": "ready",
        "package_format": "claude-native",
        "user_copy_target_client": "claude-code",
        "catalog_plugin_id": "managed/document-skills",
    }
    values.update(updates)
    return SimpleNamespace(**values)


def _claude_package(root: Path, *, content: str = "# PDF\n") -> Path:
    manifest = root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"document-skills","skills":["./skills/pdf"]}',
        encoding="utf-8",
    )
    skill = root / "skills" / "pdf"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(content, encoding="utf-8")
    return root


def _codex_package_with_unsupported_app(root: Path) -> Path:
    manifest = root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"portable-tools","apps":"./.app.json",'
        '"skills":"./skills/"}',
        encoding="utf-8",
    )
    (root / ".app.json").write_text(
        '{"apps":{"demo":{"id":"connector"}}}',
        encoding="utf-8",
    )
    skill = root / "skills" / "review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Review\n", encoding="utf-8")
    return root


def test_overwrite_approvals_must_exactly_match_conflict_revisions() -> None:
    preflight = MarketplaceUserCopyPreflightResult.model_validate(
        {
            "status": "confirmation-required",
            "packageFormat": "claude-native",
            "targetClient": "claude-code",
            "catalogPluginId": "managed/document-skills",
            "releaseRevision": "a" * 64,
            "workspaceId": "workspace-1",
            "sourceDigest": "b" * 64,
            "profileDigest": "c" * 64,
            "projectionDigest": "d" * 64,
            "materializationDigest": "e" * 64,
            "resources": [],
            "skippedResources": [],
            "conflicts": [
                {
                    "resourceType": "skill",
                    "resourceId": "pdf",
                    "sourceLocator": "skills/pdf",
                    "targetLocator": "$CLAUDE_CONFIG_DIR/skills/pdf",
                    "targetIdentity": "claude-code:skill:pdf",
                    "baselineRevision": "f" * 64,
                    "incomingDigest": "1" * 64,
                    "overwritable": True,
                }
            ],
            "blockingIssues": [],
        }
    )
    exact = {
        "targetIdentity": "claude-code:skill:pdf",
        "expectedRevision": "f" * 64,
    }

    MarketplaceUserCopyService._validate_overwrite_approvals(
        _apply_request(overwriteApprovals=[exact]), preflight
    )
    for approvals in ([], [exact, exact]):
        with pytest.raises(MarketplaceUserCopyError) as error:
            MarketplaceUserCopyService._validate_overwrite_approvals(
                _apply_request(overwriteApprovals=approvals), preflight
            )
        assert error.value.code == "marketplace.user_copy.plan_stale"


def test_sparse_source_is_read_under_catalog_identity_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _claude_package(tmp_path / "package", content="# Old\n")
    mutation_lock = threading.Lock()
    writer_started = threading.Event()
    writer_done = threading.Event()

    class _Registry:
        revision = "a" * 64
        lock_active = False

        @contextmanager
        def open_user_copy_source(
            self,
            _user_id: str,
            catalog_id: str,
            package_format: str,
            target_client: str,
        ):
            assert catalog_id == "managed/document-skills"
            assert package_format == "claude-native"
            assert target_client == "claude-code"
            with mutation_lock:
                self.lock_active = True
                try:
                    yield _summary(revision=self.revision), package_root
                finally:
                    self.lock_active = False

        def mutate(self) -> None:
            with mutation_lock:
                writer_started.set()
                (package_root / "skills" / "pdf" / "SKILL.md").write_text(
                    "# New\n", encoding="utf-8"
                )
                self.revision = "b" * 64
            writer_done.set()

    registry = _Registry()
    service = _service(registry)
    original = service._materialize_sparse_root
    writer = threading.Thread(target=registry.mutate)

    def materialize(**kwargs: Any) -> None:
        writer.start()
        assert writer_started.wait(0.05) is False
        original(**kwargs)

    monkeypatch.setattr(service, "_materialize_sparse_root", materialize)
    with service._sparse_source("user-1", _request()) as source:
        assert registry.lock_active is False
        assert writer_done.wait(1)
        assert (source.root / "skills" / "pdf" / "SKILL.md").read_text() == "# Old\n"
    writer.join(timeout=1)


def test_sparse_source_rejects_catalog_format_or_target_mismatch(
    tmp_path: Path,
) -> None:
    package_root = _claude_package(tmp_path / "package")

    class _Registry:
        @contextmanager
        def open_user_copy_source(self, *_args: Any):
            yield _summary(package_format="codex-native"), package_root

    with pytest.raises(MarketplaceUserCopyError) as error:
        with _service(_Registry())._sparse_source("user-1", _request()):
            pass
    assert error.value.code == "marketplace.user_copy.package_identity_mismatch"


def test_agent_plugin_sparse_source_includes_exact_dependency_closure(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"portable-tools"}',
        encoding="utf-8",
    )
    (package_root / "bin").mkdir()
    (package_root / "bin" / "server.js").write_text("server\n", encoding="utf-8")
    (package_root / "mcp.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'mcp.schema.json","mcpServers":{"server":{"type":"stdio",'
        '"command":"node","args":["${PLUGIN_ROOT}/bin/server.js"]}}}',
        encoding="utf-8",
    )
    request = _request(
        package_format="agent-plugin/1.0.0",
        target_client="codex",
        catalog_plugin_id="managed/portable-tools",
    )

    class _Registry:
        @contextmanager
        def open_user_copy_source(self, *_args: Any):
            yield _summary(
                package_format="agent-plugin/1.0.0",
                user_copy_target_client="codex",
                catalog_plugin_id="managed/portable-tools",
            ), package_root

    with _service(_Registry())._sparse_source("user-1", request) as source:
        assert (source.root / "plugin.json").is_file()
        assert (source.root / "mcp.json").is_file()
        assert (source.root / "bin" / "server.js").is_file()
        assert source.profile.package_format.value == "agent-plugin/1.0.0"


def test_codex_sparse_source_preserves_diagnostic_sources(
    tmp_path: Path,
) -> None:
    package_root = _codex_package_with_unsupported_app(tmp_path / "package")
    request = _request(
        package_format="codex-native",
        target_client="codex",
        catalog_plugin_id="managed/portable-tools",
    )

    class _Registry:
        @contextmanager
        def open_user_copy_source(self, *_args: Any):
            yield _summary(
                package_format="codex-native",
                user_copy_target_client="codex",
                catalog_plugin_id="managed/portable-tools",
            ), package_root

    with _service(_Registry())._sparse_source("user-1", request) as source:
        assert (source.root / ".app.json").is_file()
        assert [item.canonical_dict() for item in source.profile.diagnostics] == [
            {
                "code": "unsupported-resource",
                "sourceLocator": ".codex-plugin/plugin.json#/apps",
                "resourceType": "apps",
            }
        ]


def test_copy_activity_uses_catalog_and_target_identity_without_target_client() -> None:
    calls: list[dict[str, object]] = []

    class _Registry:
        def record_activity(self, _user_id: str, **kwargs: Any) -> None:
            calls.append(kwargs)

    _service(_Registry())._record_activity(
        user_id="user-1",
        request=_apply_request(),
        operation_id="1" * 32,
        status="succeeded",
        error_code=None,
    )

    assert calls == [
        {
            "action": "copy",
            "status": "succeeded",
            "package_format": "claude-native",
            "target_client": "claude-code",
            "package_id": "managed/document-skills",
            "operation_id": "1" * 32,
            "workspace_id": "workspace-1",
            "error_code": None,
            "catalog_plugin_id": "managed/document-skills",
            "release_revision": "a" * 64,
            "profile_digest": None,
            "projection_digest": None,
            "materialization_digest": None,
            "projected_count": None,
            "skipped_count": None,
            "conflict_count": None,
            "created_count": None,
            "merged_count": None,
            "unchanged_count": None,
            "overwritten_count": None,
            "target_locators": (),
            "diagnostic_codes": (),
        }
    ]


def test_preflight_result_must_match_the_selected_runtime_instance() -> None:
    request = _request()
    source = SimpleNamespace(
        source_digest="b" * 64,
        profile=SimpleNamespace(profile_version=2, profile_digest="c" * 64),
    )
    result = SimpleNamespace(
        package_format="claude-native",
        target_client="claude-code",
        catalog_plugin_id="managed/document-skills",
        release_revision="a" * 64,
        workspace_id="workspace-1",
        runtime_instance_id="22222222-2222-4222-8222-222222222222",
        source_digest="b" * 64,
        profile_version=2,
        profile_digest="c" * 64,
    )

    with pytest.raises(MarketplaceUserCopyError) as error:
        MarketplaceUserCopyService._verify_preflight(
            result,
            request=request,
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            source=source,
        )

    assert error.value.code == "marketplace.user_copy.runtime_contract_invalid"


def test_ready_plan_rejects_partial_copy_confirmation() -> None:
    preflight = MarketplaceUserCopyPreflightResult.model_validate(
        {
            "status": "ready",
            "packageFormat": "claude-native",
            "targetClient": "claude-code",
            "catalogPluginId": "managed/document-skills",
            "releaseRevision": "a" * 64,
            "workspaceId": "workspace-1",
            "sourceDigest": "b" * 64,
            "profileDigest": "c" * 64,
            "projectionDigest": "d" * 64,
            "materializationDigest": "e" * 64,
            "resources": [],
            "skippedResources": [],
            "conflicts": [],
            "blockingIssues": [],
        }
    )

    with pytest.raises(MarketplaceUserCopyError) as error:
        MarketplaceUserCopyService._validate_confirmations(
            _apply_request(acceptPartialCopy=True),
            preflight,
        )

    assert error.value.code == "marketplace.user_copy.plan_stale"
