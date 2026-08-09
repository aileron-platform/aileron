from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

from .command_runner import git_allow_failure, run_git


@dataclass(frozen=True)
class PushRefResult:
    ref: str
    status: str
    summary: str
    diagnostic: str = ""


@dataclass(frozen=True)
class CommitSummary:
    sha: str
    message: str
    author_name: str
    author_email: str
    authored_at: str
    additions: int
    deletions: int
    files_changed: int


@dataclass(frozen=True)
class RemoteBranchList:
    branches: List[str]
    default_branch: Optional[str]


def has_head(repo_root: Path) -> bool:
    result = git_allow_failure(repo_root, "rev-parse", "--verify", "HEAD")
    return result.returncode == 0


def stage_paths(repo_root: Path, paths: Iterable[str]) -> None:
    normalized = _path_args(paths)
    if not normalized:
        return
    run_git(repo_root, "add", "--", *normalized)


def stage_all(repo_root: Path) -> None:
    run_git(repo_root, "add", "--all")


def unstage_paths(repo_root: Path, paths: Iterable[str]) -> None:
    normalized = _path_args(paths)
    if not normalized:
        return
    if has_head(repo_root):
        run_git(repo_root, "reset", "HEAD", "--", *normalized)
    else:
        run_git(repo_root, "rm", "--cached", "--ignore-unmatch", "--", *normalized)


def unstage_all(repo_root: Path) -> None:
    if has_head(repo_root):
        run_git(repo_root, "reset", "HEAD")
    else:
        run_git(repo_root, "rm", "--cached", "-r", "--ignore-unmatch", ".")


def checkout_paths(repo_root: Path, paths: Iterable[str]) -> None:
    normalized = _path_args(paths)
    if not normalized:
        return
    run_git(repo_root, "checkout", "--", *normalized)


def commit_staged(repo_root: Path, message: str) -> CommitSummary:
    run_git(repo_root, "commit", "-m", message)
    sha = run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
    return _commit_summary(repo_root, sha)


def list_commits(
    repo_root: Path,
    ref: str = "HEAD",
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
) -> tuple[List[CommitSummary], int]:
    if search:
        all_result = run_git(repo_root, "rev-list", ref)
        keyword = search.lower()
        filtered = [
            summary
            for summary in (
                _commit_summary(repo_root, sha.strip())
                for sha in all_result.stdout.splitlines()
                if sha.strip()
            )
            if keyword in summary.message.lower()
            or keyword in summary.author_name.lower()
            or keyword in summary.author_email.lower()
            or keyword in summary.sha.lower()
        ]
        start = max(skip, 0)
        end = start + max(limit, 0)
        return filtered[start:end], len(filtered)

    rev_args = ["rev-list", ref]
    total_result = run_git(repo_root, *(rev_args + ["--count"]))
    total = int(total_result.stdout.strip() or "0")

    page_args = rev_args + [f"--skip={max(skip, 0)}", f"--max-count={max(limit, 0)}"]
    page_result = run_git(repo_root, *page_args)
    shas = [line.strip() for line in page_result.stdout.splitlines() if line.strip()]
    return [_commit_summary(repo_root, sha) for sha in shas], total


def fetch_remote(
    repo_root: Path,
    remote: str = "origin",
    *,
    env: Mapping[str, str] | None = None,
) -> List[str]:
    result = run_git(repo_root, "fetch", remote, env=env)
    output = "\n".join(part for part in [result.stdout, result.stderr] if part)
    return [line.strip() for line in output.splitlines() if line.strip()]


def list_remote_branches(
    repo_root: Path,
    remote_url: str,
    *,
    env: Mapping[str, str] | None = None,
) -> RemoteBranchList:
    command_env = {
        **dict(env or {}),
        "GIT_TERMINAL_PROMPT": "0",
    }
    result = run_git(
        repo_root,
        "ls-remote",
        "--symref",
        "--",
        remote_url,
        "HEAD",
        "refs/heads/*",
        env=command_env,
    )
    default_branch: Optional[str] = None
    branch_names: set[str] = set()
    prefix = "refs/heads/"

    for line in result.stdout.splitlines():
        if line.startswith("ref: "):
            reference, _, target = line[5:].partition("\t")
            if target == "HEAD" and reference.startswith(prefix):
                default_branch = reference[len(prefix) :]
            continue
        _, separator, reference = line.partition("\t")
        if separator and reference.startswith(prefix):
            branch_names.add(reference[len(prefix) :])

    if default_branch:
        branch_names.add(default_branch)
    branches = sorted(branch_names)
    if default_branch:
        branches.remove(default_branch)
        branches.insert(0, default_branch)
    return RemoteBranchList(
        branches=branches,
        default_branch=default_branch,
    )


def pull_remote(
    repo_root: Path,
    remote: str = "origin",
    branch: Optional[str] = None,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[str, List[CommitSummary]]:
    old_head = (
        run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
        if has_head(repo_root)
        else ""
    )
    args = ["pull", "--ff-only", remote]
    if branch:
        args.append(branch)

    result = run_git(repo_root, *args, env=env)
    new_head = (
        run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
        if has_head(repo_root)
        else ""
    )
    incoming: List[CommitSummary] = []
    if old_head and new_head and old_head != new_head:
        incoming, _ = list_commits(
            repo_root, ref=f"{old_head}..{new_head}", skip=0, limit=1000
        )
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    return output, incoming


def push_remote(
    repo_root: Path,
    remote: str = "origin",
    branch: Optional[str] = None,
    *,
    env: Mapping[str, str] | None = None,
) -> List[PushRefResult]:
    args = ["push", "--porcelain"]
    args.append(remote)
    if branch:
        args.append(branch)

    result = git_allow_failure(repo_root, *args, env=env)
    parsed = [
        PushRefResult(
            ref=item.ref,
            status=item.status,
            summary=item.summary,
            diagnostic=result.stderr.strip(),
        )
        for item in _parse_push_porcelain(result.stdout)
    ]
    if parsed:
        if result.returncode != 0 and all(item.status == "ok" for item in parsed):
            parsed.append(
                PushRefResult(
                    ref=branch or "",
                    status="error",
                    summary=result.stderr.strip(),
                )
            )
        return parsed
    if result.returncode == 0:
        return [
            PushRefResult(ref=branch or "", status="ok", summary=result.stdout.strip())
        ]
    stderr = result.stderr.strip()
    status = "rejected" if _looks_rejected(stderr) else "error"
    return [PushRefResult(ref=branch or "", status=status, summary=stderr)]


def _path_args(paths: Iterable[str]) -> List[str]:
    return [path for path in paths if path]


def _commit_summary(repo_root: Path, sha: str) -> CommitSummary:
    metadata = run_git(
        repo_root,
        "show",
        "--no-patch",
        "--format=%H%x00%s%x00%an%x00%ae%x00%aI",
        sha,
    ).stdout.rstrip("\n")
    parts = metadata.split("\0")
    while len(parts) < 5:
        parts.append("")
    additions, deletions, files_changed = _commit_stats(repo_root, sha)
    return CommitSummary(
        sha=parts[0],
        message=parts[1],
        author_name=parts[2],
        author_email=parts[3],
        authored_at=parts[4],
        additions=additions,
        deletions=deletions,
        files_changed=files_changed,
    )


def _commit_stats(repo_root: Path, sha: str) -> tuple[int, int, int]:
    output = run_git(repo_root, "diff-tree", "--root", "--numstat", "-r", sha).stdout
    additions = 0
    deletions = 0
    files_changed = 0
    for line in output.splitlines():
        columns = line.split("\t")
        if len(columns) < 3:
            continue
        files_changed += 1
        additions += _numstat_value(columns[0])
        deletions += _numstat_value(columns[1])
    return additions, deletions, files_changed


def _numstat_value(value: str) -> int:
    return 0 if value == "-" else int(value)


def _parse_push_porcelain(output: str) -> List[PushRefResult]:
    results: List[PushRefResult] = []
    for line in output.splitlines():
        if not line or line.startswith("To "):
            continue
        columns = line.split("\t")
        if len(columns) < 2:
            continue
        flag = columns[0][:1]
        ref = _remote_ref(columns[1])
        summary = columns[2] if len(columns) > 2 else ""
        if flag == "!":
            status = "rejected"
        elif flag in {" ", "+", "*", "-", "="}:
            status = "ok"
        else:
            status = "error"
        results.append(PushRefResult(ref=ref, status=status, summary=summary))
    return results


def _remote_ref(refspec: str) -> str:
    if ":" in refspec:
        return refspec.rsplit(":", 1)[1]
    return refspec


def _looks_rejected(message: str) -> bool:
    lowered = message.lower()
    return (
        "reject" in lowered or "non-fast-forward" in lowered or "fetch first" in lowered
    )
