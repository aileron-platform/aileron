"""TemplateGitService 單元Testing"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from git import GitCommandError, InvalidGitRepositoryError, Repo

from app.models.template_git import (
    GitStatus,
    GitUserConfig,
    TemplateCommitListResponse,
    TemplateStageRequest,
    TemplateUnstageRequest,
)
from app.services.template_git_service import TemplateGitService
from app.services.template_git_service import GitOperationResult


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_repo():
    """Mock Git Repo"""
    repo = MagicMock()
    repo.head.is_detached = False
    repo.active_branch.name = "main"
    repo.untracked_files = []
    repo.remotes = MagicMock()  # Changed from [] to MagicMock() to support .origin attribute
    repo.heads = []
    return repo


@pytest.fixture
def git_service(tmp_path):
    """TemplateGitService Instance"""
    with patch('app.services.template_git_service.get_settings') as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateGitService()
        service.template_center_path = tmp_path
        return service


# ============================================================================
# Repository Detection Tests
# ============================================================================

@pytest.mark.unit
class TestRepositoryDetection:
    """倉庫檢測Testing"""

    def test_is_git_repository_true(self, git_service, mock_repo):
        """Testing：檢測To Git 倉庫"""
        # Arrange
        with patch('app.services.template_git_service.Repo') as mock_repo_class:
            mock_repo_class.return_value = mock_repo

            # Act
            result = git_service.is_git_repository()

            # Assert
            assert result is True

    def test_is_git_repository_false(self, git_service):
        """Testing：未檢測To Git 倉庫"""
        # Arrange
        with patch('app.services.template_git_service.Repo') as mock_repo_class:
            mock_repo_class.side_effect = InvalidGitRepositoryError("Not a git repo")

            # Act
            result = git_service.is_git_repository()

            # Assert
            assert result is False

    def test_repository_status_not_initialized_with_local_content(self, git_service, tmp_path):
        """Testing：未初始化且已有LocalWithin容時ForbiddingDirectly clone"""
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "demo.yaml").write_text("name: demo\n")

        result = git_service.get_repository_status()

        assert result.is_git_repo is False
        assert result.has_local_content is True
        assert result.can_clone_safely is False
        assert result.can_init_safely is True
        assert result.clone_blocked_reason == "GIT_CLONE_TARGET_NOT_EMPTY"

    def test_repository_status_initialized_without_origin(self, tmp_path):
        """Testing：已初始化但未Configure origin"""
        repo = Repo.init(tmp_path)
        (tmp_path / "README.md").write_text("hello\n")

        with patch('app.services.template_git_service.get_settings') as mock_settings:
            mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
            service = TemplateGitService()
            service.template_center_path = tmp_path
            service._repo = repo

        result = service.get_repository_status()

        assert result.is_git_repo is True
        assert result.has_origin is False
        assert result.remote_url is None
        assert result.can_clone_safely is False

    def test_init_repository_creates_git_repo(self, git_service):
        """Testing：可FromTemplateCenter初始化 Git 倉庫"""
        result = git_service.init_repository()

        assert result.success is True
        assert result.code == "GIT_REPOSITORY_INITIALIZED"
        assert (git_service.template_center_path / ".git").exists()
        assert git_service.get_repository_status().is_git_repo is True

    def test_clone_repository_blocks_non_empty_uninitialized_directory(self, git_service, tmp_path):
        """Testing：非 Git 且已有Within容時 clone 不會隱式覆蓋"""
        (tmp_path / "existing.md").write_text("keep me\n")

        result = git_service.clone_repository("https://example.com/repo.git")

        assert result.success is False
        assert result.code == "GIT_CLONE_TARGET_NOT_EMPTY"
        assert (tmp_path / "existing.md").read_text() == "keep me\n"


# ============================================================================
# Git Status Tests
# ============================================================================

@pytest.mark.unit
class TestGitStatus:
    """Git 狀態Testing"""

    def test_get_git_status_not_a_repo(self, git_service):
        """Testing：非 Git 倉庫返BackDefault狀態"""
        # Arrange
        git_service._repo = None
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.get_git_status()

            # Assert
            assert isinstance(result, GitStatus)
            assert result.is_git_repo is False
            assert result.current_branch == ""
            assert result.has_changes is False

    def test_get_git_status_clean_repo(self, git_service, mock_repo):
        """Testing：乾淨的倉庫狀態"""
        # Arrange
        mock_repo.index.diff.return_value = []
        mock_repo.untracked_files = []
        mock_repo.remotes = []

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_git_status()

            # Assert
            assert result.is_git_repo is True
            assert result.current_branch == "main"
            assert result.has_changes is False
            assert result.ahead_count == 0
            assert result.behind_count == 0

    def test_get_git_status_with_changes(self, git_service, mock_repo):
        """Testing：有Change的倉庫狀態"""
        # Arrange
        mock_diff = MagicMock()
        mock_repo.index.diff.return_value = [mock_diff]
        mock_repo.untracked_files = []
        mock_repo.remotes = []

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_git_status()

            # Assert
            assert result.has_changes is True

    def test_get_git_status_with_untracked(self, git_service, mock_repo):
        """Testing：有未TrackingFile的倉庫狀態"""
        # Arrange
        mock_repo.index.diff.return_value = []
        mock_repo.untracked_files = ["newfile.txt"]
        mock_repo.remotes = []

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_git_status()

            # Assert
            assert result.has_changes is True

    def test_get_git_status_with_remote(self, git_service, mock_repo):
        """Testing：含Far端的倉庫狀態"""
        # Arrange
        mock_remote = MagicMock()
        mock_remote.url = "https://github.com/user/repo.git"
        mock_remote.fetch.return_value = None

        # 創建一個 MagicMock remotes Right象，既可以迭代又有 origin Property
        mock_remotes = MagicMock()
        mock_remotes.__iter__.return_value = iter([mock_remote])
        mock_remotes.origin = mock_remote
        mock_repo.remotes = mock_remotes

        mock_repo.index.diff.return_value = []
        mock_repo.untracked_files = []
        mock_repo.iter_commits.return_value = []

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_git_status()

            # Assert
            assert result.remote_url == "https://github.com/user/repo.git"


@pytest.mark.unit
class TestTemplateVersionControlOperations:
    """Template Center file-level version-control operations."""

    def _create_real_repo_service(self, tmp_path):
        repo = Repo.init(tmp_path)
        with repo.config_writer() as config:
            config.set_value("user", "name", "Template Tester")
            config.set_value("user", "email", "template@example.com")
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "demo").mkdir()
        readme = tmp_path / "templates" / "demo" / "README.md"
        readme.write_text("hello\n")
        repo.index.add(["templates/demo/README.md"])
        repo.index.commit("initial")

        with patch('app.services.template_git_service.get_settings') as mock_settings:
            mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
            service = TemplateGitService()
            service.template_center_path = tmp_path
            service._repo = repo
            return service

    def test_file_level_changes_include_unstaged_and_untracked(self, tmp_path):
        service = self._create_real_repo_service(tmp_path)
        (tmp_path / "templates" / "demo" / "README.md").write_text("hello\nworld\n")
        (tmp_path / "templates" / "demo" / "new.md").write_text("new\n")

        changes = service.get_file_changes()

        assert [item.path for item in changes.unstaged] == ["templates/demo/README.md"]
        assert [item.path for item in changes.untracked] == ["templates/demo/new.md"]
        assert changes.untrackedTotal == 1

    def test_diff_returns_unified_patch_for_untracked_file(self, tmp_path):
        service = self._create_real_repo_service(tmp_path)
        (tmp_path / "templates" / "demo" / "new.md").write_text("new\n")

        diff = service.diff("templates/demo/new.md")

        assert diff.path == "templates/demo/new.md"
        assert "--- /dev/null" in diff.patch
        assert "+++ b/templates/demo/new.md" in diff.patch
        assert "+new" in diff.patch

    def test_stage_and_unstage_paths(self, tmp_path):
        service = self._create_real_repo_service(tmp_path)
        (tmp_path / "templates" / "demo" / "README.md").write_text("hello\nworld\n")

        staged = service.stage(TemplateStageRequest(paths=["templates/demo/README.md"]))
        changes_after_stage = service.get_file_changes()
        unstaged = service.unstage(TemplateUnstageRequest(paths=["templates/demo/README.md"]))

        assert staged.staged == ["templates/demo/README.md"]
        assert [item.path for item in changes_after_stage.staged] == ["templates/demo/README.md"]
        assert unstaged.unstaged == ["templates/demo/README.md"]

    def test_staged_changes_show_before_first_commit(self, tmp_path):
        repo = Repo.init(tmp_path)
        (tmp_path / "templates" / "demo").mkdir(parents=True)
        (tmp_path / "templates" / "demo" / "README.md").write_text("hello\n")
        service = TemplateGitService()
        service.template_center_path = tmp_path
        service._repo = repo

        service.stage(TemplateStageRequest(paths=["templates/demo/README.md"]))
        changes = service.get_file_changes()
        status = service.get_version_control_status()
        diff = service.diff("templates/demo/README.md", head="INDEX")

        assert [item.path for item in changes.staged] == ["templates/demo/README.md"]
        assert changes.staged[0].status == "A"
        assert status.stagedCount == 1
        assert "+++ b/templates/demo/README.md" in diff.patch
        assert "+hello" in diff.patch

    def test_commit_history_lists_new_commit(self, tmp_path):
        service = self._create_real_repo_service(tmp_path)
        (tmp_path / "templates" / "demo" / "README.md").write_text("hello\nworld\n")
        service.stage(TemplateStageRequest(paths=["templates/demo/README.md"]))
        service.commit("update demo")

        commits = service.list_commits()

        assert isinstance(commits, TemplateCommitListResponse)
        assert commits.total == 2
        assert commits.items[0].message == "update demo"

    def test_commit_history_is_empty_for_initialized_repo_without_commits(self, tmp_path):
        service = TemplateGitService()
        service.template_center_path = tmp_path
        service._repo = Repo.init(tmp_path)

        commits = service.list_commits()

        assert commits.total == 0
        assert commits.items == []

    def test_safe_repo_path_rejects_traversal(self, tmp_path):
        service = self._create_real_repo_service(tmp_path)

        with pytest.raises(ValueError, match="GIT_PATH_OUTSIDE_REPOSITORY"):
            service._safe_repo_path("../outside.md")


# ============================================================================
# User Config Tests
# ============================================================================

@pytest.mark.unit
class TestUserConfig:
    """Use者SetupTesting"""

    def test_get_user_config_success(self, git_service):
        """Testing：GetUse者SetupSuccessfully"""
        # Arrange
        with patch('git.GitConfigParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.get_value.side_effect = ["Test User", "test@example.com"]
            mock_parser.__enter__ = Mock(return_value=mock_parser)
            mock_parser.__exit__ = Mock(return_value=None)
            mock_parser_class.return_value = mock_parser

            # Act
            result = git_service.get_user_config()

            # Assert
            assert isinstance(result, GitUserConfig)
            assert result.user_name == "Test User"
            assert result.user_email == "test@example.com"

    def test_get_user_config_error(self, git_service):
        """Testing：GetUse者SetupUnsuccessfully返Back None"""
        # Arrange
        with patch('git.GitConfigParser') as mock_parser_class:
            mock_parser_class.side_effect = Exception("Config error")

            # Act
            result = git_service.get_user_config()

            # Assert
            assert result.user_name is None
            assert result.user_email is None

    def test_update_user_config_success(self, git_service):
        """Testing：MoreNewUse者SetupSuccessfully"""
        # Arrange
        with patch('git.GitConfigParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.__enter__ = Mock(return_value=mock_parser)
            mock_parser.__exit__ = Mock(return_value=None)
            mock_parser_class.return_value = mock_parser

            # Act
            result = git_service.update_user_config("New User", "new@example.com")

            # Assert
            assert result.success is True
            assert result.code == "GIT_USER_CONFIG_UPDATED"
            mock_parser.set_value.assert_called()

    def test_update_user_config_empty_values(self, git_service):
        """Testing：MoreNewUse者Setup時空ValueUnsuccessfully"""
        # Act
        result = git_service.update_user_config("", "")

        # Assert
        assert result.success is False
        assert result.code == "GIT_USER_CONFIG_REQUIRED"


# ============================================================================
# Remote URL Tests
# ============================================================================

@pytest.mark.unit
class TestRemoteUrl:
    """Far端 URL Testing"""

    def test_set_remote_url_not_a_repo(self, git_service):
        """Testing：非 Git 倉庫ConfigureFar端 URL Unsuccessfully"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.set_remote_url("https://github.com/user/repo.git")

            # Assert
            assert result.success is False
            assert result.code == "GIT_REPO_NOT_FOUND"

    def test_set_remote_url_empty(self, git_service, mock_repo):
        """Testing：Configure空 URL Unsuccessfully"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.set_remote_url("")

            # Assert
            assert result.success is False
            assert result.code == "GIT_REMOTE_URL_EMPTY"

    def test_set_remote_url_create_new(self, git_service, mock_repo):
        """Testing：BuildingNew的Far端 URL"""
        # Arrange
        mock_repo.remotes = []
        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.set_remote_url("https://github.com/user/repo.git")

            # Assert
            assert result.success is True
            assert result.code == "GIT_REMOTE_URL_CREATED"
            assert result.params["url"] == "https://github.com/user/repo.git"
            mock_repo.create_remote.assert_called_once_with("origin", "https://github.com/user/repo.git")

    def test_set_remote_url_update_existing(self, git_service, mock_repo):
        """Testing：MoreNew現有Far端 URL"""
        # Arrange
        mock_remote = MagicMock()
        # Make remotes a MagicMock that supports both 'in' operator and .origin attribute
        mock_remotes = MagicMock()
        mock_remotes.__contains__ = Mock(return_value=True)  # Support 'in' operator
        mock_remotes.origin = mock_remote  # Support .origin attribute
        mock_repo.remotes = mock_remotes

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.set_remote_url("https://github.com/user/new-repo.git")

            # Assert
            assert result.success is True
            assert result.code == "GIT_REMOTE_URL_UPDATED"
            assert result.params["url"] == "https://github.com/user/new-repo.git"
            mock_remote.set_url.assert_called_once_with("https://github.com/user/new-repo.git")


# ============================================================================
# SSH Keys Tests
# ============================================================================

@pytest.mark.unit
class TestSSHKeys:
    """SSH Keys Testing"""

    def test_get_ssh_keys_not_exist(self, tmp_path):
        """Testing：SSH Keys 不存At"""
        # Arrange - Use空的臨時Catalog作為 SSH Catalog
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        with patch('app.services.template_git_service.get_settings') as mock_settings:
            mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
            git_service = TemplateGitService(ssh_dir=fake_ssh_dir)

        # Act
        result = git_service.get_ssh_keys()

        # Assert
        assert result["publicKey"] is None
        assert result["privateKey"] is None
        assert result["fingerprint"] is None

    def test_get_ssh_keys_exist(self, tmp_path):
        """Testing：Get存At的 SSH Keys"""
        # Arrange - Use臨時Catalog作為 SSH Catalog
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        private_key = "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
        # Use a valid SSH RSA public key (this is a real but test key, the padding is correct)
        public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDZnK9Q7k8J5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L5J8L test@example.com"

        private_key_path = fake_ssh_dir / "id_rsa"
        public_key_path = fake_ssh_dir / "id_rsa.pub"

        private_key_path.write_text(private_key)
        public_key_path.write_text(public_key)

        with patch('app.services.template_git_service.get_settings') as mock_settings:
            mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
            git_service = TemplateGitService(ssh_dir=fake_ssh_dir)

        # Act
        result = git_service.get_ssh_keys()

        # Assert
        assert result["privateKey"] == private_key
        assert result["publicKey"] == public_key
        assert result["fingerprint"] is not None

    def test_delete_ssh_keys(self, tmp_path):
        """Testing：Delete SSH Keys"""
        # Arrange - Use臨時Catalog作為 SSH Catalog
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        private_key_path = fake_ssh_dir / "id_rsa"
        public_key_path = fake_ssh_dir / "id_rsa.pub"

        private_key_path.write_text("private key")
        public_key_path.write_text("public key")

        with patch('app.services.template_git_service.get_settings') as mock_settings:
            mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
            git_service = TemplateGitService(ssh_dir=fake_ssh_dir)

        # Act
        git_service.delete_ssh_keys()

        # Assert
        assert not private_key_path.exists()
        assert not public_key_path.exists()


# ============================================================================
# Clone Repository Tests
# ============================================================================

@pytest.mark.unit
class TestCloneRepository:
    """克隆倉庫Testing"""

    def test_clone_repository_empty_url(self, git_service):
        """Testing：空 URL 克隆Unsuccessfully"""
        # Act
        result = git_service.clone_repository("")

        # Assert
        assert result.success is False
        assert result.code == "GIT_REMOTE_URL_EMPTY"

    def test_clone_repository_already_exists_with_changes(self, git_service, mock_repo):
        """Testing：已存At有Change的倉庫克隆Unsuccessfully"""
        # Arrange
        with patch.object(git_service, 'is_git_repository', return_value=True), \
             patch.object(git_service, '_get_repo', return_value=mock_repo), \
             patch.object(git_service, 'get_git_status') as mock_status:

            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=True,
                ahead_count=0,
                behind_count=0,
                remote_url="https://github.com/user/repo.git",
                is_git_repo=True
            )

            # Act
            result = git_service.clone_repository("https://github.com/user/repo.git")

            # Assert
            assert result.success is False
            assert result.code == "GIT_CLONE_TARGET_HAS_CHANGES"


# ============================================================================
# Registry Flow Tests
# ============================================================================

@pytest.mark.unit
class TestRegistryFlow:
    """canonical registry Git flow Testing"""

    def test_bootstrap_registry_rejects_non_empty_templates_dir(self, git_service, tmp_path):
        registry_dir = tmp_path / "templates"
        registry_dir.mkdir(parents=True, exist_ok=True)
        (registry_dir / "existing-template").mkdir()

        result = git_service.bootstrap_registry("https://github.com/example/repo.git")

        assert result.success is False
        assert result.code == "GIT_BOOTSTRAP_TARGET_NOT_EMPTY"

    def test_bootstrap_registry_uses_clone_repository(self, git_service):
        with patch.object(git_service, "clone_repository") as mock_clone:
            mock_clone.return_value = GitOperationResult(True, "GIT_CLONE_SUCCESS", "GIT_CLONE_SUCCESS")

            result = git_service.bootstrap_registry("https://github.com/example/repo.git", branch="main")

        assert result.success is True
        mock_clone.assert_called_once_with(url="https://github.com/example/repo.git", branch="main")

    def test_refresh_registry_requires_clean_repo(self, git_service):
        with patch.object(git_service, "is_git_repository", return_value=True), \
             patch.object(git_service, "get_git_status") as mock_status:
            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=True,
                ahead_count=0,
                behind_count=0,
                remote_url="https://github.com/example/repo.git",
                is_git_repo=True,
            )

            result = git_service.refresh_registry()

        assert result.success is False
        assert result.code == "GIT_REFRESH_HAS_CHANGES"

    def test_refresh_registry_pulls_remote_when_clean(self, git_service):
        with patch.object(git_service, "is_git_repository", return_value=True), \
             patch.object(git_service, "get_git_status") as mock_status, \
             patch.object(git_service, "_pull_or_clone_existing") as mock_pull:
            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=False,
                ahead_count=0,
                behind_count=0,
                remote_url="https://github.com/example/repo.git",
                is_git_repo=True,
            )
            mock_pull.return_value = GitOperationResult(True, "GIT_CLONE_UPDATE_SUCCESS", "GIT_CLONE_UPDATE_SUCCESS")

            result = git_service.refresh_registry(branch="main")

        assert result.success is True
        mock_pull.assert_called_once_with("https://github.com/example/repo.git", "main")

    def test_publish_registry_uses_file_level_commit_and_remote_push(self, git_service):
        mock_commit_response = MagicMock()
        mock_commit_response.commit.id = "abcdef123456"
        mock_commit_response.commit.message = "sync registry"
        mock_commit_response.commit.branch = "main"

        with patch.object(git_service, "_get_repo", return_value=MagicMock()) as mock_repo, \
             patch.object(git_service, "get_git_status") as mock_status, \
             patch.object(git_service, "commit", return_value=mock_commit_response) as mock_commit, \
             patch.object(git_service, "push") as mock_push:
            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=True,
                ahead_count=0,
                behind_count=0,
                remote_url="https://github.com/example/repo.git",
                is_git_repo=True,
            )
            result = git_service.publish_registry("sync registry", branch="main")

        assert result.success is True
        mock_repo.return_value.git.add.assert_called_once_with("--all")
        mock_commit.assert_called_once_with(message="sync registry")
        mock_push.assert_called_once()


# ============================================================================
# Scan Templates Tests
# ============================================================================

@pytest.mark.unit
class TestScanTemplates:
    """掃描TemplateTesting"""

    def test_scan_templates_no_plugins_dir(self, git_service, tmp_path):
        """Testing：無 templates Catalog掃描Unsuccessfully"""
        # Act
        result = git_service.scan_and_sync_templates()

        # Assert
        assert result.success is False
        assert result.code == "GIT_PLUGINS_DIR_MISSING"
        assert len(result.templates) == 0

    def test_scan_templates_success(self, git_service, tmp_path):
        """Testing：掃描TemplateSuccessfully"""
        # Arrange
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_dir = templates_dir / "test-template"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "template.yaml").write_text(
            "\n".join(
                [
                    "id: test-template",
                    "name: Test Template",
                    "description: A test template",
                    "version: 1.0.0",
                    "schemaVersion: v0",
                    "metadata:",
                    "  author:",
                    "    name: Test Author",
                    "    email: test@example.com",
                    "  category: general",
                    "  keywords:",
                    "    - test",
                ]
            ),
            encoding="utf-8",
        )

        # Act
        result = git_service.scan_and_sync_templates()

        # Assert
        assert result.success is True
        assert result.code == "GIT_SCAN_SUCCESS"
        assert len(result.templates) == 1
        assert result.templates[0]["id"] == "test-template"
        assert result.templates[0]["name"] == "Test Template"

    def test_scan_templates_supports_canonical_template_yaml(self, git_service, tmp_path):
        """Testing：掃描優先Supporting canonical template.yaml"""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_dir = templates_dir / "canonical-template"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "template.yaml").write_text(
            "\n".join(
                [
                    "id: canonical-template",
                    "name: Canonical Template",
                    "version: 2.0.0",
                    "description: Canonical source",
                    "schemaVersion: v0",
                    "supportedTargets:",
                    "  - codex",
                    "metadata:",
                    "  import:",
                    "    sourceType: gemini",
                    "  author:",
                    "    name: Canonical Author",
                    "    email: author@example.com",
                    "  keywords:",
                    "    - canonical",
                    "  status: draft",
                ]
            ),
            encoding="utf-8",
        )

        result = git_service.scan_and_sync_templates()

        assert result.success is True
        assert result.templates[0]["id"] == "canonical-template"
        assert result.templates[0]["name"] == "Canonical Template"
        assert result.templates[0]["cli_type"] == "gemini"
        assert result.templates[0]["status"] == "draft"

    def test_scan_templates_ignores_legacy_plugins_root(self, git_service, tmp_path):
        """Testing：存At templates/ 與 plugins/ 時只掃描 templates/"""
        templates_dir = tmp_path / "templates"
        plugins_dir = tmp_path / "plugins"
        templates_dir.mkdir(parents=True, exist_ok=True)
        plugins_dir.mkdir(parents=True, exist_ok=True)

        canonical_dir = templates_dir / "canonical-template"
        canonical_dir.mkdir(parents=True, exist_ok=True)
        (canonical_dir / "template.yaml").write_text(
            "id: canonical-template\nname: Canonical\nversion: 1.0.0\nschemaVersion: v0\n",
            encoding="utf-8",
        )

        legacy_dir = plugins_dir / "legacy-template" / ".claude-plugin"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / "plugin.json").write_text(
            json.dumps({"id": "legacy-template", "name": "Legacy Template"}),
            encoding="utf-8",
        )

        result = git_service.scan_and_sync_templates()

        assert result.success is True
        assert len(result.templates) == 1
        assert result.templates[0]["id"] == "canonical-template"

    def test_scan_templates_invalid_yaml(self, git_service, tmp_path):
        """Testing：Invalid YAML 跳過Template"""
        # Arrange
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_dir = templates_dir / "invalid-template"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "template.yaml").write_text("invalid: [yaml", encoding="utf-8")

        # Act
        result = git_service.scan_and_sync_templates()

        # Assert
        assert result.success is False
        assert result.code == "GIT_NO_TEMPLATES_FOUND"
        assert len(result.templates) == 0


# ============================================================================
# Conflict Check Tests
# ============================================================================

@pytest.mark.unit
class TestConflictCheck:
    """衝突CheckTesting"""

    def test_check_conflicts_not_a_repo(self, git_service):
        """Testing：非 Git 倉庫無衝突"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            has_conflicts, conflict_files = git_service.check_conflicts()

            # Assert
            assert has_conflicts is False
            assert len(conflict_files) == 0

    def test_check_conflicts_no_conflicts(self, git_service, mock_repo):
        """Testing：無衝突"""
        # Arrange
        mock_repo.index.entries = {}

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            has_conflicts, conflict_files = git_service.check_conflicts()

            # Assert
            assert has_conflicts is False
            assert len(conflict_files) == 0
