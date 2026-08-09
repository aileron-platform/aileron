import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .errors import GitCommandError


@dataclass(frozen=True)
class GitCommandResult:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str


def build_git_command(repo_root: Path, *args: str) -> List[str]:
    canonical_root = repo_root.resolve()
    return [
        "git",
        "-c",
        f"safe.directory={canonical_root}",
        # Without this, git wraps non-ASCII (e.g. CJK) paths in double quotes
        # with C-style octal byte escapes in porcelain/plumbing output that
        # isn't NUL-terminated (e.g. `diff --name-status`, `diff --numstat`,
        # a patch's `diff --git a/... b/...` header). Callers that parse such
        # output and reuse the path (to fetch a blob, build a follow-up diff,
        # etc.) would otherwise operate on that mangled placeholder instead
        # of the real path.
        "-c",
        "core.quotepath=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(canonical_root),
        *args,
    ]


def run_git(
    repo_root: Path,
    *args: str,
    timeout_seconds: int = 30,
    env: Mapping[str, str] | None = None,
) -> GitCommandResult:
    command = build_git_command(repo_root, *args)
    result = _run_command(command, timeout_seconds=timeout_seconds, env=env)
    if result.returncode != 0:
        raise GitCommandError(command, result.returncode, result.stdout, result.stderr)
    return result


def git_allow_failure(
    repo_root: Path,
    *args: str,
    timeout_seconds: int = 30,
    env: Mapping[str, str] | None = None,
) -> GitCommandResult:
    command = build_git_command(repo_root, *args)
    return _run_command(command, timeout_seconds=timeout_seconds, env=env)


def _build_env(env: Mapping[str, str] | None) -> dict[str, str]:
    """Merge caller env with a forced C locale so git emits English stderr.

    Lock-signature detection relies on English messages regardless of the
    container locale.
    """
    merged: dict[str, str] = dict(os.environ if env is None else env)
    merged["LC_ALL"] = "C"
    merged["LANGUAGE"] = "C"
    return merged


def _run_command(
    command: List[str],
    timeout_seconds: int,
    env: Mapping[str, str] | None,
) -> GitCommandResult:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
            env=_build_env(env),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        raise GitCommandError(command, -1, stdout, stderr) from exc

    result = GitCommandResult(
        args=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    return result
