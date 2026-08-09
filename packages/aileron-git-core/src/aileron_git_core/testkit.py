from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .command_runner import git_allow_failure, run_git
from .errors import GitCommandError

__all__ = ["Actor", "GitCommandError", "Repo"]


@dataclass(frozen=True)
class Actor:
    name: str
    email: str


@dataclass(frozen=True)
class _Commit:
    repo_root: Path
    hexsha: str

    @property
    def message(self) -> str:
        return run_git(self.repo_root, "show", "-s", "--format=%B", self.hexsha).stdout


@dataclass(frozen=True)
class _Branch:
    repo: "Repo"
    name: str

    def checkout(self) -> None:
        run_git(self.repo.path, "checkout", self.name)


class _Heads:
    def __init__(self, repo: "Repo") -> None:
        self._repo = repo

    def __iter__(self) -> Iterator[_Branch]:
        return iter(self._repo.branches)

    def __getattr__(self, name: str) -> _Branch:
        return _Branch(self._repo, name)


class _Head:
    def __init__(self, repo: "Repo") -> None:
        self._repo = repo

    @property
    def is_detached(self) -> bool:
        result = git_allow_failure(
            self._repo.path,
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
        )
        return result.returncode != 0

    @property
    def commit(self) -> _Commit:
        sha = run_git(self._repo.path, "rev-parse", "HEAD").stdout.strip()
        return _Commit(self._repo.path, sha)


class _Index:
    def __init__(self, repo: "Repo") -> None:
        self._repo = repo

    def add(self, paths: Iterable[str]) -> None:
        run_git(self._repo.path, "add", "--", *list(paths))

    def commit(
        self,
        message: str,
        *,
        author: Optional[Actor] = None,
        committer: Optional[Actor] = None,
    ) -> _Commit:
        env = _actor_env(author=author, committer=committer)
        run_git(self._repo.path, "commit", "-m", message, env=env)
        return self._repo.head.commit

    def diff(self, ref: str) -> list[str]:
        result = run_git(self._repo.path, "diff", "--name-only", ref)
        return [line for line in result.stdout.splitlines() if line]


class _GitProxy:
    def __init__(self, repo: "Repo") -> None:
        self._repo = repo

    def branch(self, *args: str) -> str:
        return run_git(self._repo.path, "branch", *args).stdout.strip()

    def checkout(self, *args: str) -> str:
        return run_git(self._repo.path, "checkout", *args).stdout.strip()

    def push(self, *args: str) -> str:
        return run_git(self._repo.path, "push", *args).stdout.strip()

    def merge(self, *args: str) -> str:
        return run_git(self._repo.path, "merge", *args).stdout.strip()

    def mv(self, *args: str) -> str:
        return run_git(self._repo.path, "mv", *args).stdout.strip()

    def diff(self, *args: str) -> str:
        return run_git(self._repo.path, "diff", *args).stdout.strip()


@dataclass(frozen=True)
class _Remote:
    repo: "Repo"
    name: str

    def fetch(self) -> None:
        run_git(self.repo.path, "fetch", self.name)


class _Remotes:
    def __init__(self, repo: "Repo") -> None:
        self._repo = repo

    def __iter__(self) -> Iterator[_Remote]:
        result = git_allow_failure(self._repo.path, "remote")
        if result.returncode != 0:
            return iter(())
        return iter(_Remote(self._repo, name) for name in result.stdout.splitlines() if name)

    def __getattr__(self, name: str) -> _Remote:
        return _Remote(self._repo, name)


class _ConfigWriter:
    def __init__(self, repo: "Repo") -> None:
        self._repo = repo

    def __enter__(self) -> "_ConfigWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def set_value(self, section: str, option: str, value: str) -> "_ConfigWriter":
        run_git(self._repo.path, "config", f"{section}.{option}", value)
        return self


class Repo:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.working_tree_dir = None if (self.path / "HEAD").exists() and not (self.path / ".git").exists() else str(self.path)
        self.index = _Index(self)
        self.git = _GitProxy(self)
        self.head = _Head(self)
        self.heads = _Heads(self)
        self.remotes = _Remotes(self)

    @classmethod
    def init(
        cls,
        path: Path | str,
        bare: bool = False,
        initial_branch: str | None = None,
    ) -> "Repo":
        repo_path = Path(path)
        repo_path.mkdir(parents=True, exist_ok=True)
        args = ["init"]
        if bare:
            args.append("--bare")
        if initial_branch:
            args.extend(["--initial-branch", initial_branch])
        args.append(str(repo_path))
        run_git(repo_path.parent if repo_path.parent.exists() else Path("."), *args)
        repo = cls(repo_path)
        if not bare:
            repo.config_writer().set_value("user", "name", "Test User")
            repo.config_writer().set_value("user", "email", "test@example.com")
        return repo

    def config_writer(self) -> _ConfigWriter:
        return _ConfigWriter(self)

    def create_remote(self, name: str, url: str) -> _Remote:
        run_git(self.path, "remote", "add", name, url)
        return _Remote(self, name)

    def create_head(self, name: str, commit: str | None = None) -> _Branch:
        args = ["branch", name]
        if commit:
            args.append(commit)
        run_git(self.path, *args)
        return _Branch(self, name)

    @property
    def active_branch(self) -> _Branch:
        name = run_git(self.path, "branch", "--show-current").stdout.strip()
        return _Branch(self, name)

    @property
    def branches(self) -> list[_Branch]:
        result = run_git(self.path, "branch", "--format=%(refname:short)")
        return [_Branch(self, line.strip()) for line in result.stdout.splitlines() if line.strip()]

    @property
    def untracked_files(self) -> list[str]:
        result = run_git(self.path, "ls-files", "--others", "--exclude-standard")
        return [line for line in result.stdout.splitlines() if line]

    def iter_commits(self) -> Iterator[_Commit]:
        result = run_git(self.path, "rev-list", "HEAD")
        return (_Commit(self.path, line.strip()) for line in result.stdout.splitlines() if line.strip())

    def is_dirty(self) -> bool:
        return bool(run_git(self.path, "status", "--porcelain").stdout.strip())


def _actor_env(
    *,
    author: Optional[Actor],
    committer: Optional[Actor],
) -> dict[str, str]:
    env: dict[str, str] = {}
    if author is not None:
        env["GIT_AUTHOR_NAME"] = author.name
        env["GIT_AUTHOR_EMAIL"] = author.email
    if committer is not None:
        env["GIT_COMMITTER_NAME"] = committer.name
        env["GIT_COMMITTER_EMAIL"] = committer.email
    return env
