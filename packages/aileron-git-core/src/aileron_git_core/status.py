from pathlib import Path
from typing import List, Optional

from .command_runner import run_git
from .models import FileChange, GitStatus

_CONFLICT_STATUSES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
_RENAMED_OR_COPIED = {"R", "C"}


def collect_status(repo_root: Path) -> GitStatus:
    result = run_git(
        repo_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    return parse_status_output(result.stdout)


def parse_status_output(output: str) -> GitStatus:
    staged: List[FileChange] = []
    unstaged: List[FileChange] = []
    untracked: List[FileChange] = []
    conflicts: List[FileChange] = []

    records = output.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue

        status = record[:2]
        path = record[3:] if len(record) > 3 else ""
        original_path: Optional[str] = None
        if status[0] in _RENAMED_OR_COPIED and index < len(records):
            original_path = records[index] or None
            index += 1

        if status == "??":
            untracked.append(
                FileChange(
                    path=path,
                    status=status,
                    type="untracked",
                    raw_status=status,
                )
            )
            continue

        if status in _CONFLICT_STATUSES:
            conflicts.append(
                FileChange(
                    path=path,
                    status=status,
                    type="unmerged",
                    raw_status=status,
                    original_path=original_path,
                )
            )
            continue

        index_status = status[0]
        working_tree_status = status[1]
        if index_status != " ":
            staged.append(
                FileChange(
                    path=path,
                    status=index_status,
                    type=_change_type(index_status),
                    raw_status=status,
                    original_path=original_path,
                )
            )
        if working_tree_status != " ":
            unstaged.append(
                FileChange(
                    path=path,
                    status=working_tree_status,
                    type=_change_type(working_tree_status),
                    raw_status=status,
                    original_path=original_path,
                )
            )

    return GitStatus(
        staged=sorted(staged, key=lambda item: item.path),
        unstaged=sorted(unstaged, key=lambda item: item.path),
        untracked=sorted(untracked, key=lambda item: item.path),
        conflicts=sorted(conflicts, key=lambda item: item.path),
    )


def _change_type(status: str) -> str:
    if status == "M":
        return "modified"
    if status == "A":
        return "added"
    if status == "D":
        return "deleted"
    if status == "R":
        return "renamed"
    if status == "C":
        return "copied"
    if status == "T":
        return "typechange"
    return "changed"


_parse_porcelain_z = parse_status_output
