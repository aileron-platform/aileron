"""模板 Git 版本控制服務"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml
from git import Repo, GitCommandError, InvalidGitRepositoryError
from git.util import Actor

from app.config.settings import get_settings
from app.models.template_git import (
    GitBranch,
    GitBranchList,
    GitChangeLog,
    GitStatus,
    TemplateChange,
    GitUserConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class GitOperationResult:
    success: bool
    code: str
    message: str
    params: dict[str, Any] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Any]:
        yield self.success
        yield self.message


@dataclass
class GitScanResult(GitOperationResult):
    templates: List[Dict[str, Any]] = field(default_factory=list)

    def __iter__(self) -> Iterator[Any]:
        yield self.success
        yield self.message
        yield self.templates


class TemplateGitService:
    """管理模板中心的 Git 版本控制操作"""

    def __init__(self, ssh_dir: Optional[Path] = None):
        """初始化 Git 服務

        Args:
            ssh_dir: SSH 目錄路徑，如果為 None 則使用默認的 ~/.ssh
                   主要用於單元測試中進行隔離測試
        """
        # 動態獲取 settings，確保在測試環境中使用正確的配置
        current_settings = get_settings()
        self.template_center_path = Path(current_settings.TEMPLATE_STORAGE_PATH)
        self._ssh_dir = ssh_dir or (Path.home() / ".ssh")
        self._repo: Optional[Repo] = None

    @staticmethod
    def _operation_result(
        success: bool,
        code: str,
        *,
        params: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> GitOperationResult:
        return GitOperationResult(success, code, message or code, params or {})

    @staticmethod
    def _scan_result(
        success: bool,
        code: str,
        *,
        templates: Optional[List[Dict[str, Any]]] = None,
        params: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> GitScanResult:
        return GitScanResult(success, code, message or code, params=params or {}, templates=templates or [])

    def _get_repo(self) -> Optional[Repo]:
        """取得 Git 倉庫物件，如果不存在則返回 None"""
        if self._repo is not None:
            return self._repo

        try:
            self._repo = Repo(str(self.template_center_path))
            return self._repo
        except InvalidGitRepositoryError:
            return None
        except Exception as e:
            logger.error(f"取得 Git 倉庫失敗: {e}")
            return None

    def is_git_repository(self) -> bool:
        """檢查是否為 Git 倉庫"""
        return self._get_repo() is not None

    def get_git_status(self) -> GitStatus:
        """取得 Git 倉庫狀態"""
        repo = self._get_repo()
        if repo is None:
            return GitStatus(
                current_branch="",
                has_changes=False,
                ahead_count=0,
                behind_count=0,
                remote_url=None,
                is_git_repo=False,
            )

        try:
            # 取得當前分支
            current_branch = repo.active_branch.name if repo.head.is_detached is False else "detached"

            # 檢查是否有變更
            has_changes = bool(repo.index.diff(None)) or bool(repo.untracked_files)

            # 取得遠端 URL
            remote_url = None
            try:
                if repo.remotes:
                    remote_url = repo.remotes.origin.url
            except (AttributeError, IndexError):
                pass

            # 取得 ahead/behind 數量
            ahead_count = 0
            behind_count = 0
            if remote_url:
                try:
                    # Fetch 更新遠端狀態
                    repo.remotes.origin.fetch()

                    # 計算 ahead/behind
                    try:
                        commits_behind = list(repo.iter_commits(f'{current_branch}..origin/{current_branch}'))
                        commits_ahead = list(repo.iter_commits(f'origin/{current_branch}..{current_branch}'))
                        behind_count = len(commits_behind)
                        ahead_count = len(commits_ahead)
                    except GitCommandError:
                        # 分支可能不存在於遠端
                        pass
                except Exception as e:
                    logger.warning(f"無法 fetch 遠端狀態: {e}")

            return GitStatus(
                current_branch=current_branch,
                has_changes=has_changes,
                ahead_count=ahead_count,
                behind_count=behind_count,
                remote_url=remote_url,
                is_git_repo=True,
            )
        except Exception as e:
            logger.error(f"取得 Git 狀態失敗: {e}")
            return GitStatus(
                current_branch="unknown",
                has_changes=False,
                ahead_count=0,
                behind_count=0,
                remote_url=None,
                is_git_repo=True,
            )

    def get_change_log(self) -> GitChangeLog:
        """取得變更記錄（按模板分組）"""
        repo = self._get_repo()
        if repo is None:
            return GitChangeLog(
                templates=[],
                total_changes=0,
                has_staged=False,
                has_unstaged=False,
            )

        try:
            # 取得 staged 和 unstaged 變更
            template_changes_dict: Dict[str, TemplateChange] = {}
            has_staged = False
            has_unstaged = False

            # 檢查 staged 變更
            staged_diffs = repo.index.diff("HEAD")
            if staged_diffs:
                has_staged = True

            # 檢查 unstaged 變更
            unstaged_diffs = repo.index.diff(None)
            if unstaged_diffs:
                has_unstaged = True

            # 處理 staged 變更
            for diff_item in staged_diffs:
                self._process_diff_item(diff_item, template_changes_dict, "added")

            # 處理 unstaged 變更
            for diff_item in unstaged_diffs:
                self._process_diff_item(diff_item, template_changes_dict, "modified")

            # 處理 untracked 檔案
            for untracked_file in repo.untracked_files:
                self._process_untracked_file(untracked_file, template_changes_dict)

            templates = list(template_changes_dict.values())

            return GitChangeLog(
                templates=templates,
                total_changes=len(templates),
                has_staged=has_staged,
                has_unstaged=has_unstaged,
            )
        except Exception as e:
            logger.error(f"取得變更記錄失敗: {e}")
            return GitChangeLog(
                templates=[],
                total_changes=0,
                has_staged=False,
                has_unstaged=False,
            )

    def _process_diff_item(self, diff_item: object, template_changes_dict: Dict[str, TemplateChange], default_status: str) -> None:
        """處理單個 diff 項目"""
        file_path = diff_item.b_path or diff_item.a_path or ""

        if not file_path:
            return

        # 判斷變更狀態
        if diff_item.change_type == "A":
            change_status = "added"
        elif diff_item.change_type == "D":
            change_status = "deleted"
        else:
            change_status = default_status

        self._add_to_template_changes(file_path, template_changes_dict, change_status)

    def _process_untracked_file(self, file_path: str, template_changes_dict: Dict[str, TemplateChange]) -> None:
        """處理 untracked 檔案"""
        self._add_to_template_changes(file_path, template_changes_dict, "untracked")

    def _add_to_template_changes(self, file_path: str, template_changes_dict: Dict[str, TemplateChange], change_status: str) -> None:
        """將檔案加入模板變更記錄"""
        # 判斷是否為 templates/ 目錄下的檔案
        if file_path.startswith("templates/"):
            parts = file_path.split("/")
            if len(parts) < 2:
                return

            template_id = parts[1]
            template_name = template_id
            relative_path = "/".join(parts[2:]) if len(parts) > 2 else parts[-1]
            sub_dir = "/".join(parts[2:-1]) if len(parts) > 3 else ""
        else:
            template_id = "__other__"
            template_name = "other"
            relative_path = file_path
            parts = file_path.split("/")
            sub_dir = "/".join(parts[:-1]) if len(parts) > 1 else ""

        # 建立或更新模板變更記錄
        if template_id not in template_changes_dict:
            template_changes_dict[template_id] = TemplateChange(
                template_id=template_id,
                template_name=template_name,
                status=change_status,
                changed_files=[],
                changed_dirs=[],
            )

        template_change = template_changes_dict[template_id]

        if relative_path not in template_change.changed_files:
            template_change.changed_files.append(relative_path)

        if sub_dir and sub_dir not in template_change.changed_dirs:
            template_change.changed_dirs.append(sub_dir)

    def get_user_config(self) -> GitUserConfig:
        """取得 Git 使用者資訊"""
        try:
            from git import GitConfigParser

            with GitConfigParser() as git_config:
                user_name = git_config.get_value("user", "name", None)
                user_email = git_config.get_value("user", "email", None)

            return GitUserConfig(user_name=user_name, user_email=user_email)
        except Exception as e:
            logger.warning(f"取得 Git 使用者資訊失敗: {e}")
            return GitUserConfig(user_name=None, user_email=None)

    def update_user_config(self, user_name: str, user_email: str) -> GitOperationResult:
        """更新 Git 使用者資訊"""
        if not user_name.strip() or not user_email.strip():
            return self._operation_result(False, "GIT_USER_CONFIG_REQUIRED")

        try:
            from git import GitConfigParser

            with GitConfigParser() as git_config:
                git_config.set_value("user", "name", user_name.strip())
                git_config.set_value("user", "email", user_email.strip())
                git_config.release()

            return self._operation_result(True, "GIT_USER_CONFIG_UPDATED")
        except Exception as e:
            logger.error(f"更新 Git 使用者資訊失敗: {e}")
            return self._operation_result(False, "GIT_USER_CONFIG_UPDATE_FAILED")

    def set_remote_url(self, url: str) -> GitOperationResult:
        """設定或更新 Git 遠端倉庫 URL

        Args:
            url: 遠端倉庫 URL (例如: git@github.com:user/repo.git 或 https://github.com/user/repo.git)

        Returns:
            (成功與否, 訊息)
        """
        repo = self._get_repo()
        if repo is None:
            return self._operation_result(False, "GIT_REPO_NOT_FOUND")

        if not url.strip():
            return self._operation_result(False, "GIT_REMOTE_URL_EMPTY")

        url = url.strip()

        try:
            if "origin" in repo.remotes:
                # 已存在，更新 URL
                repo.remotes.origin.set_url(url)
                return self._operation_result(True, "GIT_REMOTE_URL_UPDATED", params={"url": url})
            else:
                # 不存在，新增 origin
                repo.create_remote("origin", url)
                return self._operation_result(True, "GIT_REMOTE_URL_CREATED", params={"url": url})
        except Exception as e:
            logger.error(f"設定遠端倉庫 URL 失敗: {e}")
            return self._operation_result(False, "GIT_REMOTE_URL_SET_FAILED")

    def bootstrap_registry(self, url: str, branch: Optional[str] = None) -> GitOperationResult:
        """初始化 canonical registry。

        僅當 templates/ 目錄為空時允許 clone，避免隱式覆蓋本地內容。
        """
        registry_root = self.template_center_path / "templates"
        registry_root.mkdir(parents=True, exist_ok=True)
        if any(registry_root.iterdir()):
            return self._operation_result(False, "GIT_BOOTSTRAP_TARGET_NOT_EMPTY")
        return self.clone_repository(url=url, branch=branch)

    def refresh_registry(self, branch: Optional[str] = None) -> GitOperationResult:
        """更新 canonical registry，要求目前已是 Git 倉庫且無本地變更。"""
        if not self.is_git_repository():
            return self._operation_result(False, "GIT_REPO_NOT_FOUND")

        status = self.get_git_status()
        if status.has_changes:
            return self._operation_result(False, "GIT_REFRESH_HAS_CHANGES")
        if not status.remote_url:
            return self._operation_result(False, "GIT_PUSH_REMOTE_NOT_CONFIGURED")

        return self._pull_or_clone_existing(status.remote_url, branch)

    def publish_registry(self, message: str, branch: Optional[str] = None) -> GitOperationResult:
        """發布 canonical registry 變更。"""
        return self.commit_and_push(message=message, branch=branch, push=True)

    def get_branches(self) -> GitBranchList:
        """取得分支列表"""
        repo = self._get_repo()
        if repo is None:
            return GitBranchList(branches=[], current_branch="")

        try:
            # 取得當前分支
            current_branch = repo.active_branch.name if repo.head.is_detached is False else "detached"

            # 取得本地分支
            branches = []
            for head in repo.heads:
                branches.append(
                    GitBranch(
                        name=head.name,
                        is_current=(head.name == current_branch),
                        is_remote=False,
                    )
                )

            # 取得遠端分支
            for remote in repo.remotes:
                for ref in remote.refs:
                    branch_name = ref.remote_head
                    # 避免重複（如果本地已有同名分支）
                    if not any(b.name == branch_name for b in branches):
                        branches.append(
                            GitBranch(
                                name=branch_name,
                                is_current=False,
                                is_remote=True,
                            )
                        )

            return GitBranchList(branches=branches, current_branch=current_branch)
        except Exception as e:
            logger.error(f"取得分支列表失敗: {e}")
            return GitBranchList(branches=[], current_branch="unknown")

    def commit_and_push(
        self, message: str, branch: Optional[str] = None, push: bool = True
    ) -> GitOperationResult:
        """提交變更並推送到遠端

        Args:
            message: Commit 訊息
            branch: 目標分支（若為 None 則使用當前分支）
            push: 是否推送到遠端

        Returns:
            (成功與否, 訊息)
        """
        repo = self._get_repo()
        if repo is None:
            return self._operation_result(False, "GIT_REPO_NOT_FOUND")

        try:
            # 檢查是否有變更
            status = self.get_git_status()
            if not status.has_changes:
                return self._operation_result(False, "GIT_NO_CHANGES")

            # 如果需要推送，先檢查是否有設定 remote origin
            if push and not status.remote_url:
                return self._operation_result(False, "GIT_PUSH_REMOTE_NOT_CONFIGURED")

            # 如果指定了分支，先切換分支
            if branch:
                try:
                    repo.heads[branch].checkout()
                except IndexError:
                    return self._operation_result(False, "GIT_BRANCH_NOT_FOUND", params={"branch": branch})

            # 加入所有變更到 staging area
            repo.index.add("*")

            # 提交變更
            commit = repo.index.commit(message)
            commit_info = f"Commit {commit.hexsha[:7]}: {commit.message}"

            # 推送到遠端
            if push:
                try:
                    current_branch = branch or status.current_branch
                    repo.remotes.origin.push(current_branch)
                    return self._operation_result(True, "GIT_COMMIT_PUSH_SUCCESS", params={"commitInfo": commit_info})
                except Exception as e:
                    logger.error(f"推送失敗: {e}")
                    return self._operation_result(False, "GIT_PUSH_FAILED_LOCAL_COMMITTED")

            return self._operation_result(True, "GIT_COMMIT_LOCAL_SUCCESS", params={"commitInfo": commit_info})
        except Exception as e:
            logger.error(f"提交變更失敗: {e}")
            return self._operation_result(False, "GIT_COMMIT_FAILED")

    def pull_from_remote(self, branch: Optional[str] = None) -> GitOperationResult:
        """從遠端拉取變更

        Args:
            branch: 要拉取的分支（若為 None 則使用當前分支）

        Returns:
            (成功與否, 訊息)
        """
        repo = self._get_repo()
        if repo is None:
            return self._operation_result(False, "GIT_REPO_NOT_FOUND")

        try:
            # 檢查是否有未提交的變更
            status = self.get_git_status()
            if status.has_changes:
                return self._operation_result(False, "GIT_PULL_HAS_UNCOMMITTED_CHANGES")

            # 如果指定了分支，先切換分支
            if branch:
                try:
                    repo.heads[branch].checkout()
                except IndexError:
                    return self._operation_result(False, "GIT_BRANCH_NOT_FOUND", params={"branch": branch})

            # 拉取遠端變更
            current_branch = branch or status.current_branch
            try:
                repo.remotes.origin.pull(current_branch)
                return self._operation_result(True, "GIT_PULL_SUCCESS")
            except GitCommandError as e:
                # 檢查是否為衝突
                if "conflict" in str(e).lower():
                    return self._operation_result(False, "GIT_PULL_CONFLICT")
                return self._operation_result(False, "GIT_PULL_FAILED")
        except Exception as e:
            logger.error(f"拉取遠端變更失敗: {e}")
            return self._operation_result(False, "GIT_PULL_FAILED")

    def check_conflicts(self) -> Tuple[bool, List[str]]:
        """檢查是否有衝突

        Returns:
            (有衝突與否, 衝突檔案列表)
        """
        repo = self._get_repo()
        if repo is None:
            return False, []

        try:
            # 檢查是否有未合併的檔案
            conflict_files = []
            for item in repo.index.entries:
                # 檢查 stage 欄位，如果不是 0 表示有衝突
                if repo.index.entries[item].stage != 0:
                    conflict_files.append(item[0])

            return bool(conflict_files), conflict_files
        except Exception as e:
            logger.error(f"檢查衝突失敗: {e}")
            return False, []

    # ============ SSH Keys 管理方法 ============

    def get_ssh_keys(self) -> Dict[str, Optional[str]]:
        """取得當前的 SSH Keys 資訊

        Returns:
            包含 publicKey, privateKey, fingerprint, lastRotatedAt 的字典
        """
        ssh_dir = self._ssh_dir
        private_key_path = ssh_dir / "id_rsa"
        public_key_path = ssh_dir / "id_rsa.pub"

        result = {
            "publicKey": None,
            "privateKey": None,
            "fingerprint": None,
            "lastRotatedAt": None,
        }

        # 讀取私鑰
        if private_key_path.exists():
            try:
                result["privateKey"] = private_key_path.read_text()
                # 取得檔案修改時間
                stat = private_key_path.stat()
                from datetime import datetime
                result["lastRotatedAt"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            except Exception as e:
                logger.error(f"讀取私鑰失敗: {e}")

        # 讀取公鑰
        if public_key_path.exists():
            try:
                result["publicKey"] = public_key_path.read_text().strip()
                # 計算 fingerprint
                result["fingerprint"] = self._calculate_ssh_fingerprint(result["publicKey"])
            except Exception as e:
                logger.error(f"讀取公鑰失敗: {e}")

        return result

    def generate_ssh_keys(self) -> Dict[str, str]:
        """產生新的 SSH Key Pair 並儲存到 ~/.ssh 目錄

        Returns:
            包含 publicKey, privateKey, fingerprint, generatedAt 的字典
        """
        import tempfile
        from datetime import datetime

        # 使用臨時目錄產生金鑰
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "id_rsa"

            # 使用 ssh-keygen 產生金鑰
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-t", "rsa",
                    "-b", "4096",
                    "-f", str(key_path),
                    "-N", "",
                    "-C", f"template-center-{datetime.utcnow().isoformat()}"
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise Exception("SSH_KEY_GENERATION_FAILED")

            # 讀取私鑰和公鑰
            private_key = key_path.read_text()
            public_key = key_path.with_suffix(".pub").read_text().strip()

        # 計算 fingerprint
        fingerprint = self._calculate_ssh_fingerprint(public_key)

        # 寫入到 SSH 目錄
        ssh_dir = self._ssh_dir
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        # 寫入私鑰（確保結尾有換行）
        private_key_path = ssh_dir / "id_rsa"
        private_key_content = private_key if private_key.endswith('\n') else private_key + '\n'
        private_key_path.write_text(private_key_content)
        private_key_path.chmod(0o600)

        # 寫入公鑰
        public_key_path = ssh_dir / "id_rsa.pub"
        public_key_path.write_text(public_key + "\n")
        public_key_path.chmod(0o644)

        logger.info(f"SSH Keys 已產生並儲存到 {ssh_dir}")

        generated_at = datetime.utcnow().isoformat()

        return {
            "publicKey": public_key,
            "privateKey": private_key,
            "fingerprint": fingerprint,
            "generatedAt": generated_at,
        }

    def update_ssh_keys(self, private_key: str, public_key: str) -> Dict[str, str]:
        """更新 SSH Keys 到 ~/.ssh 目錄

        Args:
            private_key: 私鑰內容
            public_key: 公鑰內容

        Returns:
            包含 publicKey, privateKey, fingerprint, updatedAt 的字典
        """
        from datetime import datetime

        # 驗證私鑰格式
        if not private_key.strip().startswith("-----BEGIN"):
            raise ValueError("SSH_PRIVATE_KEY_INVALID")

        # 驗證公鑰格式
        if not public_key.strip().startswith("ssh-"):
            raise ValueError("SSH_PUBLIC_KEY_INVALID")

        # 計算 fingerprint
        fingerprint = self._calculate_ssh_fingerprint(public_key.strip())

        # 寫入到 SSH 目錄
        ssh_dir = self._ssh_dir
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        # 寫入私鑰（確保結尾有換行）
        private_key_path = ssh_dir / "id_rsa"
        private_key_content = private_key if private_key.endswith('\n') else private_key + '\n'
        private_key_path.write_text(private_key_content)
        private_key_path.chmod(0o600)

        # 寫入公鑰
        public_key_path = ssh_dir / "id_rsa.pub"
        public_key_path.write_text(public_key.strip() + "\n")
        public_key_path.chmod(0o644)

        logger.info(f"SSH Keys 已更新並儲存到 {ssh_dir}")

        updated_at = datetime.utcnow().isoformat()

        return {
            "publicKey": public_key.strip(),
            "privateKey": private_key,
            "fingerprint": fingerprint,
            "updatedAt": updated_at,
        }

    def delete_ssh_keys(self) -> None:
        """刪除 SSH 目錄下的 SSH Keys"""
        ssh_dir = self._ssh_dir
        private_key_path = ssh_dir / "id_rsa"
        public_key_path = ssh_dir / "id_rsa.pub"

        # 刪除私鑰
        if private_key_path.exists():
            private_key_path.unlink()
            logger.info(f"已刪除私鑰: {private_key_path}")

        # 刪除公鑰
        if public_key_path.exists():
            public_key_path.unlink()
            logger.info(f"已刪除公鑰: {public_key_path}")

    @staticmethod
    def _calculate_ssh_fingerprint(public_key: str) -> str:
        """計算 SSH 公鑰的 fingerprint (SHA256)"""
        import base64
        import hashlib

        # 取得公鑰的 base64 部分
        parts = public_key.split()
        if len(parts) < 2:
            return ""

        key_data = base64.b64decode(parts[1])

        # 計算 SHA256 hash
        sha256_hash = hashlib.sha256(key_data).digest()

        # 轉換為 base64 並移除 padding
        fingerprint = base64.b64encode(sha256_hash).decode().rstrip("=")

        return f"SHA256:{fingerprint}"

    def clone_repository(self, url: str, branch: Optional[str] = None) -> GitOperationResult:
        """Clone 遠端倉庫到模板中心目錄

        Args:
            url: 遠端倉庫 URL (例如: git@github.com:user/repo.git 或 https://github.com/user/repo.git)
            branch: 要 clone 的分支（可選）

        Returns:
            (成功與否, 訊息)
        """
        if not url.strip():
            return self._operation_result(False, "GIT_REMOTE_URL_EMPTY")

        url = url.strip()

        # 檢查目標目錄是否已是 Git 倉庫
        if self.is_git_repository():
            repo = self._get_repo()
            if repo is None:
                return self._operation_result(False, "GIT_REPO_ACCESS_FAILED")

            # 如果已經是 Git 倉庫，檢查是否有未提交的變更
            status = self.get_git_status()
            if status.has_changes:
                return self._operation_result(False, "GIT_CLONE_TARGET_HAS_CHANGES")

            # 檢查 remote URL 是否相同
            try:
                existing_url = repo.remotes.origin.url if "origin" in repo.remotes else None
            except Exception:
                existing_url = None

            if existing_url == url:
                # URL 相同，執行 pull
                return self._pull_or_clone_existing(url, branch)
            else:
                # URL 不同，提示用戶
                return self._operation_result(
                    False,
                    "GIT_CLONE_REMOTE_MISMATCH",
                    params={"currentUrl": existing_url or "(not configured)", "newUrl": url},
                )

        # 目標目錄不是 Git 倉庫，執行 clone
        return self._clone_fresh(url, branch)

    def _clone_fresh(self, url: str, branch: Optional[str] = None) -> GitOperationResult:
        """Clone 倉庫到空目錄"""
        import shutil
        import tempfile

        try:
            # 建立臨時目錄作為 clone 的父目錄
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_clone_path = Path(tmpdir) / "repo"

                # 使用 GitPython 進行 clone
                try:
                    if branch:
                        Repo.clone_from(url, str(tmp_clone_path), branch=branch)
                    else:
                        Repo.clone_from(url, str(tmp_clone_path))
                except Exception as e:
                    logger.error(f"GitPython clone 失敗: {e}")
                    return self._operation_result(False, "GIT_CLONE_FAILED")

                # 移動檔案到目標目錄
                # 先清空目標目錄（除了 .gitkeep）
                for item in self.template_center_path.iterdir():
                    if item.name not in ['.git', '.gitkeep']:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()

                # 複製 clone 的內容到目標目錄
                for item in tmp_clone_path.iterdir():
                    src = item
                    dst = self.template_center_path / item.name
                    if src.is_dir():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)

                # 清除舊的 repo 快取
                self._repo = None

            detail = f"{url}" + (f" (branch: {branch})" if branch else "")
            return self._operation_result(True, "GIT_CLONE_SUCCESS", params={"detail": detail})

        except Exception as e:
            logger.error(f"Clone 倉庫時發生錯誤: {e}")
            return self._operation_result(False, "GIT_CLONE_FAILED")

    def _pull_or_clone_existing(self, url: str, branch: Optional[str] = None) -> GitOperationResult:
        """對已存在的倉庫執行 pull 操作"""
        repo = self._get_repo()
        if repo is None:
            return self._operation_result(False, "GIT_REPO_ACCESS_FAILED")

        try:
            # 如果指定了分支，切換分支
            if branch:
                try:
                    repo.heads[branch].checkout()
                except IndexError:
                    # 嘗試從遠端 checkout
                    try:
                        repo.create_head(branch, f"origin/{branch}")
                        repo.heads[branch].checkout()
                    except Exception as e:
                        return self._operation_result(False, "GIT_CHECKOUT_BRANCH_FAILED", params={"branch": branch})

            # 執行 pull
            current_branch = branch or self.get_git_status().current_branch
            try:
                repo.remotes.origin.pull(current_branch)
            except GitCommandError as e:
                return self._operation_result(False, "GIT_PULL_FAILED")

            detail = f"{url}" + (f" (branch: {branch})" if branch else "")
            return self._operation_result(True, "GIT_CLONE_UPDATE_SUCCESS", params={"detail": detail})

        except Exception as e:
            logger.error(f"Pull 倉庫時發生錯誤: {e}")
            return self._operation_result(False, "GIT_PULL_FAILED")

    def scan_and_sync_templates(self) -> GitScanResult:
        """掃描模板中心目錄中的 canonical 模板並返回模板資訊

        Returns:
            (成功與否, 訊息, 掃描到的模板列表)
        """
        try:
            templates = []
            templates_root = self._get_scan_templates_root()
            if templates_root is None:
                return self._scan_result(False, "GIT_PLUGINS_DIR_MISSING")

            # 掃描每個插件目錄
            for plugin_dir in templates_root.iterdir():
                if not plugin_dir.is_dir():
                    continue

                template_yaml_path = plugin_dir / "template.yaml"

                try:
                    if template_yaml_path.exists():
                        template_info = self._load_canonical_template_info(plugin_dir, template_yaml_path)
                    else:
                        logger.warning("找不到 canonical template.yaml: %s", plugin_dir)
                        continue

                    templates.append(template_info)
                    logger.info(f"成功掃描模板: {template_info['id']}")

                except json.JSONDecodeError as e:
                    logger.error("解析 template.yaml 失敗 (%s): %s", template_yaml_path, e)
                except Exception as e:
                    logger.error(f"掃描模板失敗 ({plugin_dir.name}): {e}")

            if not templates:
                return self._scan_result(False, "GIT_NO_TEMPLATES_FOUND")

            return self._scan_result(True, "GIT_SCAN_SUCCESS", params={"count": len(templates)}, templates=templates)

        except Exception as e:
            logger.error(f"掃描模板時發生錯誤: {e}")
            return self._scan_result(False, "GIT_SCAN_FAILED")

    def _get_scan_templates_root(self) -> Optional[Path]:
        canonical_root = self.template_center_path / "templates"
        if canonical_root.exists():
            return canonical_root
        return None

    def _load_canonical_template_info(self, plugin_dir: Path, template_yaml_path: Path) -> Dict[str, Any]:
        with open(template_yaml_path, "r", encoding="utf-8") as f:
            template_data = yaml.safe_load(f) or {}

        metadata = template_data.get("metadata") or {}
        author = metadata.get("author") or {}
        keywords = metadata.get("keywords") or []
        supported_targets = template_data.get("supportedTargets") or []
        import_metadata = metadata.get("import") or {}
        cli_type = import_metadata.get("sourceType") or (supported_targets[0] if supported_targets else "claude-code")

        return {
            "id": template_data.get("id", plugin_dir.name),
            "name": template_data.get("name", plugin_dir.name),
            "description": template_data.get("description", ""),
            "version": template_data.get("version", "1.0.0"),
            "author_name": author.get("name", ""),
            "author_email": author.get("email", ""),
            "author_url": author.get("url", ""),
            "category": metadata.get("category", "general"),
            "keywords": keywords if isinstance(keywords, list) else [],
            "cli_type": cli_type,
            "status": metadata.get("status", "released"),
        }
