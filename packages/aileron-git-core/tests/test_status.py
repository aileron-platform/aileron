from pathlib import Path

import pytest

from aileron_git_core import collect_status
from aileron_git_core import paginate_changes, parse_status_output, to_change_dict


def run_git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-C", str(repo), *args], check=True)


def test_collect_status_groups_untracked_and_modified(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Tester")
    run_git(repo, "config", "user.email", "tester@example.test")
    (repo / "tracked.txt").write_text("old", encoding="utf-8")
    run_git(repo, "add", "tracked.txt")
    run_git(repo, "commit", "-m", "initial")
    (repo / "tracked.txt").write_text("new", encoding="utf-8")
    (repo / "z-tracked.txt").write_text("old", encoding="utf-8")
    run_git(repo, "add", "z-tracked.txt")
    run_git(repo, "commit", "-m", "add second tracked file")
    (repo / "z-tracked.txt").write_text("new", encoding="utf-8")
    (repo / "a-new.txt").write_text("new", encoding="utf-8")
    (repo / "new.txt").write_text("new", encoding="utf-8")

    status = collect_status(repo)

    assert [item.path for item in status.unstaged] == ["tracked.txt", "z-tracked.txt"]
    assert status.unstaged[0].status == "M"
    assert status.unstaged[0].type == "modified"
    assert status.unstaged[0].raw_status == " M"
    assert [item.path for item in status.untracked] == ["a-new.txt", "new.txt"]
    assert status.untracked[0].status == "??"
    assert status.untracked[0].type == "untracked"
    assert status.untracked[0].raw_status == "??"
    assert status.conflicts == []


def test_collect_status_extracts_conflicts_from_porcelain(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Tester")
    run_git(repo, "config", "user.email", "tester@example.test")
    (repo / "conflict.txt").write_text("base\n", encoding="utf-8")
    run_git(repo, "add", "conflict.txt")
    run_git(repo, "commit", "-m", "base")
    run_git(repo, "checkout", "-b", "feature")
    (repo / "conflict.txt").write_text("feature\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "feature")
    run_git(repo, "checkout", "main")
    (repo / "conflict.txt").write_text("main\n", encoding="utf-8")
    run_git(repo, "commit", "-am", "main")

    import subprocess

    subprocess.run(["git", "-C", str(repo), "merge", "feature"], check=False)
    status = collect_status(repo)

    assert [item.path for item in status.conflicts] == ["conflict.txt"]
    assert status.conflicts[0].status == "UU"
    assert status.conflicts[0].type == "unmerged"
    assert status.conflicts[0].raw_status == "UU"
    assert all(item.path != "conflict.txt" for item in status.unstaged)


def test_collect_status_preserves_rename_original_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Tester")
    run_git(repo, "config", "user.email", "tester@example.test")
    (repo / "old.txt").write_text("old", encoding="utf-8")
    run_git(repo, "add", "old.txt")
    run_git(repo, "commit", "-m", "initial")
    run_git(repo, "mv", "old.txt", "renamed.txt")

    status = collect_status(repo)

    assert [
        (item.path, item.original_path, item.status, item.type, item.raw_status)
        for item in status.staged
    ] == [
        ("renamed.txt", "old.txt", "R", "renamed", "R ")
    ]


def test_parse_status_output_extracts_all_conflict_codes() -> None:
    output = "\0".join([
        "DD deleted-by-both.txt",
        "AU added-by-us.txt",
        "UD deleted-by-them.txt",
        "UA added-by-them.txt",
        "DU deleted-by-us.txt",
        "AA added-by-both.txt",
        "UU modified-by-both.txt",
        " M normal.txt",
        "?? new.txt",
        "",
    ])

    status = parse_status_output(output)

    assert [(item.path, item.status, item.type) for item in status.conflicts] == [
        ("added-by-both.txt", "AA", "unmerged"),
        ("added-by-them.txt", "UA", "unmerged"),
        ("added-by-us.txt", "AU", "unmerged"),
        ("deleted-by-both.txt", "DD", "unmerged"),
        ("deleted-by-them.txt", "UD", "unmerged"),
        ("deleted-by-us.txt", "DU", "unmerged"),
        ("modified-by-both.txt", "UU", "unmerged"),
    ]
    assert [item.path for item in status.unstaged] == ["normal.txt"]
    assert [item.path for item in status.untracked] == ["new.txt"]
    conflict_paths = {item.path for item in status.conflicts}
    regular_paths = {item.path for item in status.staged + status.unstaged}
    assert conflict_paths.isdisjoint(regular_paths)


def test_parse_status_output_maps_typechange() -> None:
    status = parse_status_output("T  mode.txt\0")

    assert [(item.path, item.status, item.type) for item in status.staged] == [
        ("mode.txt", "T", "typechange")
    ]


def test_to_change_dict_and_paginate_changes_use_shared_shape() -> None:
    status = parse_status_output("R  renamed.txt\0old.txt\0?? a.txt\0?? b.txt\0")
    page_items, total, has_more = paginate_changes(status.untracked, page=1, page_size=1)

    assert [item.path for item in page_items] == ["a.txt"]
    assert total == 2
    assert has_more is True
    assert to_change_dict(status.staged[0]) == {
        "name": "renamed.txt",
        "path": "renamed.txt",
        "status": "R",
        "type": "renamed",
        "oldPath": "old.txt",
    }


def test_paginate_changes_rejects_invalid_page() -> None:
    status = parse_status_output("?? a.txt\0")

    with pytest.raises(ValueError, match="page"):
        paginate_changes(status.untracked, page=0, page_size=1)


def test_paginate_changes_rejects_invalid_page_size() -> None:
    status = parse_status_output("?? a.txt\0")

    with pytest.raises(ValueError, match="page_size"):
        paginate_changes(status.untracked, page=1, page_size=0)


def test_parse_status_output_preserves_copy_original_path_for_adapter() -> None:
    status = parse_status_output("C  copied.txt\0source.txt\0")
    copied = status.staged[0]

    assert copied.status == "C"
    assert copied.type == "copied"
    assert copied.original_path == "source.txt"
    assert to_change_dict(copied) == {
        "name": "copied.txt",
        "path": "copied.txt",
        "status": "C",
        "type": "copied",
        "oldPath": "source.txt",
    }
