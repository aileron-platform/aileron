from pathlib import Path

import pytest

from aileron_file_core import (
    ContentHashVersionStrategy,
    VersionConflictError,
    compare_and_write_text,
)


def test_compare_and_write_text_rejects_stale_expected_version(
    tmp_path: Path,
) -> None:
    target = tmp_path / "note.md"
    target.write_text("newer", encoding="utf-8")
    strategy = ContentHashVersionStrategy(length=16)

    with pytest.raises(VersionConflictError) as exc_info:
        compare_and_write_text(
            target,
            "older",
            expected_version_id="stale-version",
            strategy=strategy,
        )

    assert exc_info.value.path == str(target)
    assert target.read_text(encoding="utf-8") == "newer"


def test_compare_and_write_text_writes_when_expected_matches(
    tmp_path: Path,
) -> None:
    target = tmp_path / "note.md"
    target.write_text("old", encoding="utf-8")
    strategy = ContentHashVersionStrategy(length=16)
    expected = strategy.read_version(target)

    result = compare_and_write_text(
        target,
        "new",
        expected_version_id=expected,
        strategy=strategy,
    )

    assert target.read_text(encoding="utf-8") == "new"
    assert result.path == target
    assert result.version_id == strategy.read_version(target)
