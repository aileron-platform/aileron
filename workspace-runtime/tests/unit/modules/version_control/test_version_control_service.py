"""Version Control Service Unit Tests."""

from __future__ import annotations

import pytest
from pathlib import Path
from git import Actor, Repo

from app.modules.version_control.service import (
    GitService,
    VersionControlError,
)
from app.modules.version_control.models import (
    StageRequest,
    UnstageRequest,
    CommitRequest,
    CheckoutRequest,
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
    service = GitService(base_path=tmp_path)

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
        assert status.branch is not None
        assert status.stagedCount == 0
        assert status.unstagedCount == 0
        assert status.untrackedCount == 0

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
        assert status.unstagedCount >= 1 or status.untrackedCount >= 1
        assert status.unstagedCount + status.untrackedCount >= 2

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

    def test_checkout_branch_success(self, git_workspace):
        """Test successful branch checkout."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create new branch
        repo.create_head("feature-branch")

        # Act
        payload = CheckoutRequest(create=False)
        result = service.checkout_branch(workspace_id, "feature-branch", payload)

        # Assert
        assert result.branch == "feature-branch"

    def test_checkout_nonexistent_branch(self, git_workspace):
        """Test checkout nonexistent branch."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act & Assert
        payload = CheckoutRequest(create=False)
        with pytest.raises(VersionControlError):
            service.checkout_branch(workspace_id, "nonexistent-branch", payload)


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

    def test_stage_all_changes(self, git_workspace):
        """Test staging all changes."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Create multiple new files
        for i in range(3):
            file_path = workspace_path / f"file{i}.txt"
            file_path.write_text(f"Content {i}")

        # Act
        payload = StageRequest(paths=["."])
        result = service.stage(workspace_id, payload)

        # Assert
        assert len(result.staged) >= 3

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
        from app.modules.version_control.models import CommitAuthor
        payload = CommitRequest(
            message="Test commit",
            author=CommitAuthor(name="Test User", email="test@example.com"),
        )
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
        result = service.list_commits(workspace_id, page=1, page_size=10)

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
        total_changes = len(result.staged) + len(result.unstaged) + len(result.untracked)
        assert total_changes == 0
        assert len(result.staged) == 0
        assert len(result.unstaged) == 0
        assert len(result.untracked) == 0

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
        total_changes = len(result.staged) + len(result.unstaged) + len(result.untracked)
        assert total_changes >= 1
        all_changes = result.staged + result.unstaged + result.untracked
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
        total_changes = len(result.staged) + len(result.unstaged) + len(result.untracked)
        assert total_changes >= 1
        assert any(f.path == "untracked.txt" for f in result.untracked)


class TestWorkspaceValidation:
    """Test workspace validation functionality."""

    def test_non_git_repository(self, tmp_path):
        """Test non-Git repository."""
        # Arrange
        workspace_id = "non-git-workspace"
        workspace_path = tmp_path / workspace_id
        workspace_path.mkdir()

        service = GitService(base_path=tmp_path)

        # Act & Assert
        with pytest.raises(VersionControlError) as exc_info:
            service.get_status(workspace_id)

        assert exc_info.value.error_code == "VC_REPOSITORY_NOT_INITIALIZED"

    def test_workspace_path_resolution(self, git_workspace):
        """Test workspace path resolution."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act
        resolved_path = service._workspace_path(workspace_id)

        # Assert
        assert resolved_path == workspace_path
        assert resolved_path.exists()


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
        service = GitService(base_path=new_path)

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


class TestBranchState:
    """Test branch state functionality."""

    def test_current_branch(self, git_workspace):
        """Test getting current branch."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Act
        branch_name, detached = service._current_branch(repo)

        # Assert
        assert branch_name is not None
        assert detached is False

    def test_detached_head_state(self, git_workspace):
        """Test detached HEAD state."""
        # Arrange
        service, workspace_id, workspace_path, repo = git_workspace

        # Switch to detached HEAD state
        commit = repo.head.commit
        repo.git.checkout(commit.hexsha)

        # Act
        branch_name, detached = service._current_branch(repo)

        # Assert
        assert detached is True
        assert len(branch_name) > 0  # Should be short version of commit SHA
