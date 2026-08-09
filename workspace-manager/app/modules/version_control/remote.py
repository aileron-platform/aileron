"""Shared remote URL and user-scoped Git credential handling."""

from __future__ import annotations

import os
import re
import shlex
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from aileron_git_core import RemoteBranchList, list_remote_branches
from sqlalchemy.orm import Session

from app.modules.settings.user_settings import SettingsService

VC_REMOTE_URL_INVALID = "VC_REMOTE_URL_INVALID"
VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED = "VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED"
VC_SSH_KEY_REQUIRED = "VC_SSH_KEY_REQUIRED"

_SCP_REMOTE_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+:[^\s:][^\s]*$"
)


class VersionControlRemoteError(ValueError):
    """Stable version-control remote validation error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require_user_ssh_private_key(db: Session, *, user_id: str) -> str:
    user_settings = SettingsService(db).get_settings(user_id)
    private_key = (
        user_settings.ssh.private_key.strip()
        if user_settings and user_settings.ssh.private_key
        else ""
    )
    if not private_key:
        raise VersionControlRemoteError(VC_SSH_KEY_REQUIRED)
    return private_key


def is_ssh_remote_url(remote_url: str) -> bool:
    normalized = remote_url.strip()
    if _SCP_REMOTE_PATTERN.fullmatch(normalized):
        return True
    try:
        return urlparse(normalized).scheme.lower() == "ssh"
    except ValueError:
        return False


def validate_clone_remote_url(remote_url: str) -> str:
    normalized = remote_url.strip()
    if not normalized:
        raise VersionControlRemoteError(VC_REMOTE_URL_INVALID)
    if _SCP_REMOTE_PATTERN.fullmatch(normalized):
        return normalized
    try:
        parsed = urlparse(normalized)
    except ValueError as exc:
        raise VersionControlRemoteError(VC_REMOTE_URL_INVALID) from exc
    if parsed.scheme.lower() not in {"http", "https", "ssh"} or not parsed.hostname:
        raise VersionControlRemoteError(VC_REMOTE_URL_INVALID)
    if parsed.password is not None or (
        parsed.scheme.lower() in {"http", "https"} and parsed.username is not None
    ):
        raise VersionControlRemoteError(VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED)
    return normalized


def discover_remote_branches(
    db: Session,
    *,
    user_id: str,
    repo_root: Path,
    remote_url: str,
) -> RemoteBranchList:
    normalized = validate_clone_remote_url(remote_url)
    with user_git_environment(
        db,
        user_id=user_id,
        remote_url=normalized,
    ) as git_env:
        return list_remote_branches(
            repo_root,
            normalized,
            env=git_env,
        )


@contextmanager
def user_git_environment(
    db: Session,
    *,
    user_id: str,
    remote_url: str,
) -> Iterator[dict[str, str] | None]:
    """Yield an isolated Git environment for one user's SSH remote."""

    normalized = remote_url.strip()
    if not is_ssh_remote_url(normalized):
        yield None
        return

    private_key = require_user_ssh_private_key(db, user_id=user_id)

    with tempfile.TemporaryDirectory(prefix="aileron-git-credentials-") as key_dir:
        private_key_path = Path(key_dir) / "id"
        private_key_path.write_text(
            private_key if private_key.endswith("\n") else f"{private_key}\n",
            encoding="utf-8",
        )
        private_key_path.chmod(0o600)
        yield {
            **os.environ,
            "GIT_SSH_COMMAND": (
                f"ssh -i {shlex.quote(str(private_key_path))} "
                "-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
            ),
        }


__all__ = [
    "VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED",
    "VC_REMOTE_URL_INVALID",
    "VC_SSH_KEY_REQUIRED",
    "VersionControlRemoteError",
    "discover_remote_branches",
    "is_ssh_remote_url",
    "require_user_ssh_private_key",
    "user_git_environment",
    "validate_clone_remote_url",
]
