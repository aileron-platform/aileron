"""Git repository fixtures for testing

Provides various Git repository configurations for testing version control functionality.
"""

import pytest
from pathlib import Path
from git import Repo, Actor
from typing import Tuple


@pytest.fixture
def git_actor():
    """Provide a Git Actor for commits

    Usage:
        def test_commit(git_actor, tmp_path):
            repo = Repo.init(tmp_path)
            (tmp_path / "file.txt").write_text("content")
            repo.index.add(["file.txt"])
            repo.index.commit("Test commit", author=git_actor, committer=git_actor)
    """
    return Actor("Test User", "test@example.com")


@pytest.fixture
def git_repo_empty(tmp_path, git_actor) -> Tuple[Repo, Path]:
    """Create an empty Git repository

    Usage:
        def test_empty_repo(git_repo_empty):
            repo, repo_path = git_repo_empty
            assert len(list(repo.iter_commits())) == 0
    """
    repo_path = tmp_path / "empty_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    return repo, repo_path


@pytest.fixture
def git_repo_with_commits(tmp_path, git_actor) -> Tuple[Repo, Path]:
    """Create a Git repository with multiple commits

    Structure:
    - Initial commit: README.md
    - Second commit: file1.txt
    - Third commit: file2.txt

    Usage:
        def test_commits(git_repo_with_commits):
            repo, repo_path = git_repo_with_commits
            commits = list(repo.iter_commits())
            assert len(commits) == 3
    """
    repo_path = tmp_path / "repo_with_commits"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit", author=git_actor, committer=git_actor)

    # Second commit
    file1 = repo_path / "file1.txt"
    file1.write_text("Content 1\\n")
    repo.index.add(["file1.txt"])
    repo.index.commit("Add file1", author=git_actor, committer=git_actor)

    # Third commit
    file2 = repo_path / "file2.txt"
    file2.write_text("Content 2\\n")
    repo.index.add(["file2.txt"])
    repo.index.commit("Add file2", author=git_actor, committer=git_actor)

    return repo, repo_path


@pytest.fixture
def git_repo_with_branches(tmp_path, git_actor) -> Tuple[Repo, Path]:
    """Create a Git repository with multiple branches

    Structure:
    - main branch: main.txt
    - feature/test branch: feature.txt

    Usage:
        def test_branches(git_repo_with_branches):
            repo, repo_path = git_repo_with_branches
            assert "main" in repo.heads
            assert "feature/test" in repo.heads
    """
    repo_path = tmp_path / "repo_with_branches"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Main branch
    main_file = repo_path / "main.txt"
    main_file.write_text("main content\\n")
    repo.index.add(["main.txt"])
    repo.index.commit("Main commit", author=git_actor, committer=git_actor)

    # Rename default branch to main (if needed)
    try:
        repo.git.branch("-m", "main")
    except Exception:
        pass

    # Feature branch
    feature_branch = repo.create_head("feature/test")
    feature_branch.checkout()

    feature_file = repo_path / "feature.txt"
    feature_file.write_text("feature content\\n")
    repo.index.add(["feature.txt"])
    repo.index.commit("Feature commit", author=git_actor, committer=git_actor)

    # Switch back to main
    repo.heads.main.checkout()

    return repo, repo_path


@pytest.fixture
def git_repo_with_unstaged_changes(tmp_path, git_actor) -> Tuple[Repo, Path]:
    """Create a Git repository with unstaged changes

    Usage:
        def test_status(git_repo_with_unstaged_changes):
            repo, repo_path = git_repo_with_unstaged_changes
            assert repo.is_dirty()
    """
    repo_path = tmp_path / "repo_with_changes"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Initial commit
    file1 = repo_path / "file1.txt"
    file1.write_text("original content\\n")
    repo.index.add(["file1.txt"])
    repo.index.commit("Initial commit", author=git_actor, committer=git_actor)

    # Modify file (unstaged)
    file1.write_text("modified content\\n")

    # Add new file (untracked)
    new_file = repo_path / "new_file.txt"
    new_file.write_text("new content\\n")

    return repo, repo_path


@pytest.fixture
def git_repo_with_staged_changes(tmp_path, git_actor) -> Tuple[Repo, Path]:
    """Create a Git repository with staged changes

    Usage:
        def test_staged(git_repo_with_staged_changes):
            repo, repo_path = git_repo_with_staged_changes
            assert len(repo.index.diff("HEAD")) > 0
    """
    repo_path = tmp_path / "repo_with_staged"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Initial commit
    file1 = repo_path / "file1.txt"
    file1.write_text("original content\\n")
    repo.index.add(["file1.txt"])
    repo.index.commit("Initial commit", author=git_actor, committer=git_actor)

    # Modify and stage
    file1.write_text("modified content\\n")
    repo.index.add(["file1.txt"])

    # Add new file and stage
    new_file = repo_path / "new_file.txt"
    new_file.write_text("new content\\n")
    repo.index.add(["new_file.txt"])

    return repo, repo_path


@pytest.fixture
def git_repo_with_remote(tmp_path_factory, git_actor) -> Tuple[Repo, Repo, Path, Path]:
    """Create a Git repository with a remote (bare) repository

    Returns:
        (local_repo, remote_repo, local_path, remote_path)

    Usage:
        def test_remote(git_repo_with_remote):
            local_repo, remote_repo, local_path, remote_path = git_repo_with_remote
            # Push to remote
            local_repo.git.push("origin", "main")
    """
    base_path = tmp_path_factory.mktemp("git_repos")

    # Create bare remote repository
    remote_path = base_path / "remote.git"
    remote_path.mkdir()
    remote_repo = Repo.init(remote_path, bare=True)

    # Create local repository
    local_path = base_path / "local"
    local_path.mkdir()
    local_repo = Repo.init(local_path)

    # Initial commit
    readme = local_path / "README.md"
    readme.write_text("# Test Repository\\n")
    local_repo.index.add(["README.md"])
    local_repo.index.commit("Initial commit", author=git_actor, committer=git_actor)

    # Rename to main
    try:
        local_repo.git.branch("-m", "main")
    except Exception:
        pass

    # Add remote
    if "origin" not in [remote.name for remote in local_repo.remotes]:
        local_repo.create_remote("origin", remote_path.as_posix())

    # Push to remote
    local_repo.git.push("-u", "origin", "main")

    return local_repo, remote_repo, local_path, remote_path


@pytest.fixture
def git_repo_with_conflicts(tmp_path, git_actor) -> Tuple[Repo, Path]:
    """Create a Git repository in a conflicted state

    Structure:
    - main branch has conflict.txt with "main content"
    - conflict branch has conflict.txt with "conflict content"

    Usage:
        def test_conflicts(git_repo_with_conflicts):
            repo, repo_path = git_repo_with_conflicts
            # Attempting to merge will cause conflict
            # repo.git.merge("conflict_branch")  # This will fail
    """
    repo_path = tmp_path / "repo_with_conflicts"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    conflict_file = repo_path / "conflict.txt"

    # Initial commit
    conflict_file.write_text("original content\\n")
    repo.index.add(["conflict.txt"])
    repo.index.commit("Initial commit", author=git_actor, committer=git_actor)

    # Main branch modification
    try:
        repo.git.branch("-m", "main")
    except Exception:
        pass

    conflict_file.write_text("main content\\n")
    repo.index.add(["conflict.txt"])
    repo.index.commit("Main change", author=git_actor, committer=git_actor)

    # Conflict branch
    repo.git.checkout("-b", "conflict_branch", "HEAD~1")
    conflict_file.write_text("conflict content\\n")
    repo.index.add(["conflict.txt"])
    repo.index.commit("Conflict change", author=git_actor, committer=git_actor)

    # Switch back to main
    repo.heads.main.checkout()

    return repo, repo_path


@pytest.fixture
def git_service(tmp_path):
    """Create GitService with test repository path

    Usage:
        def test_git_service(git_service):
            status = await git_service.get_status("test-workspace")
    """
    from app.modules.version_control.service import VersionControlService

    service = VersionControlService(base_path=tmp_path)
    return service
