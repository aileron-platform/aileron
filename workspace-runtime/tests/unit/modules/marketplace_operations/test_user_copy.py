from __future__ import annotations

import os
import stat
import warnings
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from aileron_marketplace_core import (
    UserCopyApplyMetadataContract,
    UserCopyPreflightRequestContract,
    build_user_copy_profile_preview,
    package_tree_digest,
    resolve_user_copy_profile,
    user_copy_source_digest_from_preview,
)

from app.config.settings import Settings
from app.modules.cli_settings.user_scope.materializer import (
    UserCopyCrashPoint,
    UserCopyInjectedCrash,
    UserCopyMaterializer,
)
from app.modules.cli_settings.user_scope.planner import UserCopyInventory
from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import MarketplaceProviderGate
from app.modules.marketplace_operations.state import MarketplaceMutationStore
from app.modules.marketplace_operations.user_copy import (
    MarketplaceUserCopyService,
)

_RUNTIME_ID = "11111111-1111-4111-8111-111111111111"
_REVISION = "b" * 64
_OPERATION_ID = "a" * 32
_CONTENT = b"# Marketplace instructions\n"


class _CompleteInventoryProvider:
    def inventory(
        self,
        provider: str,
        *,
        profile: Any = None,
    ) -> UserCopyInventory:
        assert profile is not None
        assert profile.provider == provider
        return UserCopyInventory(complete=True)


@dataclass(frozen=True)
class _UserCopyCase:
    settings: Settings
    store: MarketplaceMutationStore
    service: MarketplaceUserCopyService
    inventory: _CompleteInventoryProvider
    metadata: UserCopyApplyMetadataContract
    bundle: bytes
    target: Path
    state_root: Path
    gate: MarketplaceProviderGate


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        ENV="test",
        AILERON_WORKSPACE_ID="workspace-1",
        AILERON_WORKSPACE_PATH=str(tmp_path / "workspace"),
        MARKETPLACE_OPERATION_JOURNAL_DIR=str(tmp_path / "state"),
    )


def _archive_package(package_root: Path) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for source in sorted(
            path for path in package_root.rglob("*") if path.is_file()
        ):
            relative = source.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(relative)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if os.access(source, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


def _build_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> _UserCopyCase:
    user_home = tmp_path / "home"
    user_home.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(user_home))

    package_root = tmp_path / "package"
    package_root.mkdir(mode=0o700)
    (package_root / "AGENTS.md").write_bytes(_CONTENT)
    (package_root / "AGENTS.md").chmod(0o644)
    profile = resolve_user_copy_profile("codex", package_root)
    preview = build_user_copy_profile_preview(package_root, profile)
    source_digest = user_copy_source_digest_from_preview(preview)

    settings = _settings(tmp_path)
    state_root = Path(settings.MARKETPLACE_OPERATION_JOURNAL_DIR)
    store = MarketplaceMutationStore(state_root)
    gate = MarketplaceProviderGate(store)
    inventory = _CompleteInventoryProvider()
    service = MarketplaceUserCopyService(
        settings=settings,
        mutation_store=store,
        inventory_provider=inventory,  # type: ignore[arg-type]
        gate=gate,
    )
    monkeypatch.setattr(service, "_clear_provider_caches", lambda _provider: None)

    preflight = service.preflight(
        UserCopyPreflightRequestContract.model_validate(
            {
                "provider": "codex",
                "packageId": "demo",
                "revision": _REVISION,
                "workspaceId": settings.AILERON_WORKSPACE_ID,
                "runtimeInstanceId": settings.AILERON_RUNTIME_INSTANCE_ID,
                "expectedSourceDigest": source_digest,
                "expectedProfileVersion": profile.profile_version,
                "expectedProfileDigest": profile.profile_digest,
                "userCopyProfilePreview": preview,
            }
        )
    )
    assert preflight.status == "ready"

    bundle = _archive_package(package_root)
    metadata = UserCopyApplyMetadataContract.model_validate(
        {
            "operationId": _OPERATION_ID,
            "provider": "codex",
            "packageId": "demo",
            "revision": _REVISION,
            "workspaceId": settings.AILERON_WORKSPACE_ID,
            "runtimeInstanceId": settings.AILERON_RUNTIME_INSTANCE_ID,
            "providerStateRootId": store.provider_state_root_id,
            "expectedSourceDigest": source_digest,
            "expectedArchiveDigest": sha256(bundle).hexdigest(),
            "expectedPackageTreeDigest": package_tree_digest(package_root),
            "expectedProfileVersion": profile.profile_version,
            "expectedProfileDigest": profile.profile_digest,
            "expectedMaterializationDigest": preflight.materialization_digest,
            "overwriteApprovals": [],
        }
    )
    return _UserCopyCase(
        settings=settings,
        store=store,
        service=service,
        inventory=inventory,
        metadata=metadata,
        bundle=bundle,
        target=user_home / ".codex" / "AGENTS.md",
        state_root=state_root,
        gate=gate,
    )


def _recovery_service(
    case: _UserCopyCase,
    monkeypatch: pytest.MonkeyPatch,
) -> MarketplaceUserCopyService:
    service = MarketplaceUserCopyService(
        settings=case.settings,
        mutation_store=case.store,
        inventory_provider=case.inventory,  # type: ignore[arg-type]
        gate=case.gate,
    )
    monkeypatch.setattr(service, "_clear_provider_caches", lambda _provider: None)
    return service


def _assert_operation_state_removed(case: _UserCopyCase) -> None:
    assert not (case.state_root / "user-copy-snapshots" / _OPERATION_ID).exists()
    assert not (case.state_root / "user-copy-transactions" / _OPERATION_ID).exists()
    assert not (
        case.state_root / "user-copy-recovery" / f"{_OPERATION_ID}.json"
    ).exists()
    assert not (case.state_root / "provider-resource-state.json").exists()


def test_success_publishes_once_and_removes_all_transient_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)

    result = case.service.apply(case.metadata, case.bundle)

    assert case.target.read_bytes() == _CONTENT
    assert result.created_count == 1
    assert result.merged_count == 0
    assert result.unchanged_count == 0
    assert result.overwritten_count == 0
    assert case.gate.generation("codex") == 1
    _assert_operation_state_removed(case)


@pytest.mark.parametrize("provider", ["claude-code", "codex"])
def test_user_copy_clears_all_affected_user_scope_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        "app.modules.marketplace_operations.user_copy.clear_agent_settings_cache",
        lambda **values: calls.append(values),
    )
    service = MarketplaceUserCopyService(settings=_settings(tmp_path))

    service._clear_provider_caches(provider)

    assert calls == [
        {
            "provider": provider,
            "workspace_id": "workspace-1",
            "scope": "user",
        }
    ]


def test_failure_before_generation_rolls_back_and_removes_transient_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)

    def fail_cache_clear(_provider: str) -> None:
        raise RuntimeError("cache clear failed")

    monkeypatch.setattr(case.service, "_clear_provider_caches", fail_cache_clear)

    with pytest.raises(MarketplaceOperationError):
        case.service.apply(case.metadata, case.bundle)

    assert not case.target.exists()
    assert case.gate.generation("codex") == 0
    _assert_operation_state_removed(case)


def test_publication_failure_rolls_back_and_retry_applies_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    original_mark_published = UserCopyMaterializer.mark_published

    def fail_mark_published(
        self: UserCopyMaterializer,
        operation_id: str,
    ) -> None:
        _ = (self, operation_id)
        raise RuntimeError("publication journal unavailable")

    monkeypatch.setattr(
        UserCopyMaterializer,
        "mark_published",
        fail_mark_published,
    )
    with pytest.raises(MarketplaceOperationError):
        case.service.apply(case.metadata, case.bundle)

    assert not case.target.exists()
    assert case.gate.generation("codex") == 1
    _assert_operation_state_removed(case)

    monkeypatch.setattr(
        UserCopyMaterializer,
        "mark_published",
        original_mark_published,
    )
    result = case.service.apply(case.metadata, case.bundle)

    assert result.created_count == 1
    assert case.target.read_bytes() == _CONTENT
    assert case.gate.generation("codex") == 2
    _assert_operation_state_removed(case)


def test_exact_retry_after_release_only_finishes_transient_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    original_remove = case.service._snapshot_stager.remove
    remove_calls = 0

    def fail_first_remove(operation_id: str) -> None:
        nonlocal remove_calls
        remove_calls += 1
        if remove_calls == 1:
            raise RuntimeError("snapshot cleanup unavailable")
        original_remove(operation_id)

    monkeypatch.setattr(
        case.service._snapshot_stager,
        "remove",
        fail_first_remove,
    )
    with pytest.raises(MarketplaceOperationError):
        case.service.apply(case.metadata, case.bundle)

    inode_before_retry = case.target.stat().st_ino
    assert case.gate.generation("codex") == 1

    monkeypatch.setattr(
        case.service._snapshot_stager,
        "remove",
        original_remove,
    )
    result = case.service.apply(case.metadata, case.bundle)

    assert result.created_count == 1
    assert case.target.stat().st_ino == inode_before_retry
    assert case.gate.generation("codex") == 1
    _assert_operation_state_removed(case)


@pytest.mark.parametrize(
    "crash_point",
    [
        UserCopyCrashPoint.AFTER_PREPARED,
        UserCopyCrashPoint.AFTER_BACKUP,
        UserCopyCrashPoint.AFTER_TARGET_WRITE_BEFORE_JOURNAL,
        UserCopyCrashPoint.AFTER_TARGET_APPLY,
        UserCopyCrashPoint.BEFORE_VERIFY,
        UserCopyCrashPoint.AFTER_VERIFY,
        UserCopyCrashPoint.BEFORE_FINALIZE,
    ],
)
def test_startup_rolls_back_every_unpublished_transaction_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_point: UserCopyCrashPoint,
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    original_apply = UserCopyMaterializer.apply

    def crashing_apply(
        self: UserCopyMaterializer,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        def crash(point: UserCopyCrashPoint, _target_locator: str | None) -> None:
            if point is crash_point:
                raise UserCopyInjectedCrash()

        self._crash_hook = crash
        return original_apply(self, *args, **kwargs)

    monkeypatch.setattr(UserCopyMaterializer, "apply", crashing_apply)
    with pytest.raises(UserCopyInjectedCrash):
        case.service.apply(case.metadata, case.bundle)
    assert (case.state_root / "user-copy-transactions" / _OPERATION_ID).is_dir()

    monkeypatch.setattr(UserCopyMaterializer, "apply", original_apply)
    _recovery_service(case, monkeypatch).recover_incomplete_operations()

    assert not case.target.exists()
    assert case.gate.generation("codex") == 0
    _assert_operation_state_removed(case)


def test_startup_rolls_back_when_publication_marker_was_not_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    original = UserCopyMaterializer.mark_published

    def crash_before_publication_marker(
        self: UserCopyMaterializer,
        operation_id: str,
    ) -> None:
        _ = (self, operation_id)
        raise UserCopyInjectedCrash()

    monkeypatch.setattr(
        UserCopyMaterializer,
        "mark_published",
        crash_before_publication_marker,
    )
    with pytest.raises(UserCopyInjectedCrash):
        case.service.apply(case.metadata, case.bundle)
    monkeypatch.setattr(UserCopyMaterializer, "mark_published", original)

    assert case.gate.generation("codex") == 1
    _recovery_service(case, monkeypatch).recover_incomplete_operations()

    assert not case.target.exists()
    assert case.gate.generation("codex") == 1
    _assert_operation_state_removed(case)


def test_startup_completes_published_transaction_without_rewriting_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _build_case(tmp_path, monkeypatch)
    original_remove = case.service._snapshot_stager.remove

    def crash_after_publication(_operation_id: str) -> None:
        raise UserCopyInjectedCrash()

    monkeypatch.setattr(
        case.service._snapshot_stager,
        "remove",
        crash_after_publication,
    )
    with pytest.raises(UserCopyInjectedCrash):
        case.service.apply(case.metadata, case.bundle)
    monkeypatch.setattr(
        case.service._snapshot_stager,
        "remove",
        original_remove,
    )

    inode_before_recovery = case.target.stat().st_ino
    _recovery_service(case, monkeypatch).recover_incomplete_operations()

    assert case.target.read_bytes() == _CONTENT
    assert case.target.stat().st_ino == inode_before_recovery
    assert case.gate.generation("codex") == 1
    _assert_operation_state_removed(case)


def test_startup_cleans_exact_stale_recovery_temp(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    recovery_root = (
        Path(settings.MARKETPLACE_OPERATION_JOURNAL_DIR) / "user-copy-recovery"
    )
    recovery_root.mkdir(parents=True, mode=0o700)
    stale = recovery_root / f".{_OPERATION_ID}.json.{'0' * 16}.tmp"
    stale.write_text("partial", encoding="utf-8")

    MarketplaceUserCopyService(
        settings=settings,
        inventory_provider=_CompleteInventoryProvider(),  # type: ignore[arg-type]
    ).recover_incomplete_operations()

    assert tuple(recovery_root.iterdir()) == ()


@pytest.mark.parametrize("artifact_kind", ["unknown", "symlink"])
def test_startup_rejects_unknown_or_symlink_recovery_artifact(
    tmp_path: Path,
    artifact_kind: str,
) -> None:
    settings = _settings(tmp_path)
    recovery_root = (
        Path(settings.MARKETPLACE_OPERATION_JOURNAL_DIR) / "user-copy-recovery"
    )
    recovery_root.mkdir(parents=True, mode=0o700)
    artifact = recovery_root / "unexpected"
    if artifact_kind == "unknown":
        artifact.write_text("unexpected", encoding="utf-8")
    else:
        target = tmp_path / "external"
        target.write_text("external", encoding="utf-8")
        artifact.symlink_to(target)

    with pytest.raises(MarketplaceOperationError) as exc_info:
        MarketplaceUserCopyService(
            settings=settings,
            inventory_provider=_CompleteInventoryProvider(),  # type: ignore[arg-type]
        ).recover_incomplete_operations()

    assert exc_info.value.code == "marketplace.user_copy.runtime_state_invalid"
