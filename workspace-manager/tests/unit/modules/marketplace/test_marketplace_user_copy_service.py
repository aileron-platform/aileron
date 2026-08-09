"""Focused tests for one-shot Marketplace user-copy orchestration."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from aileron_marketplace_core import (
    build_user_copy_source_snapshot,
    user_copy_source_digest_from_preview,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.modules.marketplace import user_copy as user_copy_service_module
from app.modules.marketplace.models import (
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
)
from app.modules.marketplace.user_copy import (
    MarketplaceUserCopyError,
    MarketplaceUserCopyService,
)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with Session(engine) as session:
        yield session
    engine.dispose()


def _package(root: Path, *, content: str = "# PDF\n") -> Path:
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


def _request() -> MarketplaceUserCopyRequest:
    return MarketplaceUserCopyRequest(
        provider="claude-code",
        packageId="document-skills",
        revision="a" * 64,
        workspaceId="workspace-1",
    )


def test_overwrite_approvals_must_exactly_match_conflict_revisions() -> None:
    base_request = {
        **_request().model_dump(by_alias=True),
        "expectedSourceDigest": "b" * 64,
        "expectedMaterializationDigest": "d" * 64,
    }
    preflight = MarketplaceUserCopyPreflightResult.model_validate(
        {
            "status": "confirmation-required",
            "provider": "claude-code",
            "packageId": "document-skills",
            "workspaceId": "workspace-1",
            "sourceDigest": "b" * 64,
            "profileDigest": "c" * 64,
            "materializationDigest": "d" * 64,
            "resources": [],
            "conflicts": [
                {
                    "resourceType": "skill",
                    "resourceId": "pdf",
                    "sourceLocator": "skills/pdf",
                    "targetLocator": "~/.claude/skills/pdf",
                    "targetIdentity": "claude:skill:pdf",
                    "baselineRevision": "e" * 64,
                    "incomingDigest": "f" * 64,
                    "overwritable": True,
                }
            ],
            "blockingIssues": [],
        }
    )
    exact = {
        "targetIdentity": "claude:skill:pdf",
        "expectedRevision": "e" * 64,
    }

    MarketplaceUserCopyService._validate_overwrite_approvals(
        MarketplaceUserCopyApplyRequest(
            **{**base_request, "overwriteApprovals": [exact]}
        ),
        preflight,
    )
    for approvals in (
        [],
        [exact, exact],
        [
            exact,
            {
                "targetIdentity": "claude:skill:extra",
                "expectedRevision": "1" * 64,
            },
        ],
    ):
        with pytest.raises(MarketplaceUserCopyError) as error:
            MarketplaceUserCopyService._validate_overwrite_approvals(
                MarketplaceUserCopyApplyRequest(
                    **{**base_request, "overwriteApprovals": approvals}
                ),
                preflight,
            )
        assert error.value.code == "marketplace.user_copy.plan_stale"


def test_sparse_snapshot_lock_prevents_mixed_revision_and_releases_before_yield(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _package(tmp_path / "package", content="# Old\n")
    mutation_lock = threading.Lock()
    writer_acquired = threading.Event()
    writer_done = threading.Event()

    class _LockedRegistry:
        revision = "a" * 64
        lock_active = False

        @contextmanager
        def package_source_lock(self, *_args):
            with mutation_lock:
                self.lock_active = True
                try:
                    yield
                finally:
                    self.lock_active = False

        def get_package_operation_summary(self, *_args):
            return SimpleNamespace(
                revision=self.revision,
                lifecycle_status="ready",
            )

        def resolve_package_path(self, *_args):
            return package_root

        def mutate(self) -> None:
            with mutation_lock:
                writer_acquired.set()
                (package_root / "skills" / "pdf" / "SKILL.md").write_text(
                    "# New\n",
                    encoding="utf-8",
                )
                self.revision = "b" * 64
            writer_done.set()

    registry = _LockedRegistry()
    service = MarketplaceUserCopyService(db_session, registry)
    original_materialize = service._materialize_sparse_root
    writer = threading.Thread(target=registry.mutate)

    def materialize_with_concurrent_writer(**kwargs) -> None:
        writer.start()
        assert writer_acquired.wait(0.05) is False
        original_materialize(**kwargs)

    monkeypatch.setattr(
        service,
        "_materialize_sparse_root",
        materialize_with_concurrent_writer,
    )

    with service._sparse_source("user-1", _request()) as source:
        assert registry.lock_active is False
        assert writer_done.wait(1)
        assert (source.root / "skills" / "pdf" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "# Old\n"
        assert (package_root / "skills" / "pdf" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "# New\n"
    writer.join(timeout=1)

    with pytest.raises(MarketplaceUserCopyError) as error:
        with service._sparse_source("user-1", _request()):
            pass
    assert error.value.code == "marketplace.user_copy.revision_conflict"


def test_sparse_snapshot_uses_operation_summary_and_each_core_snapshot_api_once(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _package(tmp_path / "package")
    expected = build_user_copy_source_snapshot("claude-code", package_root)

    class _TargetedRegistry:
        summary_calls = 0

        @contextmanager
        def package_source_lock(self, *_args):
            yield

        def get_package_operation_summary(self, *_args):
            self.summary_calls += 1
            return SimpleNamespace(
                revision="a" * 64,
                lifecycle_status="ready",
            )

        def get_package_detail(self, *_args):
            raise AssertionError("user-copy must not build full package detail")

        def resolve_package_path(self, *_args):
            return package_root

    calls = {"profile": 0, "snapshot": 0}
    original_profile = (
        user_copy_service_module.resolve_user_copy_profile_with_dependency_payloads
    )
    original_snapshot = user_copy_service_module.build_user_copy_source_snapshot

    def resolve_profile(*args, **kwargs):
        calls["profile"] += 1
        return original_profile(*args, **kwargs)

    def build_snapshot(*args, **kwargs):
        calls["snapshot"] += 1
        return original_snapshot(*args, **kwargs)

    monkeypatch.setattr(
        user_copy_service_module,
        "resolve_user_copy_profile_with_dependency_payloads",
        resolve_profile,
    )
    monkeypatch.setattr(
        user_copy_service_module,
        "build_user_copy_source_snapshot",
        build_snapshot,
    )

    registry = _TargetedRegistry()
    service = MarketplaceUserCopyService(db_session, registry)
    with service._sparse_source("user-1", _request()) as source:
        assert source.profile == expected.profile
        assert source.preview.to_wire(exclude_unset=True) == expected.preview
        assert source.package_tree_digest == expected.package_tree_digest
        assert source.source_digest == user_copy_source_digest_from_preview(
            expected.preview
        )

    assert registry.summary_calls == 1
    assert calls == {"profile": 1, "snapshot": 1}


def test_sparse_snapshot_includes_exact_dependency_payload_closure(
    db_session: Session,
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "package"
    manifest = package_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
        {
          "name": "document-skills",
          "mcpServers": {
            "local": {
              "command": "${CLAUDE_PLUGIN_ROOT}/bin/server.js",
              "args": ["${CLAUDE_PLUGIN_ROOT}/assets"]
            }
          }
        }
        """,
        encoding="utf-8",
    )
    server = package_root / "bin" / "server.js"
    server.parent.mkdir(parents=True)
    server.write_text("console.log('ready')\n", encoding="utf-8")
    assets = package_root / "assets"
    assets.mkdir()
    (assets / "schema.json").write_text("{}\n", encoding="utf-8")
    (package_root / "unrelated.txt").write_text("omit\n", encoding="utf-8")

    class _Registry:
        @contextmanager
        def package_source_lock(self, *_args):
            yield

        def get_package_operation_summary(self, *_args):
            return SimpleNamespace(
                revision="a" * 64,
                lifecycle_status="ready",
            )

        def resolve_package_path(self, *_args):
            return package_root

    service = MarketplaceUserCopyService(db_session, _Registry())
    expected_server_digest = sha256()
    for component in (b"file", b"600", server.read_bytes()):
        expected_server_digest.update(len(component).to_bytes(8, "big"))
        expected_server_digest.update(component)

    with service._sparse_source("user-1", _request()) as source:
        assert (source.root / "bin" / "server.js").read_text(
            encoding="utf-8"
        ) == "console.log('ready')\n"
        assert (source.root / "assets" / "schema.json").is_file()
        assert not (source.root / "unrelated.txt").exists()
        preview = source.preview.to_wire(exclude_unset=True)
        assert preview["dependencyPayloads"] == [
            {
                "sourceLocator": "assets",
                "sourceKind": "directory",
                "contentDigest": preview["dependencyPayloads"][0]["contentDigest"],
            },
            {
                "sourceLocator": "bin/server.js",
                "sourceKind": "file",
                "contentDigest": expected_server_digest.hexdigest(),
            },
        ]
        assert all(
            resource["dependencyPayloadProjectable"] is True
            for resource in preview["resources"]
        )
        assert source.source_digest == source.preview.source_digest


def test_copy_activity_contains_only_terminal_audit_fields(
    db_session: Session,
) -> None:
    calls: list[dict[str, object]] = []

    class _RecordingRegistry:
        def record_activity(self, _user_id: str, **kwargs) -> None:
            calls.append(kwargs)

    request = MarketplaceUserCopyApplyRequest(
        **{
            **_request().model_dump(by_alias=True),
            "expectedSourceDigest": "b" * 64,
            "expectedMaterializationDigest": "c" * 64,
            "overwriteApprovals": [],
        }
    )
    MarketplaceUserCopyService(db_session, _RecordingRegistry())._record_activity(
        user_id="user-1",
        request=request,
        operation_id="1" * 32,
        status="succeeded",
        error_code=None,
    )

    assert calls == [
        {
            "action": "copy",
            "status": "succeeded",
            "provider": "claude-code",
            "package_id": "document-skills",
            "operation_id": "1" * 32,
            "workspace_id": "workspace-1",
            "error_code": None,
        }
    ]
