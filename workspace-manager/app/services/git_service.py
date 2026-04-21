"""Git 相關服務"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)


class GitBranchLookupError(RuntimeError):
    def __init__(self, message: str, *, code: str, params: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class GitService:
    """處理 Git 相關操作的服務"""

    def __init__(self, ssh_key_path: Optional[Path] = None):
        """
        初始化 Git 服務
        
        Args:
            ssh_key_path: SSH 私鑰路徑，用於認證私有倉庫
        """
        self.ssh_key_path = ssh_key_path

    def get_remote_branches(self, git_url: str) -> List[str]:
        """
        獲取遠端 Git repository 的分支列表

        Args:
            git_url: Git repository URL

        Returns:
            分支名稱列表

        Raises:
            ValueError: 當 Git URL 無效或無法訪問時
            RuntimeError: 當 git 命令執行失敗時
        """
        if not git_url or not git_url.strip():
            raise GitBranchLookupError("Git URL 不能為空", code="WORKSPACE_SETUP_GIT_EMPTY_URL")

        # 清理 URL（移除換行符和空白）
        git_url = git_url.strip()

        # 驗證 Git URL 格式
        if not self._is_valid_git_url(git_url):
            raise GitBranchLookupError(f"無效的 Git URL: {git_url}", code="WORKSPACE_SETUP_GIT_INVALID_URL", params={"gitUrl": git_url})

        try:
            # 準備環境變數
            env = self._prepare_git_env()
            
            # 使用 git ls-remote 獲取遠端分支
            # --heads 只列出分支（不包含 tags）
            cmd = ["git", "ls-remote", "--heads", git_url]
            
            logger.info(f"執行 git ls-remote: {git_url}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"git ls-remote 失敗: {error_msg}")
                
                # 提供更友善的錯誤訊息
                if "Authentication failed" in error_msg or "Permission denied" in error_msg:
                    raise GitBranchLookupError("認證失敗，請確認 SSH key 設定正確或使用公開倉庫", code="WORKSPACE_SETUP_GIT_AUTH_FAILED")
                elif "Could not resolve host" in error_msg:
                    raise GitBranchLookupError("無法解析主機名稱，請檢查網路連線", code="WORKSPACE_SETUP_GIT_RESOLVE_FAILED")
                elif "Repository not found" in error_msg:
                    raise GitBranchLookupError("找不到 repository，請確認 URL 是否正確", code="WORKSPACE_SETUP_GIT_REPOSITORY_NOT_FOUND")
                else:
                    raise GitBranchLookupError(f"無法獲取分支列表: {error_msg}", code="WORKSPACE_SETUP_GIT_FETCH_FAILED")

            # 解析輸出
            branches = self._parse_ls_remote_output(result.stdout)
            
            logger.info(f"成功獲取 {len(branches)} 個分支: {branches}")
            return branches

        except subprocess.TimeoutExpired:
            logger.error(f"git ls-remote 超時: {git_url}")
            raise GitBranchLookupError("獲取分支列表超時，請稍後再試", code="WORKSPACE_SETUP_GIT_TIMEOUT")
        except Exception as e:
            if isinstance(e, GitBranchLookupError):
                raise
            logger.error(f"獲取分支列表時發生錯誤: {e}")
            raise GitBranchLookupError(f"獲取分支列表失敗: {str(e)}", code="WORKSPACE_SETUP_GIT_FETCH_FAILED")

    def _is_valid_git_url(self, url: str) -> bool:
        """
        驗證 Git URL 格式

        支援的格式：
        - https://github.com/user/repo.git
        - https://github.com/user/repo (不帶 .git)
        - git@github.com:user/repo.git
        - git@github.com:user/repo (不帶 .git)
        - git@ssh.dev.azure.com:v3/org/project/repo (Azure DevOps)
        - ssh://git@github.com/user/repo.git
        """
        # HTTPS 格式 (.git 可選)
        if url.startswith(("http://", "https://")):
            return self._is_valid_https_git_url(url)

        # SSH 格式 (git@host:path，.git 可選)
        # 支援一般格式: git@github.com:user/repo.git 或 git@github.com:user/repo
        ssh_pattern = r"^git@[a-zA-Z0-9\-._]+:[a-zA-Z0-9\-._/]+(\.git)?$"

        # Azure DevOps SSH 格式: git@ssh.dev.azure.com:v3/org/project/repo
        azure_ssh_pattern = r"^git@ssh\.dev\.azure\.com:v3/[a-zA-Z0-9\-._]+/[a-zA-Z0-9\-._]+/[a-zA-Z0-9\-._]+(\.git)?$"

        # SSH URL 格式 (ssh://git@host/path，.git 可選)
        ssh_url_pattern = r"^ssh://git@[a-zA-Z0-9\-._]+/[a-zA-Z0-9\-._/]+(\.git)?$"

        return bool(
            re.match(ssh_pattern, url) or
            re.match(azure_ssh_pattern, url) or
            re.match(ssh_url_pattern, url)
        )

    def _is_valid_https_git_url(self, url: str) -> bool:
        """驗證 HTTPS Git URL，允許省略 .git 但排除常見的非 repository 路徑."""
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return False
        if not parsed.netloc or parsed.query or parsed.fragment:
            return False

        path = parsed.path.rstrip('/')
        if not path:
            return False

        segments = [segment for segment in path.split('/') if segment]
        if not segments:
            return False

        repo_segment = segments[-1]
        if repo_segment.endswith('.git'):
            repo_segment = repo_segment[:-4]

        if not repo_segment or not re.match(r"^[a-zA-Z0-9._-]+$", repo_segment):
            return False

        reserved_suffixes = {
            'tree', 'blob', 'raw', 'commit', 'pull', 'pulls', 'issues', 'archive', 'releases', 'compare'
        }
        if len(segments) >= 2 and segments[-2] in reserved_suffixes:
            return False

        allowed_segment = re.compile(r"^[a-zA-Z0-9._-]+$")
        if not all(allowed_segment.match(segment) for segment in segments):
            return False

        return True

    def _prepare_git_env(self) -> dict:
        """準備 Git 命令的環境變數"""
        import os
        
        env = os.environ.copy()
        
        # 如果有提供 SSH key，設定 GIT_SSH_COMMAND
        if self.ssh_key_path and self.ssh_key_path.exists():
            # 使用指定的 SSH key，並禁用 host key 檢查（開發環境）
            ssh_cmd = (
                f"ssh -i {self.ssh_key_path} "
                f"-o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null"
            )
            env["GIT_SSH_COMMAND"] = ssh_cmd
            logger.debug(f"使用 SSH key: {self.ssh_key_path}")
        
        return env

    def _parse_ls_remote_output(self, output: str) -> List[str]:
        """
        解析 git ls-remote 的輸出
        
        輸出格式範例：
        abc123...  refs/heads/main
        def456...  refs/heads/develop
        
        Returns:
            分支名稱列表（不包含 refs/heads/ 前綴）
        """
        branches = []
        
        for line in output.strip().split("\n"):
            if not line:
                continue
                
            # 每行格式: <commit-hash>\t<ref-name>
            parts = line.split("\t")
            if len(parts) != 2:
                continue
                
            ref_name = parts[1].strip()
            
            # 只處理 refs/heads/ 開頭的（分支）
            if ref_name.startswith("refs/heads/"):
                branch_name = ref_name.replace("refs/heads/", "")
                branches.append(branch_name)
        
        return branches


def get_git_service(ssh_key_path: Optional[Path] = None) -> GitService:
    """
    獲取 GitService 實例
    
    Args:
        ssh_key_path: SSH 私鑰路徑
        
    Returns:
        GitService 實例
    """
    return GitService(ssh_key_path=ssh_key_path)


__all__ = ["GitService", "get_git_service"]
