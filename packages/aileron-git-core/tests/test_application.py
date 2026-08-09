from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import threading
import time

from aileron_git_core import (
    ActorContext,
    BranchCreateAndSwitch,
    BranchDeleteLocal,
    BranchListQuery,
    BranchPublish,
    BranchRenameLocal,
    BranchSwitch,
    BlobQuery,
    ChangesListQuery,
    CommitCreate,
    CommitFilesQuery,
    CommitRevert,
    ConflictAbort,
    ConflictMarkResolved,
    DiffQuery,
    DiscardChanges,
    HistoryListQuery,
    LfsPatternsQuery,
    LfsPatternsUpdate,
    LfsSnapshotConvert,
    LfsSnapshotPreview,
    RemoteFetch,
    RemotePullFastForward,
    RemotePush,
    RemoteSettingsQuery,
    RemoteSettingsUpdate,
    NumstatQuery,
    OperationCancel,
    OperationForceUnlock,
    LockScopeKeys,
    RepositoryStatusQuery,
    RepositoryTarget,
    RepositoryClone,
    RepositoryInitialize,
    StageAll,
    StagePaths,
    UnstageAll,
    VersionControlError,
    VersionControlApplication,
    VersionControlOperation,
)
from aileron_git_core import lfs as lfs_module
from aileron_git_core.command_runner import GitCommandResult
import pytest


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def init_repo(path: Path) -> Path:
    path.mkdir()
    run_git(path, "init", "-b", "main")
    run_git(path, "config", "user.name", "Tester")
    run_git(path, "config", "user.email", "tester@example.test")
    (path / "README.md").write_text("initial\n", encoding="utf-8")
    run_git(path, "add", "README.md")
    run_git(path, "commit", "-m", "initial")
    return path


def target(repo: Path) -> RepositoryTarget:
    return RepositoryTarget(
        root=repo,
        lock_scope_keys=LockScopeKeys("repository:test", "repository:test:primary"),
    )


def test_application_reads_repository_status_from_git_truth(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    status = VersionControlApplication().read(target(repo), RepositoryStatusQuery())

    assert status.is_initialized is True
    assert status.current_branch == "main"
    assert status.detached_head is False
    assert status.head_sha == run_git(repo, "rev-parse", "HEAD")
    assert status.has_origin is False
    assert status.staged_total == 0
    assert status.unstaged_total == 1
    assert status.untracked_total == 1
    assert status.conflict_total == 0


def test_application_lists_local_and_remote_branches_with_upstream_metadata(
    tmp_path: Path,
) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repo = init_repo(tmp_path / "repo")
    run_git(repo, "remote", "add", "origin", str(remote))
    run_git(repo, "push", "-u", "origin", "main")
    run_git(repo, "branch", "feature")
    run_git(repo, "branch", "--track", "tracking", "origin/main")

    result = VersionControlApplication().read(target(repo), BranchListQuery())

    local = {branch.name: branch for branch in result.branches if branch.kind == "local"}
    remote_branches = {
        branch.name: branch for branch in result.branches if branch.kind == "remote"
    }
    assert local["main"].is_current is True
    assert local["main"].upstream == "origin/main"
    assert local["main"].ahead == 0
    assert local["main"].behind == 0
    assert local["feature"].upstream is None
    assert remote_branches["origin/main"].capabilities.switch.allowed is False
    assert remote_branches["origin/main"].capabilities.switch.disabled_reason_key == (
        "versionControl.branch.remoteTrackingRequired"
    )


def test_application_lists_unborn_current_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")

    result = VersionControlApplication().read(target(repo), BranchListQuery())

    assert len(result.branches) == 1
    branch = result.branches[0]
    assert branch.name == "main"
    assert branch.kind == "local"
    assert branch.is_current is True
    assert branch.capabilities.switch.allowed is False
    assert branch.capabilities.rename.allowed is True
    assert branch.capabilities.delete.allowed is False


def test_branch_commands_create_switch_rename_and_safely_delete(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    application = VersionControlApplication()
    repository_target = target(repo)

    application.execute(
        repository_target,
        BranchCreateAndSwitch(name="feature", start_point="HEAD"),
    )
    assert run_git(repo, "branch", "--show-current") == "feature"

    application.execute(
        repository_target,
        BranchRenameLocal(old_name="feature", new_name="renamed"),
    )
    assert run_git(repo, "branch", "--show-current") == "renamed"

    application.execute(repository_target, BranchSwitch(name="main"))
    application.execute(repository_target, BranchDeleteLocal(name="renamed"))
    assert "renamed" not in run_git(repo, "branch", "--format=%(refname:short)")


def test_branch_transition_rejects_dirty_repository_without_auto_stash(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    run_git(repo, "branch", "feature")
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(VersionControlError) as raised:
        VersionControlApplication().execute(target(repo), BranchSwitch(name="feature"))

    assert raised.value.error_code == "repository_dirty"
    assert run_git(repo, "branch", "--show-current") == "main"
    assert (repo / "README.md").read_text(encoding="utf-8") == "dirty\n"


def test_safe_delete_rejects_unmerged_branch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    run_git(repo, "switch", "-c", "unmerged")
    (repo / "unique.txt").write_text("unique\n", encoding="utf-8")
    run_git(repo, "add", "unique.txt")
    run_git(repo, "commit", "-m", "unique")
    run_git(repo, "switch", "main")

    with pytest.raises(VersionControlError) as raised:
        VersionControlApplication().execute(
            target(repo), BranchDeleteLocal(name="unmerged")
        )

    assert raised.value.error_code == "branch_unmerged"
    assert "unmerged" in run_git(repo, "branch", "--format=%(refname:short)")


def test_publish_sets_upstream_without_force(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repo = init_repo(tmp_path / "repo")
    run_git(repo, "remote", "add", "origin", str(remote))

    VersionControlApplication().execute(target(repo), BranchPublish())

    assert run_git(repo, "rev-parse", "--abbrev-ref", "@{upstream}") == "origin/main"
    assert run_git(repo, "ls-remote", "--heads", "origin", "main")


def test_fetch_pull_and_push_use_safe_shared_semantics(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    source = init_repo(tmp_path / "source")
    run_git(source, "remote", "add", "origin", str(remote))
    run_git(source, "push", "-u", "origin", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(remote), str(clone)], check=True, capture_output=True)
    run_git(clone, "config", "user.name", "Tester")
    run_git(clone, "config", "user.email", "tester@example.test")
    run_git(clone, "switch", "main")
    (source / "remote.txt").write_text("remote\n", encoding="utf-8")
    run_git(source, "add", "remote.txt")
    run_git(source, "commit", "-m", "remote update")
    run_git(source, "push")

    application = VersionControlApplication()
    clone_target = target(clone)
    application.execute(clone_target, RemoteFetch())
    application.execute(clone_target, RemotePullFastForward())
    assert (clone / "remote.txt").read_text(encoding="utf-8") == "remote\n"

    (clone / "local.txt").write_text("local\n", encoding="utf-8")
    run_git(clone, "add", "local.txt")
    run_git(clone, "commit", "-m", "local update")
    application.execute(clone_target, RemotePush())
    assert run_git(source, "fetch", "origin") == ""
    assert run_git(source, "rev-parse", "origin/main") == run_git(clone, "rev-parse", "HEAD")


def test_changes_commit_and_discard_operate_on_current_index_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (repo / "README.md").write_text("staged\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    application = VersionControlApplication()
    repository_target = target(repo)

    application.execute(repository_target, StagePaths(paths=("README.md",)))
    changes = application.read(repository_target, ChangesListQuery())
    assert [item.path for item in changes.staged.items] == ["README.md"]
    assert [item.path for item in changes.untracked.items] == ["untracked.txt"]

    result = application.execute(
        repository_target,
        CommitCreate(message="shared commit"),
        ActorContext(
            display_name="Taylor",
            git_name="Taylor Author",
            git_email="taylor@example.test",
        ),
    )
    assert result.head_sha == run_git(repo, "rev-parse", "HEAD")
    assert run_git(repo, "show", "-s", "--format=%an <%ae>") == (
        "Taylor Author <taylor@example.test>"
    )
    assert run_git(repo, "show", "--format=", "--name-only", "HEAD") == "README.md"
    assert (repo / "untracked.txt").exists()

    application.execute(
        repository_target,
        DiscardChanges(paths=("untracked.txt",)),
    )
    assert not (repo / "untracked.txt").exists()


def test_stage_all_always_includes_untracked_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    VersionControlApplication().execute(target(repo), StageAll())

    assert run_git(repo, "diff", "--cached", "--name-only") == "untracked.txt"


def test_stage_all_and_unstage_all_report_repository_totals(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    application = VersionControlApplication()
    repository_target = target(repo)

    staged = application.execute(repository_target, StageAll())
    assert staged.affected_total == 2
    assert len(application.read(repository_target, ChangesListQuery()).staged.items) == 2

    unstaged = application.execute(repository_target, UnstageAll())
    assert unstaged.affected_total == 2
    assert application.read(repository_target, ChangesListQuery()).staged.total == 0


def test_history_search_diff_and_blob_use_server_side_git_truth(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("second\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "second feature")
    application = VersionControlApplication()
    repository_target = target(repo)

    history = application.read(
        repository_target, HistoryListQuery(scope="all", search="feature", limit=10)
    )
    assert history.total == 1
    assert history.items[0].message == "second feature"
    assert application.read(
        repository_target, BlobQuery(path="README.md", ref="HEAD")
    ).content == "second\n"
    assert "-initial" in application.read(
        repository_target,
        DiffQuery(path="README.md", commit_sha=run_git(repo, "rev-parse", "HEAD")),
    ).patch


def test_history_reports_empty_page_for_repository_without_commits(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("untracked\n", encoding="utf-8")

    history = VersionControlApplication().read(target(repo), HistoryListQuery())

    assert history.items == []
    assert history.total == 0
    assert history.has_more is False
    assert history.next_cursor is None
    assert history.query_scope == "current"


def test_conflict_resolution_blocks_commit_and_supports_mark_resolved_then_abort(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    run_git(repo, "switch", "-c", "feature")
    (repo / "README.md").write_text("feature\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "feature")
    run_git(repo, "switch", "main")
    (repo / "README.md").write_text("main\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "main")
    subprocess.run(
        ["git", "-C", str(repo), "merge", "feature"],
        check=False,
        capture_output=True,
    )
    application = VersionControlApplication()
    repository_target = target(repo)

    with pytest.raises(VersionControlError) as raised:
        application.execute(
            repository_target,
            CommitCreate(message="must not commit"),
            ActorContext("Taylor", "Taylor", "taylor@example.test"),
        )
    assert raised.value.error_code == "unresolved_conflicts"

    (repo / "README.md").write_text("resolved\n", encoding="utf-8")
    application.execute(
        repository_target, ConflictMarkResolved(paths=("README.md",))
    )
    assert application.read(repository_target, RepositoryStatusQuery()).conflict_total == 0

    application.execute(repository_target, ConflictAbort())
    assert (repo / "README.md").read_text(encoding="utf-8") == "main\n"
    assert run_git(repo, "status", "--porcelain") == ""


def test_lfs_patterns_and_snapshot_preview_use_gitattributes_as_truth(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "asset.bin").write_bytes(b"binary")
    (repo / "nested").mkdir()
    (repo / "nested" / "large.bin").write_bytes(b"0123456789")
    (repo / "note.txt").write_text("note\n", encoding="utf-8")
    (repo / ".gitattributes").write_text(
        "# Keep this comment\n*.txt text eol=lf\n",
        encoding="utf-8",
    )
    application = VersionControlApplication()
    repository_target = target(repo)

    application.execute(repository_target, LfsPatternsUpdate(patterns=("*.bin",)))

    assert application.read(repository_target, LfsPatternsQuery()).patterns == ("*.bin",)
    attributes = (repo / ".gitattributes").read_text(encoding="utf-8")
    assert "# Keep this comment" in attributes
    assert "*.txt text eol=lf" in attributes
    assert [
        item.path
        for item in application.read(
            repository_target, ChangesListQuery(group="staged")
        ).staged.items
    ] == [".gitattributes"]
    preview = application.execute(
        repository_target, LfsSnapshotPreview(patterns=("*.bin",))
    )
    assert preview.matched_total == 2
    assert preview.total_size == 16
    assert preview.path_sample == ("asset.bin", "nested/large.bin")
    assert all(not Path(path).is_absolute() for path in preview.path_sample)


def test_repository_setup_and_remote_settings_use_typed_commands(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    initialized = tmp_path / "initialized"
    initialized_target = target(initialized)
    application = VersionControlApplication()

    application.execute(initialized_target, RepositoryInitialize(default_branch="develop"))
    assert run_git(initialized, "branch", "--show-current") == "develop"
    application.execute(
        initialized_target,
        RemoteSettingsUpdate(name="origin", url=str(remote)),
    )
    settings = application.read(
        initialized_target, RemoteSettingsQuery(name="origin")
    )
    assert settings.remote_name == "origin"
    assert settings.remote_url == str(remote)
    assert settings.has_origin is True

    missing = application.read(
        initialized_target, RemoteSettingsQuery(name="upstream")
    )
    assert missing.remote_name == "upstream"
    assert missing.remote_url is None
    assert missing.has_origin is False

    source = init_repo(tmp_path / "source")
    run_git(source, "remote", "add", "origin", str(remote))
    run_git(source, "push", "-u", "origin", "main")
    cloned = tmp_path / "cloned"
    application.execute(target(cloned), RepositoryClone(remote_url=str(remote), branch="main"))
    assert (cloned / "README.md").read_text(encoding="utf-8") == "initial\n"


def test_revert_creates_inverse_commit_without_rewriting_history(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "change")
    change_sha = run_git(repo, "rev-parse", "HEAD")

    VersionControlApplication().execute(
        target(repo),
        CommitRevert(sha=change_sha),
        ActorContext(
            display_name="Taylor",
            git_name="Taylor Reverter",
            git_email="taylor@example.test",
        ),
    )

    assert (repo / "README.md").read_text(encoding="utf-8") == "initial\n"
    assert run_git(repo, "rev-list", "--count", "HEAD") == "3"
    assert run_git(repo, "show", "-s", "--format=%an <%ae>", "HEAD") == (
        "Taylor Reverter <taylor@example.test>"
    )


def test_lfs_snapshot_convert_reports_missing_runtime_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "asset.bin").write_bytes(b"binary")
    # Simulate a runtime without git-lfs instead of depending on whether the
    # test image happens to ship it.
    real_git_allow_failure = lfs_module.git_allow_failure

    def without_git_lfs(repo_root: Path, *args: str, **kwargs):
        if args[:2] == ("lfs", "version"):
            return GitCommandResult(
                args=list(args),
                returncode=1,
                stdout="",
                stderr="git: 'lfs' is not a git command.",
            )
        return real_git_allow_failure(repo_root, *args, **kwargs)

    monkeypatch.setattr(lfs_module, "git_allow_failure", without_git_lfs)

    with pytest.raises(VersionControlError) as raised:
        VersionControlApplication().execute(
            target(repo), LfsSnapshotConvert(paths=("asset.bin",))
        )

    assert raised.value.error_code == "lfs_unavailable"


def test_force_unlock_only_clears_stale_on_disk_git_locks(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    application = VersionControlApplication()

    with pytest.raises(VersionControlError) as fresh:
        application.execute(target(repo), OperationForceUnlock())
    assert fresh.value.error_code == "operation_lock_not_stale"
    assert lock.exists()

    stale_time = time.time() - 60
    os.utime(lock, (stale_time, stale_time))
    result = application.execute(target(repo), OperationForceUnlock())

    assert result.affected_total == 1
    assert not lock.exists()


def test_numstat_returns_only_requested_visible_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("initial\nsecond\n", encoding="utf-8")
    (repo / "hidden.txt").write_text("hidden\n", encoding="utf-8")

    result = VersionControlApplication().read(
        target(repo), NumstatQuery(paths=("README.md",))
    )

    assert [(item.path, item.additions, item.deletions) for item in result.entries] == [
        ("README.md", 1, 0)
    ]


def test_lfs_snapshot_conversion_reports_progress_and_accepts_cancel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    path = "asset.bin"
    (repo / path).write_bytes(b"asset\n")
    repository_target = RepositoryTarget(
        root=repo,
        lock_scope_keys=LockScopeKeys("repository:test", "repository:test:primary"),
    )
    application = VersionControlApplication()
    conversion_started = threading.Event()
    allow_conversion_to_finish = threading.Event()

    def controlled_conversion(
        repo_root,
        paths,
        *,
        progress,
        is_cancel_requested,
        environment,
    ):
        _ = repo_root, environment
        normalized = tuple(paths)
        progress(0, len(normalized))
        conversion_started.set()
        assert allow_conversion_to_finish.wait(timeout=5)
        if is_cancel_requested():
            raise VersionControlError("operation_cancelled")
        return normalized

    monkeypatch.setattr(
        "aileron_git_core.application.convert_snapshot",
        controlled_conversion,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        conversion = executor.submit(
            application.execute,
            repository_target,
            LfsSnapshotConvert(paths=(path,)),
        )
        assert conversion_started.wait(timeout=5)
        observed = application.operation_manager.active_operation(
            repository_target.lock_scope_keys.working_tree_target
        )
        assert observed is not None
        assert observed.cancellable is True
        application.execute(repository_target, OperationCancel())
        allow_conversion_to_finish.set()
        with pytest.raises(VersionControlError) as cancelled:
            conversion.result(timeout=5)

    assert cancelled.value.error_code == "operation_cancelled"
    assert application.operation_manager.active_operation(
        repository_target.lock_scope_keys.working_tree_target
    ) is None


def test_commit_files_combines_name_status_numstat_and_patch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "added.txt").write_text("added\n", encoding="utf-8")
    run_git(repo, "add", "README.md", "added.txt")
    run_git(repo, "commit", "-m", "change files")
    sha = run_git(repo, "rev-parse", "HEAD")

    result = VersionControlApplication().read(target(repo), CommitFilesQuery(sha=sha))

    files = {item.path: item for item in result.files}
    assert files["README.md"].status == "M"
    assert files["README.md"].additions == 1
    assert files["README.md"].deletions == 1
    assert "+changed" in files["README.md"].patch
    assert files["added.txt"].status == "A"
    assert files["added.txt"].additions == 1


def test_read_maps_missing_blob_to_shared_error(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")

    with pytest.raises(VersionControlError) as raised:
        VersionControlApplication().read(
            target(repo), BlobQuery(path="missing.txt", ref="HEAD")
        )

    assert raised.value.error_code == "file_conflict"


@pytest.mark.parametrize(
    "query",
    [
        ChangesListQuery(),
        HistoryListQuery(),
        NumstatQuery(paths=("README.md",)),
        DiffQuery(path="README.md"),
        LfsPatternsQuery(),
        RemoteSettingsQuery(),
    ],
)
def test_read_reports_uninitialized_repository_instead_of_file_conflict(
    tmp_path: Path, query
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(VersionControlError) as raised:
        VersionControlApplication().read(target(workspace), query)

    assert raised.value.error_code == "repository_not_initialized"


@pytest.mark.parametrize(
    "query, attribute, expected",
    [
        (RepositoryStatusQuery(), "is_initialized", False),
        (BranchListQuery(), "branches", []),
    ],
)
def test_read_keeps_status_and_branch_queries_available_before_initialization(
    tmp_path: Path, query, attribute: str, expected
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = VersionControlApplication().read(target(workspace), query)

    assert getattr(result, attribute) == expected


def test_application_uses_injected_stale_lock_threshold(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    stale_time = time.time() - 2
    os.utime(lock, (stale_time, stale_time))

    result = VersionControlApplication(stale_threshold_seconds=1).execute(
        target(repo), StageAll()
    )

    assert result.affected_total == 1
    assert not lock.exists()
    assert run_git(repo, "status", "--porcelain").startswith("M  README.md")


def test_operation_locked_error_exposes_stale_force_unlock_capability(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    repository_target = target(repo)
    application = VersionControlApplication(stale_threshold_seconds=0)

    def read_status() -> None:
        application.read(repository_target, RepositoryStatusQuery())

    with application.operation_manager.acquire_scoped(
        repository_target.lock_scope_keys,
        VersionControlOperation.CHANGES_STAGE_ALL,
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(VersionControlError) as raised:
                executor.submit(read_status).result(timeout=1)

    assert raised.value.error_code == "operation_locked"
    assert raised.value.stale is True
    assert raised.value.can_force_unlock is True
    assert raised.value.operation_status.stale is True
