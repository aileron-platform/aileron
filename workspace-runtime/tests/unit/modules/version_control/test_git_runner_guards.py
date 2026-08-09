from __future__ import annotations

from pathlib import Path


def test_workspace_mutation_paths_do_not_use_gitpython_mutation_api() -> None:
    root = Path(__file__).resolve().parents[4]
    scoped_files = [
        root / "app/modules/version_control/git_operations.py",
    ]
    forbidden = [
        "from git import",
        "import git",
        "Repo(",
        ".index.",
        ".remote(",
        ".remotes",
        ".git.",
        "iter_commits",
    ]

    violations = []
    for path in scoped_files:
        text = path.read_text(encoding="utf-8")
        violations.extend(
            f"{path.name}: {pattern}" for pattern in forbidden if pattern in text
        )

    assert violations == []


def test_workspace_version_control_uses_shared_git_runner_for_scoped_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    scoped_root = root / "app/modules/version_control"
    forbidden = [
        "from git import",
        "import git",
        "Repo(",
        ".index.",
        ".remote(",
        ".remotes",
        ".git.",
        "iter_commits",
        "unmerged_blobs",
        "subprocess.run",
    ]

    violations = []
    for path in scoped_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        violations.extend(
            f"{path.name}: {pattern}" for pattern in forbidden if pattern in text
        )

    assert violations == []
