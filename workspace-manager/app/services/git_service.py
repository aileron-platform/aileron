"""Git related service"""

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
    """Service handling Git related operations"""

    def __init__(self, ssh_key_path: Optional[Path] = None):
        """
        Initialize Git Service

        Args:
            ssh_key_path: SSH private key path, used for authenticating private repositories
        """
        self.ssh_key_path = ssh_key_path

    def get_remote_branches(self, git_url: str) -> List[str]:
        """
        Get branch list of remote Git repository

        Args:
            git_url: Git repository URL

        Returns:
            List of branch names

        Raises:
            ValueError: When Git URL is invalid or inaccessible
            RuntimeError: When git command execution fails
        """
        if not git_url or not git_url.strip():
            raise GitBranchLookupError("Git URL cannot be empty", code="WORKSPACE_SETUP_GIT_EMPTY_URL")

        # Clean URL (remove newlines and whitespace)
        git_url = git_url.strip()

        # Validate Git URL format
        if not self._is_valid_git_url(git_url):
            raise GitBranchLookupError(f"Invalid Git URL: {git_url}", code="WORKSPACE_SETUP_GIT_INVALID_URL", params={"gitUrl": git_url})

        try:
            # Prepare environment variables
            env = self._prepare_git_env()
            
            # Use git ls-remote to get remote branches
            # --heads only list branches (exclude tags)
            cmd = ["git", "ls-remote", "--heads", git_url]
            
            logger.info(f"Executing git ls-remote: {git_url}")

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
                logger.error(f"git ls-remote failed: {error_msg}")

                # Provide more friendly error message
                if "Authentication failed" in error_msg or "Permission denied" in error_msg:
                    raise GitBranchLookupError("Authentication failed, please confirm SSH key settings are correct or use public repository", code="WORKSPACE_SETUP_GIT_AUTH_FAILED")
                elif "Could not resolve host" in error_msg:
                    raise GitBranchLookupError("Cannot resolve host name, please check network connection", code="WORKSPACE_SETUP_GIT_RESOLVE_FAILED")
                elif "Repository not found" in error_msg:
                    raise GitBranchLookupError("Repository not found, please confirm URL is correct", code="WORKSPACE_SETUP_GIT_REPOSITORY_NOT_FOUND")
                else:
                    raise GitBranchLookupError(f"Cannot get branch list: {error_msg}", code="WORKSPACE_SETUP_GIT_FETCH_FAILED")

            # Parse output
            branches = self._parse_ls_remote_output(result.stdout)

            logger.info(f"Successfully got {len(branches)} branches: {branches}")
            return branches

        except subprocess.TimeoutExpired:
            logger.error(f"git ls-remote timeout: {git_url}")
            raise GitBranchLookupError("Get branch list timeout, please try again later", code="WORKSPACE_SETUP_GIT_TIMEOUT")
        except Exception as e:
            if isinstance(e, GitBranchLookupError):
                raise
            logger.error(f"Error occurred while getting branch list: {e}")
            raise GitBranchLookupError(f"Get branch list failed: {str(e)}", code="WORKSPACE_SETUP_GIT_FETCH_FAILED")

    def _is_valid_git_url(self, url: str) -> bool:
        """
        Verify Git URL format

        Supported formats:
        - https://github.com/user/repo.git
        - https://github.com/user/repo (without .git)
        - git@github.com:user/repo.git
        - git@github.com:user/repo (without .git)
        - git@ssh.dev.azure.com:v3/org/project/repo (Azure DevOps)
        - ssh://git@github.com/user/repo.git
        """
        # HTTPS format (.git optional)
        if url.startswith(("http://", "https://")):
            return self._is_valid_https_git_url(url)

        # SSH format (git@host:path, .git optional)
        # Support common format: git@github.com:user/repo.git or git@github.com:user/repo
        ssh_pattern = r"^git@[a-zA-Z0-9\-._]+:[a-zA-Z0-9\-._/]+(\.git)?$"

        # Azure DevOps SSH format: git@ssh.dev.azure.com:v3/org/project/repo
        azure_ssh_pattern = r"^git@ssh\.dev\.azure\.com:v3/[a-zA-Z0-9\-._]+/[a-zA-Z0-9\-._]+/[a-zA-Z0-9\-._]+(\.git)?$"

        # SSH URL format (ssh://git@host/path, .git optional)
        ssh_url_pattern = r"^ssh://git@[a-zA-Z0-9\-._]+/[a-zA-Z0-9\-._/]+(\.git)?$"

        return bool(
            re.match(ssh_pattern, url) or
            re.match(azure_ssh_pattern, url) or
            re.match(ssh_url_pattern, url)
        )

    def _is_valid_https_git_url(self, url: str) -> bool:
        """Verify HTTPS Git URL, allow omitting .git but exclude common non-repository paths."""
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
        """Prepare environment variables for Git commands"""
        import os
        
        env = os.environ.copy()
        
        # If SSH key provided, set GIT_SSH_COMMAND
        if self.ssh_key_path and self.ssh_key_path.exists():
            # Use specified SSH key and disable host key checking (development environment)
            ssh_cmd = (
                f"ssh -i {self.ssh_key_path} "
                f"-o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null"
            )
            env["GIT_SSH_COMMAND"] = ssh_cmd
            logger.debug(f"Use SSH key: {self.ssh_key_path}")
        
        return env

    def _parse_ls_remote_output(self, output: str) -> List[str]:
        """
        Parse git ls-remote output

        Output format example:
        abc123...  refs/heads/main
        def456...  refs/heads/develop

        Returns:
            List of branch names (without refs/heads/ prefix)
        """
        branches = []
        
        for line in output.strip().split("\n"):
            if not line:
                continue
                
            # Line format: <commit-hash>\t<ref-name>
            parts = line.split("\t")
            if len(parts) != 2:
                continue
                
            ref_name = parts[1].strip()
            
            # Only handle refs/heads/ prefix (branches)
            if ref_name.startswith("refs/heads/"):
                branch_name = ref_name.replace("refs/heads/", "")
                branches.append(branch_name)
        
        return branches


def get_git_service(ssh_key_path: Optional[Path] = None) -> GitService:
    """
    Get GitService instance

    Args:
        ssh_key_path: SSH private key path

    Returns:
        GitService instance
    """
    return GitService(ssh_key_path=ssh_key_path)


__all__ = ["GitService", "get_git_service"]
