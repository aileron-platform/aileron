"""TemplateGitService 單元測試"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from git import GitCommandError, InvalidGitRepositoryError

from app.models.template_git import (
    GitBranch,
    GitBranchList,
    GitChangeLog,
    GitStatus,
    GitUserConfig,
    TemplateChange,
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
    """TemplateGitService 實例"""
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
    """倉庫檢測測試"""

    def test_is_git_repository_true(self, git_service, mock_repo):
        """測試：檢測到 Git 倉庫"""
        # Arrange
        with patch('app.services.template_git_service.Repo') as mock_repo_class:
            mock_repo_class.return_value = mock_repo

            # Act
            result = git_service.is_git_repository()

            # Assert
            assert result is True

    def test_is_git_repository_false(self, git_service):
        """測試：未檢測到 Git 倉庫"""
        # Arrange
        with patch('app.services.template_git_service.Repo') as mock_repo_class:
            mock_repo_class.side_effect = InvalidGitRepositoryError("Not a git repo")

            # Act
            result = git_service.is_git_repository()

            # Assert
            assert result is False


# ============================================================================
# Git Status Tests
# ============================================================================

@pytest.mark.unit
class TestGitStatus:
    """Git 狀態測試"""

    def test_get_git_status_not_a_repo(self, git_service):
        """測試：非 Git 倉庫返回預設狀態"""
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
        """測試：乾淨的倉庫狀態"""
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
        """測試：有變更的倉庫狀態"""
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
        """測試：有未追蹤檔案的倉庫狀態"""
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
        """測試：含遠端的倉庫狀態"""
        # Arrange
        mock_remote = MagicMock()
        mock_remote.url = "https://github.com/user/repo.git"
        mock_remote.fetch.return_value = None

        # 創建一個 MagicMock remotes 對象，既可以迭代又有 origin 屬性
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


# ============================================================================
# Change Log Tests
# ============================================================================

@pytest.mark.unit
class TestChangeLog:
    """變更記錄測試"""

    def test_get_change_log_not_a_repo(self, git_service):
        """測試：非 Git 倉庫返回空變更記錄"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.get_change_log()

            # Assert
            assert isinstance(result, GitChangeLog)
            assert result.total_changes == 0
            assert result.has_staged is False
            assert result.has_unstaged is False

    def test_get_change_log_with_staged_changes(self, git_service, mock_repo):
        """測試：含 staged 變更的記錄"""
        # Arrange
        mock_diff = MagicMock()
        mock_diff.change_type = "M"
        mock_diff.b_path = "templates/test-template/test.py"
        mock_diff.a_path = "templates/test-template/test.py"

        mock_repo.index.diff.side_effect = [[mock_diff], []]
        mock_repo.untracked_files = []

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_change_log()

            # Assert
            assert result.has_staged is True
            assert result.total_changes > 0

    def test_get_change_log_with_untracked_files(self, git_service, mock_repo):
        """測試：含未追蹤檔案的記錄"""
        # Arrange
        mock_repo.index.diff.side_effect = [[], []]
        mock_repo.untracked_files = ["templates/test-template/newfile.py"]

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_change_log()

            # Assert
            assert result.total_changes > 0

    def test_process_diff_item_added(self, git_service):
        """測試：處理新增的檔案"""
        # Arrange
        mock_diff = MagicMock()
        mock_diff.change_type = "A"
        mock_diff.b_path = "templates/test-template/new.py"
        mock_diff.a_path = None

        template_changes_dict = {}

        # Act
        git_service._process_diff_item(mock_diff, template_changes_dict, "added")

        # Assert
        assert "test-template" in template_changes_dict
        assert template_changes_dict["test-template"].status == "added"

    def test_process_diff_item_deleted(self, git_service):
        """測試：處理刪除的檔案"""
        # Arrange
        mock_diff = MagicMock()
        mock_diff.change_type = "D"
        mock_diff.b_path = None
        mock_diff.a_path = "templates/test-template/deleted.py"

        template_changes_dict = {}

        # Act
        git_service._process_diff_item(mock_diff, template_changes_dict, "deleted")

        # Assert
        assert "test-template" in template_changes_dict
        assert template_changes_dict["test-template"].status == "deleted"


# ============================================================================
# User Config Tests
# ============================================================================

@pytest.mark.unit
class TestUserConfig:
    """使用者配置測試"""

    def test_get_user_config_success(self, git_service):
        """測試：取得使用者配置成功"""
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
        """測試：取得使用者配置失敗返回 None"""
        # Arrange
        with patch('git.GitConfigParser') as mock_parser_class:
            mock_parser_class.side_effect = Exception("Config error")

            # Act
            result = git_service.get_user_config()

            # Assert
            assert result.user_name is None
            assert result.user_email is None

    def test_update_user_config_success(self, git_service):
        """測試：更新使用者配置成功"""
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
        """測試：更新使用者配置時空值失敗"""
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
    """遠端 URL 測試"""

    def test_set_remote_url_not_a_repo(self, git_service):
        """測試：非 Git 倉庫設定遠端 URL 失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.set_remote_url("https://github.com/user/repo.git")

            # Assert
            assert result.success is False
            assert result.code == "GIT_REPO_NOT_FOUND"

    def test_set_remote_url_empty(self, git_service, mock_repo):
        """測試：設定空 URL 失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.set_remote_url("")

            # Assert
            assert result.success is False
            assert result.code == "GIT_REMOTE_URL_EMPTY"

    def test_set_remote_url_create_new(self, git_service, mock_repo):
        """測試：建立新的遠端 URL"""
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
        """測試：更新現有遠端 URL"""
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
# Branch Tests
# ============================================================================

@pytest.mark.unit
class TestBranches:
    """分支測試"""

    def test_get_branches_not_a_repo(self, git_service):
        """測試：非 Git 倉庫返回空分支列表"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.get_branches()

            # Assert
            assert isinstance(result, GitBranchList)
            assert len(result.branches) == 0
            assert result.current_branch == ""

    def test_get_branches_with_local_branches(self, git_service, mock_repo):
        """測試：取得本地分支"""
        # Arrange
        mock_head1 = MagicMock()
        mock_head1.name = "main"
        mock_head2 = MagicMock()
        mock_head2.name = "develop"

        mock_repo.heads = [mock_head1, mock_head2]
        mock_repo.remotes = []

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            result = git_service.get_branches()

            # Assert
            assert len(result.branches) == 2
            assert result.current_branch == "main"
            branch_names = [b.name for b in result.branches]
            assert "main" in branch_names
            assert "develop" in branch_names


# ============================================================================
# Commit and Push Tests
# ============================================================================

@pytest.mark.unit
class TestCommitAndPush:
    """提交和推送測試"""

    def test_commit_and_push_not_a_repo(self, git_service):
        """測試：非 Git 倉庫提交失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.commit_and_push("Test commit")

            # Assert
            assert result.success is False
            assert result.code == "GIT_REPO_NOT_FOUND"

    def test_commit_and_push_no_changes(self, git_service, mock_repo):
        """測試：無變更時提交失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=mock_repo), \
             patch.object(git_service, 'get_git_status') as mock_status:

            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=False,
                ahead_count=0,
                behind_count=0,
                remote_url=None,
                is_git_repo=True
            )

            # Act
            result = git_service.commit_and_push("Test commit")

            # Assert
            assert result.success is False
            assert result.code == "GIT_NO_CHANGES"

    def test_commit_and_push_no_remote(self, git_service, mock_repo):
        """測試：無遠端時推送失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=mock_repo), \
             patch.object(git_service, 'get_git_status') as mock_status:

            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=True,
                ahead_count=0,
                behind_count=0,
                remote_url=None,
                is_git_repo=True
            )

            # Act
            result = git_service.commit_and_push("Test commit", push=True)

            # Assert
            assert result.success is False
            assert result.code == "GIT_PUSH_REMOTE_NOT_CONFIGURED"

    def test_commit_and_push_success_no_push(self, git_service, mock_repo):
        """測試：提交成功但不推送"""
        # Arrange
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_commit.message = "Test commit"
        mock_repo.index.commit.return_value = mock_commit

        with patch.object(git_service, '_get_repo', return_value=mock_repo), \
             patch.object(git_service, 'get_git_status') as mock_status:

            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=True,
                ahead_count=0,
                behind_count=0,
                remote_url=None,
                is_git_repo=True
            )

            # Act
            result = git_service.commit_and_push("Test commit", push=False)

            # Assert
            assert result.success is True
            assert result.code == "GIT_COMMIT_LOCAL_SUCCESS"
            assert "Commit abc123" in result.params["commitInfo"]
            mock_repo.index.add.assert_called_once()
            mock_repo.index.commit.assert_called_once_with("Test commit")

    def test_commit_and_push_success_with_push(self, git_service, mock_repo):
        """測試：提交並推送成功"""
        # Arrange
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_commit.message = "Test commit"
        mock_repo.index.commit.return_value = mock_commit

        mock_remote = MagicMock()
        mock_repo.remotes.origin = mock_remote

        with patch.object(git_service, '_get_repo', return_value=mock_repo), \
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
            result = git_service.commit_and_push("Test commit", push=True)

            # Assert
            assert result.success is True
            assert result.code == "GIT_COMMIT_PUSH_SUCCESS"
            mock_remote.push.assert_called_once()


# ============================================================================
# Pull Tests
# ============================================================================

@pytest.mark.unit
class TestPull:
    """拉取測試"""

    def test_pull_not_a_repo(self, git_service):
        """測試：非 Git 倉庫拉取失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            result = git_service.pull_from_remote()

            # Assert
            assert result.success is False
            assert result.code == "GIT_REPO_NOT_FOUND"

    def test_pull_with_uncommitted_changes(self, git_service, mock_repo):
        """測試：有未提交變更時拉取失敗"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=mock_repo), \
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
            result = git_service.pull_from_remote()

            # Assert
            assert result.success is False
            assert result.code == "GIT_PULL_HAS_UNCOMMITTED_CHANGES"

    def test_pull_success(self, git_service, mock_repo):
        """測試：拉取成功"""
        # Arrange
        mock_remote = MagicMock()
        mock_repo.remotes.origin = mock_remote

        with patch.object(git_service, '_get_repo', return_value=mock_repo), \
             patch.object(git_service, 'get_git_status') as mock_status:

            mock_status.return_value = GitStatus(
                current_branch="main",
                has_changes=False,
                ahead_count=0,
                behind_count=0,
                remote_url="https://github.com/user/repo.git",
                is_git_repo=True
            )

            # Act
            result = git_service.pull_from_remote()

            # Assert
            assert result.success is True
            assert result.code == "GIT_PULL_SUCCESS"
            mock_remote.pull.assert_called_once()


# ============================================================================
# SSH Keys Tests
# ============================================================================

@pytest.mark.unit
class TestSSHKeys:
    """SSH Keys 測試"""

    def test_get_ssh_keys_not_exist(self, tmp_path):
        """測試：SSH Keys 不存在"""
        # Arrange - 使用空的臨時目錄作為 SSH 目錄
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
        """測試：取得存在的 SSH Keys"""
        # Arrange - 使用臨時目錄作為 SSH 目錄
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
        """測試：刪除 SSH Keys"""
        # Arrange - 使用臨時目錄作為 SSH 目錄
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
    """克隆倉庫測試"""

    def test_clone_repository_empty_url(self, git_service):
        """測試：空 URL 克隆失敗"""
        # Act
        result = git_service.clone_repository("")

        # Assert
        assert result.success is False
        assert result.code == "GIT_REMOTE_URL_EMPTY"

    def test_clone_repository_already_exists_with_changes(self, git_service, mock_repo):
        """測試：已存在有變更的倉庫克隆失敗"""
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
    """canonical registry Git flow 測試"""

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

    def test_publish_registry_uses_commit_and_push(self, git_service):
        with patch.object(git_service, "commit_and_push") as mock_commit:
            mock_commit.return_value = GitOperationResult(True, "GIT_PUSH_SUCCESS", "GIT_PUSH_SUCCESS")

            result = git_service.publish_registry("sync registry", branch="main")

        assert result.success is True
        mock_commit.assert_called_once_with(message="sync registry", branch="main", push=True)


# ============================================================================
# Scan Templates Tests
# ============================================================================

@pytest.mark.unit
class TestScanTemplates:
    """掃描模板測試"""

    def test_scan_templates_no_plugins_dir(self, git_service, tmp_path):
        """測試：無 templates 目錄掃描失敗"""
        # Act
        result = git_service.scan_and_sync_templates()

        # Assert
        assert result.success is False
        assert result.code == "GIT_PLUGINS_DIR_MISSING"
        assert len(result.templates) == 0

    def test_scan_templates_success(self, git_service, tmp_path):
        """測試：掃描模板成功"""
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
        """測試：掃描優先支援 canonical template.yaml"""
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
        """測試：存在 templates/ 與 plugins/ 時只掃描 templates/"""
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
        """測試：無效 YAML 跳過模板"""
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
    """衝突檢查測試"""

    def test_check_conflicts_not_a_repo(self, git_service):
        """測試：非 Git 倉庫無衝突"""
        # Arrange
        with patch.object(git_service, '_get_repo', return_value=None):

            # Act
            has_conflicts, conflict_files = git_service.check_conflicts()

            # Assert
            assert has_conflicts is False
            assert len(conflict_files) == 0

    def test_check_conflicts_no_conflicts(self, git_service, mock_repo):
        """測試：無衝突"""
        # Arrange
        mock_repo.index.entries = {}

        with patch.object(git_service, '_get_repo', return_value=mock_repo):

            # Act
            has_conflicts, conflict_files = git_service.check_conflicts()

            # Assert
            assert has_conflicts is False
            assert len(conflict_files) == 0
