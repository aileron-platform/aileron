from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "copy_private_inputs.py"
SPEC = importlib.util.spec_from_file_location("copy_private_inputs", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _private(path: Path, value: bytes = b"private") -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(value)
    path.chmod(0o600)
    return path


def test_copies_external_input_without_following_source(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    source = _private(private_root / "tls.crt")
    destination_dir = tmp_path / "destination"
    destination_dir.mkdir(mode=0o700)
    destination = destination_dir / "tls.crt"

    MODULE.copy_private(private_root, source, destination)

    assert destination.read_bytes() == b"private"
    assert destination.stat().st_mode & 0o777 == 0o600


def test_rejects_symlinked_external_input_and_ancestor(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    target = _private(private_root / "target")
    linked = private_root / "linked"
    linked.symlink_to(target)
    destination_dir = tmp_path / "destination"
    destination_dir.mkdir(mode=0o700)

    with pytest.raises(ValueError, match="symbolic link"):
        MODULE.copy_private(private_root, linked, destination_dir / "copied")


def test_rejects_external_input_outside_private_root(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    outside = _private(tmp_path / "outside")
    destination_dir = tmp_path / "destination"
    destination_dir.mkdir(mode=0o700)

    with pytest.raises(ValueError, match="private root"):
        MODULE.copy_private(private_root, outside, destination_dir / "copied")
