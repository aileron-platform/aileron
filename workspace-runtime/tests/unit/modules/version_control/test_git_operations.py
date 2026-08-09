"""Version Control Service Unit Tests."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aileron_git_core import (
    ActorContext,
    LfsPatterns,
    LfsPatternsQuery,
    LfsSnapshotConvert,
    LfsSnapshotPreview,
    LfsSnapshotPreviewResult,
    MutationResult,
    OperationCancel,
    OperationKind,
    RemoteSettings,
    RemoteSettingsQuery,
)
from aileron_git_core.testkit import Actor, Repo

from app.modules.version_control.git_operations import (
    GitService,
    VersionControlError,
)
from app.modules.version_control.models import (
    StageRequest,
    UnstageRequest,
    CommitRequest,
)


@pytest.fixture
def git_workspace(tmp_path):
    """Create test Git workspace."""
    workspace_id = "test-workspace"
    workspace_path = tmp_path / workspace_id
    workspace_path.mkdir()

    # Initialize Git repository
    repo = Repo.init(workspace_path)

    # Create initial commit
    readme = workspace_path / "README.md"
    readme.write_text("# Test Repository\n")
    repo.index.add(["README.md"])
    actor = Actor("Test User", "test@example.com")
    repo.index.commit("Initial commit", author=actor, committer=actor)

    # Create Git service
    service = GitService(
        base_path=tmp_path,
        actor_context_resolver=lambda: ActorContext(
            display_name="Test User",
            git_name="Test User",
            git_email="test@example.com",
        ),
    )

    return service, workspace_id, workspace_path, repo


class TestGitOperations:
    """Test Git operations functionality."""

    def test_get_status_success(self, git_workspace):
        """Test successful repository status retrieval."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act
        status = service.get_status(workspace_id)

        # Assert
        assert status is not None
        assert status.currentBranch is not None
        assert status.stagedTotal == 0
        assert status.unstagedTotal == 0
        assert status.untrackedTotal == 0

    def test_get_status_with_changes(self, git_workspace):
        """Test repository status with changes."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create new file
        new_file = workspace_path / "new.txt"
        new_file.write_text("New file")

        # Modify existing file
        readme = workspace_path / "README.md"
        readme.write_text("# Modified README\n")

        # Act
        status = service.get_status(workspace_id)

        # Assert
        assert status.unstagedTotal >= 1 or status.untrackedTotal >= 1
        assert status.unstagedTotal + status.untrackedTotal >= 2

    def test_get_status_nonexistent_workspace(self, tmp_path):
        """Test nonexistent workspace status."""
        # Arrange
        service = GitService(base_path=tmp_path)

        # Act & Assert
        with pytest.raises(VersionControlError) as exc_info:
            service.get_status("nonexistent-workspace")

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value).lower()


class TestBranchManagement:
    """Test branch management functionality."""

    def test_list_branches_success(self, git_workspace):
        """Test successful branch listing."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act
        result = service.list_branches(workspace_id)

        # Assert
        assert result is not None
        assert len(result.branches) >= 1
        # Should have at least one branch (usually main or master)

    def test_shared_application_branch_lifecycle(self, git_workspace):
        service, workspace_id, _workspace_path, _repo = git_workspace

        created = service.create_branch(
            workspace_id,
            name="feature/shared-branch",
            start_point="HEAD",
        )
        assert created.commandId == "branch.createAndSwitch"
        assert created.branch == "feature/shared-branch"

        branches = service.list_branches(workspace_id)
        current = next(branch for branch in branches.branches if branch.isCurrent)
        assert current.name == "feature/shared-branch"
        assert current.kind == "local"
        assert current.capabilities.delete.allowed is False

        renamed = service.rename_branch(
            workspace_id,
            old_name="feature/shared-branch",
            new_name="feature/renamed",
        )
        assert renamed.commandId == "branch.renameLocal"
        assert renamed.branch == "feature/renamed"

    def test_switch_branch_success(self, git_workspace):
        """Test successful branch checkout."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create new branch
        repo.create_head("feature-branch")

        # Act
        result = service.switch_branch(workspace_id, name="feature-branch")

        # Assert
        assert result.branch == "feature-branch"

    def test_switch_nonexistent_branch(self, git_workspace):
        """Test checkout nonexistent branch."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act & Assert
        with pytest.raises(VersionControlError):
            service.switch_branch(workspace_id, name="nonexistent-branch")

    def test_switch_dirty_repository_is_rejected_without_changing_branch(
        self, git_workspace
    ):
        """Branch transitions never hide local changes in an implicit stash."""
        service, workspace_id, workspace_path, repo = git_workspace
        original_branch = repo.active_branch.name
        repo.create_head("feature-branch")
        (workspace_path / "README.md").write_text("# Uncommitted change\n")

        with pytest.raises(VersionControlError) as exc_info:
            service.switch_branch(workspace_id, name="feature-branch")

        assert exc_info.value.error_code == "repository_dirty"
        assert repo.active_branch.name == original_branch


class TestStagingOperations:
    """Test staging operations functionality."""

    def test_stage_files_success(self, git_workspace):
        """Test successful file staging."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create new file
        new_file = workspace_path / "test.txt"
        new_file.write_text("Test content")

        # Act
        payload = StageRequest(paths=["test.txt"])
        result = service.stage(workspace_id, payload)

        # Assert
        assert len(result.staged) >= 1
        assert "test.txt" in result.staged

    def test_update_lfs_patterns_uses_shared_application_and_stages_attributes(
        self, git_workspace
    ):
        service, workspace_id, workspace_path, _repo = git_workspace

        result = service.update_lfs_patterns(
            workspace_id,
            patterns=["assets/**/*.psd"],
        )

        assert result.commandId == "lfs.patterns.update"
        assert result.affectedTotal == 1
        assert (workspace_path / ".gitattributes").read_text(encoding="utf-8") == (
            "assets/**/*.psd filter=lfs diff=lfs merge=lfs -text\n"
        )
        changes = service.get_changes(workspace_id)
        assert [change.path for change in changes.staged.items] == [".gitattributes"]

    def test_update_lfs_patterns_uses_existing_defaults_when_omitted(
        self, git_workspace
    ):
        service, workspace_id, workspace_path, _repo = git_workspace

        service.update_lfs_patterns(workspace_id)

        attributes = (workspace_path / ".gitattributes").read_text(encoding="utf-8")
        assert "*.pdf filter=lfs diff=lfs merge=lfs -text\n" in attributes
        assert "*.xlsx filter=lfs diff=lfs merge=lfs -text\n" in attributes

    def test_remote_and_lfs_reads_use_shared_queries(self):
        service = GitService.__new__(GitService)
        service._read_shared = MagicMock(
            side_effect=[
                RemoteSettings(
                    remote_name="origin",
                    remote_url="https://example.com/repository.git",
                    has_origin=True,
                ),
                LfsPatterns(patterns=("*.pdf", "*.xlsx")),
            ]
        )

        remote = service.get_remote_settings("workspace")
        patterns = service.get_lfs_patterns("workspace")

        assert remote.model_dump() == {
            "remoteName": "origin",
            "remoteUrl": "https://example.com/repository.git",
            "hasOrigin": True,
        }
        assert patterns.patterns == ["*.pdf", "*.xlsx"]
        assert isinstance(service._read_shared.call_args_list[0].args[1], RemoteSettingsQuery)
        assert isinstance(service._read_shared.call_args_list[1].args[1], LfsPatternsQuery)

    def test_lfs_preview_convert_and_cancel_use_shared_commands(self):
        service = GitService.__new__(GitService)
        service._execute_shared = MagicMock(
            side_effect=[
                LfsSnapshotPreviewResult(
                    matched_total=2,
                    total_size=1024,
                    path_sample=("assets/a.bin", "assets/b.bin"),
                ),
                MutationResult(
                    command_id="lfs.snapshot.convert",
                    affected_total=2,
                ),
                MutationResult(command_id="operation.cancel"),
            ]
        )

        preview = service.preview_lfs_snapshot(
            "workspace", patterns=["assets/**"]
        )
        converted = service.convert_lfs_snapshot(
            "workspace", paths=["assets/a.bin", "assets/b.bin"]
        )
        cancelled = service.cancel_operation("workspace")

        assert preview.matchedTotal == 2
        assert preview.totalSize == 1024
        assert preview.pathSample == ["assets/a.bin", "assets/b.bin"]
        assert converted.commandId == "lfs.snapshot.convert"
        assert converted.affectedTotal == 2
        assert cancelled.commandId == "operation.cancel"
        assert isinstance(
            service._execute_shared.call_args_list[0].args[1], LfsSnapshotPreview
        )
        assert isinstance(
            service._execute_shared.call_args_list[1].args[1], LfsSnapshotConvert
        )
        assert isinstance(
            service._execute_shared.call_args_list[2].args[1], OperationCancel
        )

    def test_operation_status_reads_shared_application_operation(self, git_workspace):
        service, workspace_id, _workspace_path, _repo = git_workspace
        target = service._repository_target(workspace_id)

        with service._version_control_application.operation_manager.acquire(
            target.lock_scope_keys.working_tree_target,
            OperationKind.WRITE,
            operation_name="lfs.patterns.update",
        ):
            status = service.get_operation_status(workspace_id)

        assert status.isActive is True
        assert status.operation == "lfs.patterns.update"
        assert status.blockingScope is None
        assert status.startedAt is not None

    def test_stage_all_changes(self, git_workspace):
        """Test staging all changes."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create multiple new files
        for i in range(3):
            file_path = workspace_path / f"file{i}.txt"
            file_path.write_text(f"Content {i}")

        # Act
        payload = StageRequest(paths=[], all=True)
        service.stage(workspace_id, payload)

        # Assert
        changes = service.get_changes(workspace_id)
        assert changes.staged.total >= 3

    def test_unstage_files_success(self, git_workspace):
        """Test successful file unstaging."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create and stage new file
        new_file = workspace_path / "test.txt"
        new_file.write_text("Test content")
        repo.index.add(["test.txt"])

        # Act
        payload = UnstageRequest(paths=["test.txt"])
        result = service.unstage(workspace_id, payload)

        # Assert
        assert len(result.unstaged) >= 1


class TestCommitOperations:
    """Test commit operations functionality."""

    def test_commit_success(self, git_workspace):
        """Test successful commit."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create and stage new file
        new_file = workspace_path / "commit_test.txt"
        new_file.write_text("Test content")
        repo.index.add(["commit_test.txt"])

        # Act
        payload = CommitRequest(message="Test commit")
        result = service.commit(workspace_id, payload)

        # Assert
        assert result.commit is not None
        assert result.commit.id is not None
        assert len(result.commit.id) > 0

    def test_list_commits_success(self, git_workspace):
        """Test successful commit listing."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act
        result = service.list_commits(workspace_id, cursor=None, limit=10)

        # Assert
        assert result is not None
        assert len(result.items) >= 1  # At least initial commit
        assert result.total >= 1

    def test_get_commit_success(self, git_workspace):
        """Test successful commit detail retrieval."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Get latest commit
        commit_id = repo.head.commit.hexsha

        # Act
        result = service.get_commit(workspace_id, commit_id)

        # Assert
        assert result is not None
        assert result.id == commit_id
        assert result.message is not None
        assert result.author is not None


class TestChangesOperations:
    """Test changes operations functionality."""

    def test_get_changes_no_changes(self, git_workspace):
        """Test repository with no changes."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act
        result = service.get_changes(workspace_id)

        # Assert
        assert result is not None
        total_changes = (
            len(result.staged.items)
            + len(result.unstaged.items)
            + len(result.untracked.items)
        )
        assert total_changes == 0
        assert len(result.staged.items) == 0
        assert len(result.unstaged.items) == 0
        assert len(result.untracked.items) == 0

    def test_get_changes_with_modifications(self, git_workspace):
        """Test repository with modifications."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Modify file
        readme = workspace_path / "README.md"
        readme.write_text("# Modified README\n")

        # Act
        result = service.get_changes(workspace_id)

        # Assert
        total_changes = (
            len(result.staged.items)
            + len(result.unstaged.items)
            + len(result.untracked.items)
        )
        assert total_changes >= 1
        all_changes = (
            result.staged.items + result.unstaged.items + result.untracked.items
        )
        assert len(all_changes) >= 1
        assert any(f.path == "README.md" for f in all_changes)

    def test_get_changes_with_untracked(self, git_workspace):
        """Test repository with untracked files."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create new file
        new_file = workspace_path / "untracked.txt"
        new_file.write_text("Untracked content")

        # Act
        result = service.get_changes(workspace_id)

        # Assert
        total_changes = (
            len(result.staged.items)
            + len(result.unstaged.items)
            + len(result.untracked.items)
        )
        assert total_changes >= 1
        assert any(f.path == "untracked.txt" for f in result.untracked.items)


class TestWorkspaceValidation:
    """Test workspace validation functionality."""

    def test_repository_status_allows_clone_with_only_runtime_defaults(self, tmp_path):
        workspace_id = "clone-ready-workspace"
        workspace_path = tmp_path / workspace_id
        (workspace_path / ".agents").mkdir(parents=True)
        (workspace_path / ".mcp.json").write_text("{}\n", encoding="utf-8")
        (workspace_path / ".gitignore").write_text(
            "# >>> Aileron managed worktrees >>>\n"
            ".worktrees/\n"
            "# <<< Aileron managed worktrees <<<\n",
            encoding="utf-8",
        )
        service = GitService(base_path=tmp_path)

        result = service.get_repository_status(workspace_id)

        assert result.isGitRepo is False
        assert result.hasLocalContent is True
        assert result.canCloneSafely is True
        assert result.canInitSafely is True
        assert result.cloneBlockedReason is None

    def test_repository_status_blocks_clone_when_workspace_has_user_content(
        self, tmp_path
    ):
        workspace_id = "non-empty-workspace"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()
        (workspace_path / "README.md").write_text("# Local\n", encoding="utf-8")
        service = GitService(base_path=tmp_path)

        result = service.get_repository_status(workspace_id)

        assert result.isGitRepo is False
        assert result.hasLocalContent is True
        assert result.canCloneSafely is False
        assert result.canInitSafely is True
        assert result.cloneBlockedReason == "VC_CLONE_TARGET_NOT_EMPTY"

    def test_repository_status_returns_origin_for_initialized_repository(
        self, git_workspace
    ):
        service, workspace_id, workspace_path, repo = git_workspace
        repo.create_remote("origin", "https://example.com/team/repository.git")

        result = service.get_repository_status(workspace_id)

        assert result.isGitRepo is True
        assert result.currentBranch == repo.active_branch.name
        assert result.remoteUrl == "https://example.com/team/repository.git"
        assert result.hasOrigin is True
        assert result.canCloneSafely is False
        assert result.canInitSafely is False
        assert result.cloneBlockedReason == "VC_REPOSITORY_ALREADY_INITIALIZED"

    def test_non_git_repository(self, tmp_path):
        """Test non-Git repository."""
        # Arrange
        workspace_id = "non-git-workspace"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()

        service = GitService(base_path=tmp_path)

        status = service.get_status(workspace_id)

        assert status.isInitialized is False
        assert status.currentBranch is None

    def test_initialize_repository_preserves_files_and_uses_configured_branch(
        self, tmp_path, monkeypatch
    ):
        workspace_id = "non-git-workspace"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()
        existing_file = workspace_path / "README.md"
        existing_file.write_text("# Existing workspace\n", encoding="utf-8")
        service = GitService(base_path=tmp_path)

        result = service.initialize_repository(workspace_id, default_branch="develop")

        assert (workspace_path / ".git").is_dir()
        assert existing_file.read_text(encoding="utf-8") == "# Existing workspace\n"
        assert result.isInitialized is True
        assert result.currentBranch == "develop"

    def test_clone_repository_populates_workspace_root_without_subdirectory(
        self, tmp_path
    ):
        source_path = tmp_path / "source-repository"
        source_repo = Repo.init(source_path)
        (source_path / ".gitignore").write_text(
            "node_modules/\n",
            encoding="utf-8",
        )
        source_readme = source_path / "README.md"
        source_readme.write_text("# Cloned workspace\n", encoding="utf-8")
        source_repo.index.add([".gitignore", "README.md"])
        actor = Actor("Test User", "test@example.com")
        source_repo.index.commit(
            "Initial commit",
            author=actor,
            committer=actor,
        )

        workspace_id = "clone-target"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()
        service = GitService(base_path=tmp_path)

        result = service.clone_repository(
            workspace_id,
            remote_url=str(source_path),
        )

        assert (workspace_path / ".git").is_dir()
        assert (workspace_path / "README.md").read_text(
            encoding="utf-8"
        ) == "# Cloned workspace\n"
        assert not (workspace_path / source_path.name).exists()
        assert result.isInitialized is True

    def test_clone_repository_preserves_agent_defaults_without_nested_repository(
        self, tmp_path
    ):
        source_path = tmp_path / "source-repository"
        source_repo = Repo.init(source_path)
        (source_path / ".gitignore").write_text(
            "node_modules/\n",
            encoding="utf-8",
        )
        source_readme = source_path / "README.md"
        source_readme.write_text("# Cloned workspace\n", encoding="utf-8")
        source_repo.index.add([".gitignore", "README.md"])
        actor = Actor("Test User", "test@example.com")
        source_repo.index.commit(
            "Initial commit",
            author=actor,
            committer=actor,
        )

        workspace_id = "clone-with-agent-defaults"
        workspace_path = tmp_path / workspace_id
        default_skill = (
            workspace_path
            / ".agents"
            / "skills"
            / "default-skill"
            / "SKILL.md"
        )
        default_skill.parent.mkdir(parents=True)
        default_skill.write_text("# Runtime default\n", encoding="utf-8")
        codex_skills = workspace_path / ".codex" / "skills"
        codex_skills.mkdir(parents=True)
        (codex_skills / "default-skill").symlink_to(default_skill.parent)
        (workspace_path / ".gitignore").write_text(
            "# >>> Aileron managed worktrees >>>\n"
            ".worktrees/\n"
            "# <<< Aileron managed worktrees <<<\n",
            encoding="utf-8",
        )
        service = GitService(base_path=tmp_path)

        result = service.clone_repository(
            workspace_id,
            remote_url=str(source_path),
            branch=source_repo.active_branch.name,
        )

        assert (workspace_path / ".git").is_dir()
        assert (workspace_path / "README.md").is_file()
        assert default_skill.read_text(encoding="utf-8") == "# Runtime default\n"
        assert (codex_skills / "default-skill").is_symlink()
        merged_gitignore = (workspace_path / ".gitignore").read_text(
            encoding="utf-8"
        )
        assert "node_modules/" in merged_gitignore
        assert ".worktrees/" in merged_gitignore
        assert result.isInitialized is True
        assert result.currentBranch == source_repo.active_branch.name
        assert not list(workspace_path.glob(".aileron-clone-*"))

    def test_clone_repository_rejects_agent_default_path_conflict_without_changes(
        self, tmp_path
    ):
        source_path = tmp_path / "source-repository"
        source_repo = Repo.init(source_path)
        (source_path / ".gitignore").write_text(
            "node_modules/\n",
            encoding="utf-8",
        )
        source_skill = (
            source_path / ".agents" / "skills" / "default-skill" / "SKILL.md"
        )
        source_skill.parent.mkdir(parents=True)
        source_skill.write_text("# Repository version\n", encoding="utf-8")
        source_repo.index.add(
            [".gitignore", str(source_skill.relative_to(source_path))]
        )
        actor = Actor("Test User", "test@example.com")
        source_repo.index.commit(
            "Initial commit",
            author=actor,
            committer=actor,
        )

        workspace_id = "clone-conflicting-agent-default"
        workspace_path = tmp_path / workspace_id
        existing_skill = (
            workspace_path
            / ".agents"
            / "skills"
            / "default-skill"
            / "SKILL.md"
        )
        existing_skill.parent.mkdir(parents=True)
        existing_skill.write_text("# User version\n", encoding="utf-8")
        existing_gitignore = workspace_path / ".gitignore"
        existing_gitignore.write_text(".worktrees/\n", encoding="utf-8")
        service = GitService(base_path=tmp_path)

        with pytest.raises(VersionControlError) as exc_info:
            service.clone_repository(
                workspace_id,
                remote_url=str(source_path),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "VC_CLONE_PUBLISH_CONFLICT"
        assert existing_skill.read_text(encoding="utf-8") == "# User version\n"
        assert existing_gitignore.read_text(encoding="utf-8") == ".worktrees/\n"
        assert not (workspace_path / ".git").exists()
        assert not list(workspace_path.glob(".aileron-clone-*"))

    def test_clone_repository_requires_configured_key_for_ssh_remote(
        self, tmp_path
    ):
        workspace_id = "ssh-clone-target"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()
        service = GitService(
            base_path=tmp_path,
            ssh_private_key_path=tmp_path / "missing-id-rsa",
        )

        with pytest.raises(VersionControlError) as exc_info:
            service.clone_repository(
                workspace_id,
                remote_url="git@127.0.0.1:team/repository.git",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "VC_SSH_KEY_REQUIRED"
        assert not (workspace_path / ".git").exists()

    def test_remote_branches_requires_configured_key_for_ssh_remote(
        self, tmp_path
    ):
        workspace_id = "ssh-branch-target"
        (tmp_path / workspace_id).mkdir()
        service = GitService(
            base_path=tmp_path,
            ssh_private_key_path=tmp_path / "missing-id-rsa",
        )

        with pytest.raises(VersionControlError) as exc_info:
            service.remote_branches(
                workspace_id,
                remote_url="git@127.0.0.1:team/repository.git",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "VC_SSH_KEY_REQUIRED"

    def test_remote_branches_logs_redacted_git_diagnostic_on_failure(
        self, tmp_path, monkeypatch, caplog
    ):
        from aileron_git_core.errors import GitCommandError

        workspace_id = "remote-branch-target"
        (tmp_path / workspace_id).mkdir()
        service = GitService(base_path=tmp_path)

        def fail_list_remote_branches(*args, **kwargs):
            raise GitCommandError(
                ["git", "ls-remote", "--heads"],
                128,
                stderr=(
                    "fatal: could not read Username for "
                    "'https://token:secret@example.test'"
                ),
            )

        monkeypatch.setattr(
            "app.modules.version_control.git_operations.list_remote_branches",
            fail_list_remote_branches,
        )

        with caplog.at_level(logging.WARNING):
            with pytest.raises(VersionControlError) as exc_info:
                service.remote_branches(
                    workspace_id,
                    remote_url="https://token:secret@example.test/team/repo.git",
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "VC_REMOTE_BRANCHES_FAILED"
        diagnostics = "\n".join(record.getMessage() for record in caplog.records)
        assert "could not read Username" in diagnostics
        assert "secret" not in diagnostics
        assert "[REDACTED]" in diagnostics

    def test_clone_repository_uses_configured_ssh_key_and_accepts_new_host(
        self, tmp_path, monkeypatch
    ):
        workspace_id = "ssh-clone-target"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()
        private_key_path = tmp_path / "configured key"
        private_key_path.write_text("private key\n", encoding="utf-8")
        private_key_path.chmod(0o600)
        captured_environment: dict[str, str] = {}

        def fake_run_git(repo_root, *args, **kwargs):
            if args[0] != "clone":
                raise AssertionError(f"Unexpected Git command: {args}")
            captured_environment.update(kwargs["env"])
            Repo.init(Path(repo_root) / args[-1], initial_branch="main")

        monkeypatch.setattr(
            "aileron_git_core.application.run_git",
            fake_run_git,
        )
        service = GitService(
            base_path=tmp_path,
            ssh_private_key_path=private_key_path,
        )

        result = service.clone_repository(
            workspace_id,
            remote_url="git@127.0.0.1:team/repository.git",
        )

        assert result.isInitialized is True
        ssh_command = captured_environment["GIT_SSH_COMMAND"]
        assert f"-i '{private_key_path}'" in ssh_command
        assert "-o IdentitiesOnly=yes" in ssh_command
        assert "-o StrictHostKeyChecking=accept-new" in ssh_command

    def test_clone_repository_rejects_non_empty_workspace_without_deleting_files(
        self, tmp_path
    ):
        source_path = tmp_path / "source-repository"
        Repo.init(source_path)
        workspace_id = "non-empty-clone-target"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()
        existing_file = workspace_path / "notes.txt"
        existing_file.write_text("keep me", encoding="utf-8")
        service = GitService(base_path=tmp_path)

        with pytest.raises(VersionControlError) as exc_info:
            service.clone_repository(
                workspace_id,
                remote_url=str(source_path),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "VC_CLONE_TARGET_NOT_EMPTY"
        assert existing_file.read_text(encoding="utf-8") == "keep me"
        assert not (workspace_path / ".git").exists()


class TestGitServiceInitialization:
    """Test Git service initialization functionality."""

    def test_init_with_base_path(self, tmp_path):
        """Test initialization with specified path."""
        # Act
        service = GitService(base_path=tmp_path)

        # Assert
        assert service._root_path == tmp_path

    def test_init_creates_directory(self, tmp_path):
        """Test directory creation on initialization."""
        # Arrange
        new_path = tmp_path / "git_workspaces"

        # Act
        GitService(base_path=new_path)

        # Assert
        assert new_path.exists()
        assert new_path.is_dir()


class TestDiffOperations:
    """Test diff operations functionality."""

    def test_diff_worktree(self, git_workspace):
        """Test worktree diff retrieval."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Modify file
        readme = workspace_path / "README.md"
        readme.write_text("# Modified Content\n")

        # Act
        result = service.diff(workspace_id, path="README.md")

        # Assert
        assert result is not None
        assert result.path == "README.md"
        assert result.patch is not None
        assert len(result.patch) > 0

    def test_diff_staged(self, git_workspace):
        """Test staged diff retrieval."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Modify and stage file
        readme = workspace_path / "README.md"
        readme.write_text("# Staged Content\n")
        repo.index.add(["README.md"])

        # Act
        result = service.diff(workspace_id, path="README.md", head="INDEX")

        # Assert
        assert result is not None
        assert result.path == "README.md"
        assert result.patch is not None
