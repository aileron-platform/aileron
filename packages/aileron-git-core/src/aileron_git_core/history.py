from pathlib import Path
from typing import Optional

from .command_runner import git_allow_failure, run_git
from .models import (
    BlobResult,
    CommitFileDetail,
    CommitFilesResult,
    CommitHistoryPage,
    DiffResult,
)
from .mutations import list_commits


def _resolves_to_commit(repo_root: Path, ref: str) -> bool:
    result = git_allow_failure(
        repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"
    )
    return result.returncode == 0


def read_history(
    repo_root: Path,
    *,
    scope: str,
    branch: Optional[str],
    search: Optional[str],
    cursor: Optional[str],
    limit: int,
) -> CommitHistoryPage:
    if limit < 1:
        raise ValueError("History limit must be positive")
    offset = int(cursor or "0")
    if offset < 0:
        raise ValueError("History cursor must not be negative")
    if scope == "current":
        ref = "HEAD"
    elif scope == "all":
        ref = "--all"
    elif scope in {"local", "remote"} and branch:
        ref = branch
    else:
        raise ValueError("History scope requires a valid branch")
    if ref != "--all" and not _resolves_to_commit(repo_root, ref):
        # A repository without commits on the requested ref has an empty history.
        return CommitHistoryPage(
            items=[], total=0, next_cursor=None, has_more=False, query_scope=scope
        )
    items, total = list_commits(
        repo_root, ref=ref, skip=offset, limit=limit, search=search
    )
    next_offset = offset + len(items)
    has_more = next_offset < total
    return CommitHistoryPage(
        items=list(items),
        total=total,
        next_cursor=str(next_offset) if has_more else None,
        has_more=has_more,
        query_scope=scope,
    )


def read_diff(
    repo_root: Path,
    *,
    path: str,
    staged: bool,
    commit_sha: Optional[str],
) -> DiffResult:
    if commit_sha:
        result = run_git(repo_root, "show", "--format=", "--no-ext-diff", commit_sha, "--", path)
    else:
        args = ["diff", "--no-ext-diff"]
        if staged:
            args.append("--cached")
        args.extend(["--", path])
        result = run_git(repo_root, *args)
    return DiffResult(path=path, patch=result.stdout)


def read_blob(repo_root: Path, *, path: str, ref: str) -> BlobResult:
    content = run_git(repo_root, "show", f"{ref}:{path}").stdout
    return BlobResult(path=path, ref=ref, content=content)


def read_commit_files(repo_root: Path, sha: str) -> CommitFilesResult:
    resolved_sha = run_git(
        repo_root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{sha}^{{commit}}",
    ).stdout.strip()
    name_status = run_git(
        repo_root,
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-status",
        "-r",
        "-M",
        resolved_sha,
    ).stdout
    stats = _commit_numstat(repo_root, resolved_sha)
    files = []
    for line in name_status.splitlines():
        columns = line.split("\t")
        if len(columns) < 2:
            continue
        raw_status = columns[0]
        original_path = columns[1] if raw_status.startswith(("R", "C")) else None
        path = columns[2] if original_path is not None and len(columns) > 2 else columns[1]
        additions, deletions, binary = stats.get(path, (0, 0, False))
        if original_path is not None:
            old_additions, old_deletions, old_binary = stats.get(
                original_path, (0, 0, False)
            )
            additions += old_additions
            deletions += old_deletions
            binary = binary or old_binary
        patch = run_git(
            repo_root,
            "show",
            "--format=",
            "--no-ext-diff",
            resolved_sha,
            "--",
            path,
        ).stdout
        files.append(
            CommitFileDetail(
                path=path,
                original_path=original_path,
                status=raw_status[:1],
                additions=additions,
                deletions=deletions,
                binary=binary,
                patch=patch,
            )
        )
    return CommitFilesResult(sha=resolved_sha, files=files)


def _commit_numstat(
    repo_root: Path, sha: str
) -> dict[str, tuple[int, int, bool]]:
    output = run_git(
        repo_root,
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--numstat",
        "--no-renames",
        "-r",
        sha,
    ).stdout
    stats = {}
    for line in output.splitlines():
        additions, separator, remainder = line.partition("\t")
        if not separator:
            continue
        deletions, separator, path = remainder.partition("\t")
        if not separator:
            continue
        binary = additions == "-" or deletions == "-"
        stats[path] = (
            0 if binary else int(additions),
            0 if binary else int(deletions),
            binary,
        )
    return stats
