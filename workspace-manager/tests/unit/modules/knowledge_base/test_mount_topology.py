from pathlib import Path

import pytest

from app.modules.knowledge_base.mount_topology import contains_nested_mount


class MountTopologyError(RuntimeError):
    pass


def _error(message: str) -> Exception:
    return MountTopologyError(message)


def test_contains_nested_mount_detects_mount_below_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    nested = source / "nested"
    mountinfo = f"1 2 0:1 / {nested} rw - tmpfs tmpfs rw\n"
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: mountinfo)

    assert contains_nested_mount(
        source,
        error_factory=_error,
        read_error_message="read failed",
        invalid_error_message="invalid",
    )


def test_contains_nested_mount_ignores_unrelated_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    unrelated = tmp_path / "other"
    mountinfo = f"1 2 0:1 / {unrelated} rw - tmpfs tmpfs rw\n"
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: mountinfo)

    assert not contains_nested_mount(
        source,
        error_factory=_error,
        read_error_message="read failed",
        invalid_error_message="invalid",
    )


def test_contains_nested_mount_maps_read_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()

    def fail_read(*_args, **_kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(Path, "read_text", fail_read)

    with pytest.raises(MountTopologyError, match="read failed") as exc_info:
        contains_nested_mount(
            source,
            error_factory=_error,
            read_error_message="read failed",
            invalid_error_message="invalid",
        )

    assert isinstance(exc_info.value.__cause__, OSError)


def test_contains_nested_mount_rejects_invalid_mountinfo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: "invalid\n")

    with pytest.raises(MountTopologyError, match="invalid"):
        contains_nested_mount(
            source,
            error_factory=_error,
            read_error_message="read failed",
            invalid_error_message="invalid",
        )
