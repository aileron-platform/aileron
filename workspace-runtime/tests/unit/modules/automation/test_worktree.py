from __future__ import annotations

import errno
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aileron_git_core import OperationKind, OperationManager

from app.modules.automation.worktree import (
    AutomationWorktreeError,
    AutomationWorktreeService,
)
from app.modules.version_control.cache import GitCacheInvalidator
from app.modules.version_control.git_operations import GitService
from app.modules.version_control.working_tree_operations import WorkingTreeOperations

WORKSPACE_ID = "ws-1"


def _git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _git_path(repo: Path, name: str) -> Path:
    raw_path = _git(repo, "rev-parse", "--git-path", name).stdout.strip()
    path = Path(raw_path)
    return path if path.is_absolute() else repo / path


@pytest.fixture
def primary_repo(tmp_path: Path) -> Path:
    repo = tmp_path / WORKSPACE_ID
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Automation Test")
    _git(repo, "config", "user.email", "automation@example.test")
    (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    return repo


def _service(
    tmp_path: Path,
    *,
    worktree_subdir: str = ".worktrees",
    operation_manager: OperationManager | None = None,
    disk_threshold: float = 99.0,
) -> tuple[GitService, AutomationWorktreeService]:
    working_tree_operations = (
        WorkingTreeOperations(operation_manager, GitCacheInvalidator(None))
        if operation_manager is not None
        else None
    )
    git_service = GitService(
        base_path=tmp_path,
        worktree_subdir=worktree_subdir,
        working_tree_operations=working_tree_operations,
    )
    return git_service, AutomationWorktreeService(
        git_service=git_service,
        workspace_id=WORKSPACE_ID,
        disk_threshold=disk_threshold,
    )


async def _assert_error(
    awaitable: object,
    error_code: str,
) -> AutomationWorktreeError:
    with pytest.raises(AutomationWorktreeError) as exc_info:
        await awaitable  # type: ignore[misc]
    assert exc_info.value.error_code == error_code
    return exc_info.value


@pytest.mark.asyncio
async def test_creates_deterministic_branch_and_registered_worktree(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    git_service, service = _service(tmp_path)

    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    assert context.branch == "automation/job-1"
    assert context.context_id == "worktree:automation--job-1"
    assert context.path == primary_repo / ".worktrees" / "automation" / "job-1"
    assert (
        _git(context.path, "branch", "--show-current").stdout.strip() == context.branch
    )
    assert (
        git_service._utils.resolve_context_path(  # noqa: SLF001
            WORKSPACE_ID, context.context_id
        )
        == context.path.resolve()
    )


@pytest.mark.asyncio
async def test_workspace_preflight_accepts_repository_with_initial_commit(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _, service = _service(tmp_path)

    await service.validate_workspace()


@pytest.mark.asyncio
async def test_workspace_preflight_rejects_plain_directory(tmp_path: Path) -> None:
    (tmp_path / WORKSPACE_ID).mkdir()
    _, service = _service(tmp_path)

    await _assert_error(
        service.validate_workspace(),
        "workspace_git_repository_required",
    )


@pytest.mark.asyncio
async def test_workspace_preflight_rejects_repository_without_commit(
    tmp_path: Path,
) -> None:
    repo = tmp_path / WORKSPACE_ID
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _, service = _service(tmp_path)

    await _assert_error(
        service.validate_workspace(),
        "workspace_git_initial_commit_required",
    )


@pytest.mark.asyncio
async def test_reuses_matching_branch_and_registration(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _, service = _service(tmp_path)
    first = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    second = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    assert second == first
    assert (
        _git(primary_repo, "worktree", "list", "--porcelain").stdout.count(
            f"worktree {first.path}"
        )
        == 1
    )


@pytest.mark.asyncio
async def test_mounts_existing_deterministic_branch(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _git(primary_repo, "branch", "automation/job-1", "HEAD")
    _, service = _service(tmp_path)

    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    assert context.path.exists()
    assert (
        _git(context.path, "branch", "--show-current").stdout.strip() == context.branch
    )


@pytest.mark.asyncio
async def test_restart_converges_branch_only_partial_state(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _git(primary_repo, "branch", "automation/job-1", "HEAD")
    _, restarted_service = _service(tmp_path)

    context = await restarted_service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    assert context.path.is_dir()
    assert (
        _git(context.path, "rev-parse", "HEAD").stdout
        == _git(primary_repo, "rev-parse", "HEAD").stdout
    )


@pytest.mark.asyncio
async def test_custom_worktree_subdir_resolves_nested_context(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    git_service, service = _service(tmp_path, worktree_subdir="worktree")

    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    assert context.path == primary_repo / "worktree" / "automation" / "job-1"
    assert git_service.managed_worktree_root(WORKSPACE_ID) == primary_repo / "worktree"
    assert (
        git_service._utils.resolve_context_path(  # noqa: SLF001
            WORKSPACE_ID, context.context_id
        )
        == context.path.resolve()
    )


@pytest.mark.asyncio
async def test_rejects_non_deterministic_snapshot(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _, service = _service(tmp_path)

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="other/path"),
        "worktree_conflict",
    )

    assert not (primary_repo / ".worktrees").exists()


@pytest.mark.asyncio
async def test_rejects_branch_checked_out_in_another_worktree(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    branch = "automation/job-1"
    _git(primary_repo, "branch", branch, "HEAD")
    _git(primary_repo, "worktree", "add", str(tmp_path / "elsewhere"), branch)
    _, service = _service(tmp_path)

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key=branch),
        "worktree_conflict",
    )


@pytest.mark.asyncio
async def test_rejects_unregistered_target_path_content(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    target = primary_repo / ".worktrees" / "automation" / "job-1"
    target.mkdir(parents=True)
    (target / "user-file.txt").write_text("keep\n", encoding="utf-8")
    _, service = _service(tmp_path)

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
        "worktree_conflict",
    )
    assert (target / "user-file.txt").read_text(encoding="utf-8") == "keep\n"


@pytest.mark.asyncio
async def test_rejects_target_registration_for_different_branch(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    target = primary_repo / ".worktrees" / "automation" / "job-1"
    _git(primary_repo, "branch", "other-branch", "HEAD")
    _git(primary_repo, "worktree", "add", str(target), "other-branch")
    _, service = _service(tmp_path)

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
        "worktree_conflict",
    )


@pytest.mark.asyncio
async def test_dirty_staged_and_committed_state_survives_later_executions(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _, service = _service(tmp_path)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    (context.path / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    (context.path / "committed.txt").write_text("committed\n", encoding="utf-8")
    _git(context.path, "add", "committed.txt")
    _git(context.path, "commit", "-m", "automation state")
    (context.path / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(context.path, "add", "staged.txt")
    expected_head = _git(context.path, "rev-parse", "HEAD").stdout.strip()

    _, restarted_service = _service(tmp_path)
    reused = await restarted_service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    await restarted_service.preflight(reused)

    assert _git(reused.path, "rev-parse", "HEAD").stdout.strip() == expected_head
    status = _git(reused.path, "status", "--porcelain").stdout
    assert "?? dirty.txt" in status
    assert "A  staged.txt" in status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "marker",
    [
        "MERGE_HEAD",
        "rebase-merge",
        "rebase-apply",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "BISECT_LOG",
    ],
)
async def test_preflight_rejects_incomplete_git_operations(
    tmp_path: Path,
    primary_repo: Path,
    marker: str,
) -> None:
    _, service = _service(tmp_path)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    marker_path = _git_path(context.path, marker)
    if marker.startswith("rebase-"):
        marker_path.mkdir(parents=True)
    else:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("operation\n", encoding="utf-8")

    await _assert_error(service.preflight(context), "worktree_operation_in_progress")
    assert marker_path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lock_name",
    [
        "index.lock",
        "HEAD.lock",
        "config.lock",
        "packed-refs.lock",
        "shallow.lock",
        "refs/heads/automation/job-1.lock",
    ],
)
async def test_preflight_rejects_git_locks_without_deleting_them(
    tmp_path: Path,
    primary_repo: Path,
    lock_name: str,
) -> None:
    _, service = _service(tmp_path)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    lock_path = _git_path(context.path, lock_name)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("locked\n", encoding="utf-8")

    await _assert_error(service.preflight(context), "worktree_locked")

    assert lock_path.read_text(encoding="utf-8") == "locked\n"


@pytest.mark.asyncio
async def test_platform_operation_collision_returns_stable_lock_error(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    manager = OperationManager()
    _, service = _service(tmp_path, operation_manager=manager)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    key = f"workspace:{WORKSPACE_ID}:context:{context.context_id}"

    with manager.acquire(key, OperationKind.WORKING_TREE, operation_name="user-op"):
        await _assert_error(service.preflight(context), "worktree_locked")


@pytest.mark.asyncio
async def test_disk_threshold_prevents_branch_or_worktree_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    monkeypatch.setattr(
        "app.modules.automation.worktree.shutil.disk_usage",
        Mock(return_value=shutil._ntuple_diskusage(total=100, used=95, free=5)),
    )
    _, service = _service(tmp_path, disk_threshold=90.0)

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
        "worktree_storage_limit",
    )

    assert (
        _git(
            primary_repo,
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/automation/job-1",
            check=False,
        ).returncode
        != 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_errno", [errno.ENOSPC, errno.EDQUOT])
async def test_storage_os_errors_return_stable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    primary_repo: Path,
    storage_errno: int,
) -> None:
    _, service = _service(tmp_path)
    original_run_git = __import__(
        "app.modules.automation.worktree", fromlist=["run_git"]
    ).run_git

    def fail_worktree_add(repo: Path, *args: str):
        if args[:2] == ("worktree", "add"):
            raise OSError(storage_errno, "storage unavailable")
        return original_run_git(repo, *args)

    monkeypatch.setattr("app.modules.automation.worktree.run_git", fail_worktree_add)

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
        "worktree_storage_limit",
    )


@pytest.mark.asyncio
async def test_service_never_calls_destructive_git_service_methods(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    git_service, service = _service(tmp_path)
    destructive = {
        name: Mock()
        for name in (
            "commit",
            "reset",
            "abort",
            "remove",
            "destroy_worktree",
            "force_unlock",
        )
    }
    for name, method in destructive.items():
        setattr(git_service, name, method)

    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    await service.preflight(context)

    for method in destructive.values():
        method.assert_not_called()


@pytest.mark.asyncio
async def test_reuse_rejects_registration_whose_branch_ref_was_deleted(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _, service = _service(tmp_path)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    _git(primary_repo, "update-ref", "-d", "refs/heads/automation/job-1")
    assert (
        _git(
            primary_repo,
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/automation/job-1",
            check=False,
        ).returncode
        != 0
    )
    assert context.path.exists()

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
        "worktree_conflict",
    )


@pytest.mark.asyncio
async def test_ensure_collides_with_production_target_context_operation(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    manager = OperationManager()
    _, service = _service(tmp_path, operation_manager=manager)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    key = f"workspace:{WORKSPACE_ID}:context:{context.context_id}"
    started = threading.Event()
    release = threading.Event()

    def target_operation() -> None:
        with manager.acquire(
            key,
            OperationKind.WORKING_TREE,
            operation_name="branch.switch",
        ):
            started.set()
            assert release.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(target_operation)
        assert started.wait(timeout=5)
        try:
            await _assert_error(
                service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
                "worktree_locked",
            )
        finally:
            release.set()
            future.result(timeout=5)


@pytest.mark.asyncio
async def test_ensure_acquires_primary_then_target_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    manager = OperationManager()
    _, service = _service(tmp_path, operation_manager=manager)
    acquired_keys: list[str] = []
    original_acquire = manager.acquire

    def recording_acquire(key: str, *args, **kwargs):
        acquired_keys.append(key)
        return original_acquire(key, *args, **kwargs)

    monkeypatch.setattr(manager, "acquire", recording_acquire)

    await service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1")

    assert acquired_keys == [
        f"workspace:{WORKSPACE_ID}:context:primary",
        f"workspace:{WORKSPACE_ID}:context:worktree:automation--job-1",
    ]


@pytest.mark.asyncio
async def test_reuse_rejects_non_operation_detached_worktree(
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    _, service = _service(tmp_path)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    _git(context.path, "checkout", "--detach")

    await _assert_error(
        service.ensure_for_job(job_id="job-1", worktree_key="automation/job-1"),
        "worktree_conflict",
    )


@pytest.mark.asyncio
async def test_service_never_runs_destructive_git_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    primary_repo: Path,
) -> None:
    from app.modules.automation import worktree as worktree_module

    commands: list[tuple[str, ...]] = []
    original_run_git = worktree_module.run_git

    def recording_run_git(repo: Path, *args: str):
        commands.append(args)
        return original_run_git(repo, *args)

    monkeypatch.setattr(worktree_module, "run_git", recording_run_git)
    _, service = _service(tmp_path)

    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    await service.preflight(context)

    forbidden = {
        ("commit",),
        ("reset",),
        ("merge", "--abort"),
        ("rebase", "--abort"),
        ("cherry-pick", "--abort"),
        ("revert", "--abort"),
        ("worktree", "remove"),
    }
    assert not any(
        command[: len(prefix)] == prefix for command in commands for prefix in forbidden
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    ["merge", "rebase", "cherry-pick", "revert", "bisect"],
)
async def test_preflight_rejects_real_incomplete_git_operations(
    tmp_path: Path,
    primary_repo: Path,
    operation: str,
) -> None:
    _, service = _service(tmp_path)
    context = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )

    if operation == "bisect":
        (context.path / "bisect.txt").write_text("bad\n", encoding="utf-8")
        _git(context.path, "add", "bisect.txt")
        _git(context.path, "commit", "-m", "bad")
        _git(context.path, "bisect", "start", "HEAD", "HEAD~1")
    elif operation == "revert":
        (context.path / "tracked.txt").write_text("first\n", encoding="utf-8")
        _git(context.path, "commit", "-am", "first")
        first_commit = _git(context.path, "rev-parse", "HEAD").stdout.strip()
        (context.path / "tracked.txt").write_text("later\n", encoding="utf-8")
        _git(context.path, "commit", "-am", "later")
        assert _git(context.path, "revert", first_commit, check=False).returncode != 0
    else:
        _git(primary_repo, "checkout", "-b", f"source-{operation}")
        (primary_repo / "tracked.txt").write_text("source\n", encoding="utf-8")
        _git(primary_repo, "commit", "-am", "source")
        source_commit = _git(primary_repo, "rev-parse", "HEAD").stdout.strip()
        (context.path / "tracked.txt").write_text("automation\n", encoding="utf-8")
        _git(context.path, "commit", "-am", "automation")
        if operation == "merge":
            result = _git(context.path, "merge", f"source-{operation}", check=False)
        elif operation == "rebase":
            result = _git(context.path, "rebase", f"source-{operation}", check=False)
        else:
            result = _git(context.path, "cherry-pick", source_commit, check=False)
        assert result.returncode != 0

    reused = await service.ensure_for_job(
        job_id="job-1", worktree_key="automation/job-1"
    )
    assert reused == context
    await _assert_error(service.preflight(reused), "worktree_operation_in_progress")


def test_automation_provider_reuses_cached_git_service_working_tree_operations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.modules.automation import dependencies

    manager = OperationManager()
    working_tree_operations = WorkingTreeOperations(
        manager,
        GitCacheInvalidator(None),
    )
    git_service = GitService(
        base_path=tmp_path,
        working_tree_operations=working_tree_operations,
    )
    monkeypatch.setattr(dependencies, "get_git_service", lambda: git_service)
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(AILERON_WORKSPACE_ID=WORKSPACE_ID, DISK_THRESHOLD=90.0),
    )
    dependencies.get_automation_worktree_service.cache_clear()

    first = dependencies.get_automation_worktree_service()
    second = dependencies.get_automation_worktree_service()

    assert first is second
    assert first._git_service is git_service  # noqa: SLF001
    assert (
        git_service._working_tree_operations is working_tree_operations  # noqa: SLF001
    )
