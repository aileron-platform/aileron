from __future__ import annotations

import errno
import os
import tomllib
from pathlib import Path

import pytest

from app.modules.cli_settings.user_scope import materializer as materializer_module
from app.modules.cli_settings.user_scope.materializer import (
    UserCopyCrashPoint,
    UserCopyInjectedCrash,
    UserCopyJournalPhase,
    UserCopyMaterializationError,
    UserCopyMaterializer,
)
from app.modules.cli_settings.user_scope.paths import UserScopePathResolver
from app.modules.cli_settings.user_scope.planner import (
    UserCopyOverwriteApproval,
)

from .fixtures import plan_codex_package, write_full_codex_package, write_text

_OPERATION_ID = "0123456789abcdef0123456789abcdef"


def _materializer(
    tmp_path: Path,
    runtime_home: Path,
    *,
    crash_point: UserCopyCrashPoint | None = None,
) -> UserCopyMaterializer:
    def crash(
        point: UserCopyCrashPoint,
        _target_locator: str | None,
    ) -> None:
        if point is crash_point:
            raise UserCopyInjectedCrash()

    return UserCopyMaterializer(
        operation_state_root=tmp_path / "operations",
        paths=UserScopePathResolver(user_home=runtime_home),
        crash_hook=crash if crash_point is not None else None,
    )


def _single_file_plan(tmp_path: Path) -> tuple[Path, Path, object]:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(package / "AGENTS.md", "# Marketplace instructions\n")
    plan = plan_codex_package(package, runtime_home)
    return package, runtime_home, plan


def _approval(plan: object) -> tuple[UserCopyOverwriteApproval, ...]:
    conflicts = plan.conflicts  # type: ignore[attr-defined]
    return tuple(
        UserCopyOverwriteApproval(
            target_identity=conflict.target_identity,
            expected_revision=conflict.baseline_revision,
        )
        for conflict in conflicts
    )


def test_apply_publish_and_finalize_leave_only_ordinary_user_content(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_full_codex_package(package)
    plan = plan_codex_package(package, runtime_home)
    materializer = _materializer(tmp_path, runtime_home)

    result = materializer.apply(
        plan,
        package,
        operation_id=_OPERATION_ID,
        workspace_id="workspace-1",
    )
    payload = next(
        item.runtime_path
        for item in plan.resources
        if item.resource_type == "dependency-payload"
    )

    assert result.journal_phase is UserCopyJournalPhase.COMPLETED
    assert payload.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
    assert payload.stat().st_mode & 0o777 == 0o700
    config = tomllib.loads(
        (runtime_home / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert config["mcp_servers"]["local"]["command"] == str(payload)

    materializer.mark_published(_OPERATION_ID)
    recovered = materializer.recover(
        plan,
        operation_id=_OPERATION_ID,
    )
    assert recovered.action == "completed"
    assert recovered.published is True

    materializer.finalize(_OPERATION_ID)
    assert not (tmp_path / "operations" / _OPERATION_ID).exists()
    assert payload.is_file()


@pytest.mark.parametrize("source_kind", ["file", "directory"])
def test_rename_noreplace_falls_back_when_nfs_rejects_renameat2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_kind: str,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    if source_kind == "file":
        source.write_text("content", encoding="utf-8")
    else:
        source.mkdir()
        (source / "content.txt").write_text("content", encoding="utf-8")

    monkeypatch.setattr(
        materializer_module,
        "_renameat2_noreplace",
        lambda _source, _target: errno.EINVAL,
    )

    materializer_module._rename_noreplace(source, target)

    assert not source.exists()
    if source_kind == "file":
        assert target.read_text(encoding="utf-8") == "content"
    else:
        assert (target / "content.txt").read_text(encoding="utf-8") == "content"


@pytest.mark.parametrize("target_kind", ["file", "directory"])
def test_nfs_fallback_never_replaces_an_existing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_kind: str,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "incoming.txt").write_text("incoming", encoding="utf-8")
    if target_kind == "file":
        target.write_text("existing", encoding="utf-8")
    else:
        target.mkdir()
        (target / "existing.txt").write_text("existing", encoding="utf-8")

    monkeypatch.setattr(
        materializer_module,
        "_renameat2_noreplace",
        lambda _source, _target: errno.EINVAL,
    )

    with pytest.raises(FileExistsError):
        materializer_module._rename_noreplace(source, target)

    assert (source / "incoming.txt").read_text(encoding="utf-8") == "incoming"
    if target_kind == "file":
        assert target.read_text(encoding="utf-8") == "existing"
    else:
        assert (target / "existing.txt").read_text(encoding="utf-8") == "existing"


@pytest.mark.parametrize(
    "crash_point",
    [
        UserCopyCrashPoint.AFTER_PREPARED,
        UserCopyCrashPoint.AFTER_BACKUP,
        UserCopyCrashPoint.AFTER_TARGET_WRITE_BEFORE_JOURNAL,
        UserCopyCrashPoint.AFTER_VERIFY,
        UserCopyCrashPoint.BEFORE_FINALIZE,
    ],
)
def test_every_pre_release_crash_phase_rolls_back(
    tmp_path: Path,
    crash_point: UserCopyCrashPoint,
) -> None:
    package, runtime_home, plan = _single_file_plan(tmp_path)
    crashing = _materializer(
        tmp_path,
        runtime_home,
        crash_point=crash_point,
    )

    with pytest.raises(UserCopyInjectedCrash):
        crashing.apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
        )

    recovered = _materializer(tmp_path, runtime_home).recover(
        plan,
        operation_id=_OPERATION_ID,
    )

    assert recovered.action == "rolled-back"
    assert recovered.phase is UserCopyJournalPhase.ROLLED_BACK
    assert not (runtime_home / ".codex" / "AGENTS.md").exists()


def test_completed_but_unpublished_transaction_rolls_back(tmp_path: Path) -> None:
    package, runtime_home, plan = _single_file_plan(tmp_path)
    materializer = _materializer(tmp_path, runtime_home)
    materializer.apply(
        plan,
        package,
        operation_id=_OPERATION_ID,
        workspace_id="workspace-1",
    )

    recovered = materializer.recover(
        plan,
        operation_id=_OPERATION_ID,
    )

    assert recovered.action == "rolled-back"
    assert not (runtime_home / ".codex" / "AGENTS.md").exists()


def test_overwrite_preserves_concurrent_edit_without_overwriting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    target = runtime_home / ".codex" / "AGENTS.md"
    write_text(package / "AGENTS.md", "# Incoming\n")
    write_text(target, "# Baseline\n")
    plan = plan_codex_package(package, runtime_home)
    original = materializer_module._rename_noreplace
    raced = False

    def race_before_displacement(source: Path, destination: Path) -> None:
        nonlocal raced
        if not raced:
            raced = True
            target.write_text("# Concurrent edit\n", encoding="utf-8")
        original(source, destination)

    monkeypatch.setattr(
        materializer_module,
        "_rename_noreplace",
        race_before_displacement,
    )

    with pytest.raises(UserCopyMaterializationError) as error:
        _materializer(tmp_path, runtime_home).apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
            overwrite_approvals=_approval(plan),
        )

    assert error.value.code == "marketplace.user_copy.plan_stale"
    assert target.read_text(encoding="utf-8") == "# Concurrent edit\n"
    assert not list(target.parent.glob(".*.pending"))
    assert not list(target.parent.glob(".*.previous"))


def test_absent_target_concurrently_created_with_identical_content_is_not_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, runtime_home, plan = _single_file_plan(tmp_path)
    target = runtime_home / ".codex" / "AGENTS.md"
    original = materializer_module._rename_noreplace
    raced = False

    def race_before_publish(source: Path, destination: Path) -> None:
        nonlocal raced
        if not raced:
            raced = True
            target.write_text(
                "# Marketplace instructions\n",
                encoding="utf-8",
            )
        original(source, destination)

    monkeypatch.setattr(
        materializer_module,
        "_rename_noreplace",
        race_before_publish,
    )

    with pytest.raises(UserCopyMaterializationError) as error:
        _materializer(tmp_path, runtime_home).apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
        )

    assert error.value.code == "marketplace.user_copy.plan_stale"
    assert target.read_text(encoding="utf-8") == "# Marketplace instructions\n"
    assert not list(target.parent.glob(".*.pending"))


def test_concurrent_create_after_displacement_is_preserved_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    target = runtime_home / ".codex" / "AGENTS.md"
    write_text(package / "AGENTS.md", "# Incoming\n")
    write_text(target, "# Baseline\n")
    plan = plan_codex_package(package, runtime_home)
    original = materializer_module._rename_noreplace
    calls = 0

    def race_after_displacement(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            target.write_text("# Concurrent create\n", encoding="utf-8")
        original(source, destination)

    monkeypatch.setattr(
        materializer_module,
        "_rename_noreplace",
        race_after_displacement,
    )

    with pytest.raises(UserCopyMaterializationError) as error:
        _materializer(tmp_path, runtime_home).apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
            overwrite_approvals=_approval(plan),
        )

    assert error.value.code == "marketplace.user_copy.rollback_failed"
    assert target.read_text(encoding="utf-8") == "# Concurrent create\n"
    previous = list(target.parent.glob(".*.previous"))
    assert len(previous) == 1
    assert previous[0].read_text(encoding="utf-8") == "# Baseline\n"


def test_rollback_preserves_target_replaced_after_ownership_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, runtime_home, plan = _single_file_plan(tmp_path)
    target = runtime_home / ".codex" / "AGENTS.md"
    crashing = _materializer(
        tmp_path,
        runtime_home,
        crash_point=UserCopyCrashPoint.AFTER_TARGET_WRITE_BEFORE_JOURNAL,
    )
    with pytest.raises(UserCopyInjectedCrash):
        crashing.apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
        )
    original = UserCopyMaterializer._remove_rollback_capture
    replaced = False

    def replace_before_capture_delete(
        self: UserCopyMaterializer,
        capture: Path,
        resource: object,
        backup: object,
        *,
        expected_post_revision: str | None,
    ) -> None:
        nonlocal replaced
        if not replaced:
            replaced = True
            target.write_text("# Concurrent replacement\n", encoding="utf-8")
        original(
            self,
            capture,
            resource,  # type: ignore[arg-type]
            backup,  # type: ignore[arg-type]
            expected_post_revision=expected_post_revision,
        )

    monkeypatch.setattr(
        UserCopyMaterializer,
        "_remove_rollback_capture",
        replace_before_capture_delete,
    )

    recovered = _materializer(tmp_path, runtime_home).recover(
        plan,
        operation_id=_OPERATION_ID,
    )

    assert recovered.action == "rolled-back"
    assert target.read_text(encoding="utf-8") == "# Concurrent replacement\n"


def test_execute_rejects_fifo_and_parent_symlink_targets(tmp_path: Path) -> None:
    package, runtime_home, plan = _single_file_plan(tmp_path)
    target = runtime_home / ".codex" / "AGENTS.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(target)

    with pytest.raises(UserCopyMaterializationError) as fifo_error:
        _materializer(tmp_path, runtime_home).apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
        )
    assert fifo_error.value.code == "marketplace.user_copy.target_unsafe"

    target.unlink()
    target.parent.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (runtime_home / ".codex").symlink_to(outside, target_is_directory=True)
    with pytest.raises(UserCopyMaterializationError) as symlink_error:
        _materializer(tmp_path, runtime_home).apply(
            plan,
            package,
            operation_id="1123456789abcdef0123456789abcdef",
            workspace_id="workspace-1",
        )
    assert symlink_error.value.code == "marketplace.user_copy.target_unsafe"


def test_recovery_removes_exact_stale_journal_temp_and_rejects_unknown_artifact(
    tmp_path: Path,
) -> None:
    package, runtime_home, plan = _single_file_plan(tmp_path)
    crashing = _materializer(
        tmp_path,
        runtime_home,
        crash_point=UserCopyCrashPoint.AFTER_PREPARED,
    )
    with pytest.raises(UserCopyInjectedCrash):
        crashing.apply(
            plan,
            package,
            operation_id=_OPERATION_ID,
            workspace_id="workspace-1",
        )
    operation_dir = tmp_path / "operations" / _OPERATION_ID
    (operation_dir / ".journal.tmp").write_text("stale", encoding="utf-8")

    recovered = _materializer(tmp_path, runtime_home).recover(
        plan,
        operation_id=_OPERATION_ID,
    )
    assert recovered.action == "rolled-back"
    assert not (operation_dir / ".journal.tmp").exists()

    (operation_dir / "unknown").write_text("invalid", encoding="utf-8")
    with pytest.raises(UserCopyMaterializationError) as error:
        _materializer(tmp_path, runtime_home).recover(
            plan,
            operation_id=_OPERATION_ID,
        )
    assert error.value.code == "marketplace.user_copy.runtime_state_invalid"
