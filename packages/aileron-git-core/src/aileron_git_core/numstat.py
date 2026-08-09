from pathlib import Path
from typing import Iterable, Optional

from .command_runner import run_git
from .models import NumstatEntry, NumstatResult


def read_numstat(
    repo_root: Path,
    *,
    paths: Iterable[str],
    staged: bool,
    commit_sha: Optional[str],
) -> NumstatResult:
    visible_paths = tuple(paths)
    if not visible_paths:
        return NumstatResult(entries=[])
    if commit_sha:
        args = ["show", "--format=", "--numstat", commit_sha]
    else:
        args = ["diff", "--numstat"]
        if staged:
            args.append("--cached")
    args.extend(["--", *visible_paths])
    output = run_git(repo_root, *args).stdout
    entries = []
    allowed = set(visible_paths)
    for line in output.splitlines():
        additions, separator, remainder = line.partition("\t")
        if not separator:
            continue
        deletions, separator, path = remainder.partition("\t")
        if not separator or path not in allowed:
            continue
        binary = additions == "-" or deletions == "-"
        entries.append(
            NumstatEntry(
                path=path,
                additions=0 if binary else int(additions),
                deletions=0 if binary else int(deletions),
                binary=binary,
            )
        )
    return NumstatResult(entries=entries)
