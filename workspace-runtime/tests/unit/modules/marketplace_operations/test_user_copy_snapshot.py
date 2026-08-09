from __future__ import annotations

import json
import os
import stat
import warnings
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Callable

import pytest
from aileron_marketplace_core import package_tree_digest

from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.user_copy_snapshot import (
    UserCopySnapshotLimits,
    UserCopySnapshotStager,
)

_OPERATION_ID = "a" * 32
_OTHER_OPERATION_ID = "b" * 32


@dataclass(frozen=True)
class _ArchiveEntry:
    name: str
    content: bytes = b""
    mode: int = 0o644
    file_type: int = stat.S_IFREG
    compression: int = zipfile.ZIP_DEFLATED
    dos_directory: bool = False


def _archive_bytes(*entries: _ArchiveEntry) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for entry in entries:
            info = zipfile.ZipInfo(entry.name)
            info.create_system = 3
            info.compress_type = entry.compression
            info.external_attr = (entry.file_type | entry.mode) << 16
            if entry.dos_directory:
                info.external_attr |= 0x10
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(info, entry.content)
    return buffer.getvalue()


def _expected_tree_digest(
    tmp_path: Path,
    *entries: _ArchiveEntry,
) -> str:
    root = tmp_path / "expected"
    root.mkdir(mode=0o700)
    for entry in entries:
        relative = entry.name[:-1] if entry.name.endswith("/") else entry.name
        target = root.joinpath(*relative.split("/"))
        if entry.name.endswith("/"):
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(target, 0o700)
            continue
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(entry.content)
        os.chmod(target, 0o755 if entry.mode & 0o111 else 0o644)
    return package_tree_digest(root)


def _stage(
    stager: UserCopySnapshotStager,
    archive: bytes,
    tree_digest: str,
    *,
    operation_id: str = _OPERATION_ID,
) -> object:
    return stager.stage(
        operation_id=operation_id,
        archive=archive,
        expected_archive_digest=sha256(archive).hexdigest(),
        expected_package_tree_digest=tree_digest,
    )


def _assert_error(
    expected_code: str,
    action: Callable[[], object],
) -> MarketplaceOperationError:
    with pytest.raises(MarketplaceOperationError) as exc_info:
        action()
    assert exc_info.value.code == expected_code
    return exc_info.value


def _valid_entries() -> tuple[_ArchiveEntry, ...]:
    return (
        _ArchiveEntry("skills/demo/SKILL.md", b"# Demo\n"),
        _ArchiveEntry("skills/demo/run.sh", b"#!/bin/sh\n", mode=0o755),
    )


def _stage_valid_snapshot(
    tmp_path: Path,
    *,
    stager: UserCopySnapshotStager | None = None,
) -> tuple[UserCopySnapshotStager, object, bytes, str]:
    entries = _valid_entries()
    archive = _archive_bytes(*entries)
    tree_digest = _expected_tree_digest(tmp_path, *entries)
    snapshot_stager = stager or UserCopySnapshotStager(tmp_path / "snapshots")
    snapshot = _stage(snapshot_stager, archive, tree_digest)
    return snapshot_stager, snapshot, archive, tree_digest


def test_stage_reuses_verified_snapshot_and_normalizes_modes(
    tmp_path: Path,
) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)

    package_root = snapshot.package_root
    assert snapshot.entry_count == 4
    assert snapshot.total_bytes == len(b"# Demo\n") + len(b"#!/bin/sh\n")
    assert stat.S_IMODE(package_root.stat().st_mode) == 0o700
    assert stat.S_IMODE((package_root / "skills/demo/SKILL.md").stat().st_mode) == 0o600
    assert stat.S_IMODE((package_root / "skills/demo/run.sh").stat().st_mode) == 0o700
    assert _stage(stager, archive, tree_digest).package_root == package_root


def test_remove_is_idempotent_and_does_not_create_missing_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"
    stager = UserCopySnapshotStager(root)

    stager.remove(_OPERATION_ID)
    assert not root.exists()

    stager, snapshot, _archive, _digest = _stage_valid_snapshot(
        tmp_path,
        stager=stager,
    )
    stager.remove(_OPERATION_ID)
    stager.remove(_OPERATION_ID)
    assert not snapshot.package_root.exists()
    assert root.is_dir()


def test_load_strictly_reverifies_retained_snapshot(tmp_path: Path) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)

    loaded = stager.load(
        _OPERATION_ID,
        expected_archive_digest=sha256(archive).hexdigest(),
        expected_package_tree_digest=tree_digest,
    )

    assert loaded == snapshot
    _assert_error(
        "marketplace.user_copy.operation_conflict",
        lambda: stager.load(
            _OPERATION_ID,
            expected_archive_digest="0" * 64,
            expected_package_tree_digest=tree_digest,
        ),
    )


def test_load_rejects_missing_runtime_state(tmp_path: Path) -> None:
    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: UserCopySnapshotStager(tmp_path / "missing").load(
            _OPERATION_ID,
            expected_archive_digest="0" * 64,
            expected_package_tree_digest="0" * 64,
        ),
    )


@pytest.mark.parametrize("root_kind", ["file", "symlink"])
def test_stage_and_remove_reject_invalid_snapshot_root(
    tmp_path: Path,
    root_kind: str,
) -> None:
    root = tmp_path / "snapshots"
    if root_kind == "file":
        root.write_text("not a directory", encoding="utf-8")
    else:
        target = tmp_path / "external"
        target.mkdir()
        root.symlink_to(target, target_is_directory=True)
    archive = _archive_bytes(_ArchiveEntry("skill.txt", b"value"))
    stager = UserCopySnapshotStager(root)

    for action in (
        lambda: _stage(stager, archive, "0" * 64),
        lambda: stager.remove(_OPERATION_ID),
    ):
        error = _assert_error(
            "marketplace.user_copy.runtime_state_invalid",
            action,
        )
        assert error.http_status == 409


@pytest.mark.parametrize("operation_kind", ["file", "symlink"])
def test_stage_rejects_non_directory_operation_root(
    tmp_path: Path,
    operation_kind: str,
) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    operation_root = root / _OPERATION_ID
    if operation_kind == "file":
        operation_root.write_text("collision", encoding="utf-8")
    else:
        target = tmp_path / "external"
        target.mkdir()
        operation_root.symlink_to(target, target_is_directory=True)
    archive = _archive_bytes(_ArchiveEntry("skill.txt", b"value"))

    error = _assert_error(
        "marketplace.user_copy.operation_conflict",
        lambda: _stage(
            UserCopySnapshotStager(root),
            archive,
            "0" * 64,
        ),
    )
    assert error.http_status == 409


@pytest.mark.parametrize(
    ("operation_id", "archive_digest", "tree_digest", "expected_code"),
    [
        ("A" * 32, "0" * 64, "0" * 64, "operation_id_invalid"),
        ("a" * 31, "0" * 64, "0" * 64, "operation_id_invalid"),
        (_OPERATION_ID, "G" * 64, "0" * 64, "digest_invalid"),
        (_OPERATION_ID, "0" * 64, "f" * 63, "digest_invalid"),
    ],
)
def test_stage_rejects_noncanonical_identifiers_and_digests(
    tmp_path: Path,
    operation_id: str,
    archive_digest: str,
    tree_digest: str,
    expected_code: str,
) -> None:
    _assert_error(
        f"marketplace.user_copy.{expected_code}",
        lambda: UserCopySnapshotStager(tmp_path / "snapshots").stage(
            operation_id=operation_id,
            archive=b"",
            expected_archive_digest=archive_digest,
            expected_package_tree_digest=tree_digest,
        ),
    )


def test_stage_rejects_archive_size_and_digest_mismatch(tmp_path: Path) -> None:
    archive = _archive_bytes(_ArchiveEntry("skill.txt", b"value"))
    tree_digest = "0" * 64

    _assert_error(
        "marketplace.user_copy.archive_too_large",
        lambda: UserCopySnapshotStager(
            tmp_path / "size",
            limits=UserCopySnapshotLimits(max_archive_bytes=len(archive) - 1),
        ).stage(
            operation_id=_OPERATION_ID,
            archive=archive,
            expected_archive_digest=sha256(archive).hexdigest(),
            expected_package_tree_digest=tree_digest,
        ),
    )
    mismatch = _assert_error(
        "marketplace.user_copy.archive_digest_mismatch",
        lambda: UserCopySnapshotStager(tmp_path / "digest").stage(
            operation_id=_OPERATION_ID,
            archive=archive,
            expected_archive_digest="0" * 64,
            expected_package_tree_digest=tree_digest,
        ),
    )
    assert mismatch.http_status == 409


def test_stage_rejects_package_tree_digest_mismatch_and_cleans_temp(
    tmp_path: Path,
) -> None:
    archive = _archive_bytes(_ArchiveEntry("skill.txt", b"value"))
    root = tmp_path / "snapshots"

    error = _assert_error(
        "marketplace.user_copy.package_tree_digest_mismatch",
        lambda: _stage(
            UserCopySnapshotStager(root),
            archive,
            "0" * 64,
        ),
    )

    assert error.http_status == 409
    assert tuple(root.iterdir()) == ()


def test_truncated_archive_maps_to_archive_invalid(tmp_path: Path) -> None:
    archive = _archive_bytes(_ArchiveEntry("skill.txt", b"value"))[:-22]

    _assert_error(
        "marketplace.user_copy.archive_invalid",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


def test_crc_failure_maps_to_archive_invalid(tmp_path: Path) -> None:
    entry = _ArchiveEntry(
        "skill.txt",
        b"payload",
        compression=zipfile.ZIP_STORED,
    )
    archive = bytearray(_archive_bytes(entry))
    with zipfile.ZipFile(BytesIO(archive)) as reader:
        info = reader.getinfo(entry.name)
    name_size = int.from_bytes(
        archive[info.header_offset + 26 : info.header_offset + 28],
        "little",
    )
    extra_size = int.from_bytes(
        archive[info.header_offset + 28 : info.header_offset + 30],
        "little",
    )
    payload_offset = info.header_offset + 30 + name_size + extra_size
    archive[payload_offset] ^= 0x01
    corrupted = bytes(archive)

    _assert_error(
        "marketplace.user_copy.archive_invalid",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            corrupted,
            _expected_tree_digest(tmp_path, entry),
        ),
    )


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "../escape",
        "a/../escape",
        "./relative",
        "a//duplicate-separator",
        "C:/windows",
        "a\\windows",
        "e\u0301/non-nfc",
    ],
)
def test_stage_rejects_noncanonical_archive_paths(
    tmp_path: Path,
    path: str,
) -> None:
    archive = _archive_bytes(_ArchiveEntry(path, b"value"))

    _assert_error(
        "marketplace.user_copy.archive_entry_invalid",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


@pytest.mark.parametrize(
    ("path", "limits"),
    [
        (
            "12345",
            UserCopySnapshotLimits(max_path_bytes=4),
        ),
        (
            "12345/file",
            UserCopySnapshotLimits(max_component_bytes=4),
        ),
        (
            "a/b/c",
            UserCopySnapshotLimits(max_path_depth=2),
        ),
    ],
)
def test_stage_enforces_path_limits(
    tmp_path: Path,
    path: str,
    limits: UserCopySnapshotLimits,
) -> None:
    archive = _archive_bytes(_ArchiveEntry(path, b"value"))

    _assert_error(
        "marketplace.user_copy.archive_entry_invalid",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots", limits=limits),
            archive,
            "0" * 64,
        ),
    )


@pytest.mark.parametrize(
    "entries",
    [
        (
            _ArchiveEntry("skill.txt", b"one"),
            _ArchiveEntry("skill.txt", b"two"),
        ),
        (
            _ArchiveEntry("Skill.txt", b"one"),
            _ArchiveEntry("skill.txt", b"two"),
        ),
        (
            _ArchiveEntry(
                "Skills/",
                file_type=stat.S_IFDIR,
                dos_directory=True,
            ),
            _ArchiveEntry("skills/demo.txt", b"value"),
        ),
    ],
)
def test_stage_rejects_duplicate_and_casefold_paths(
    tmp_path: Path,
    entries: tuple[_ArchiveEntry, ...],
) -> None:
    archive = _archive_bytes(*entries)

    _assert_error(
        "marketplace.user_copy.archive_duplicate_path",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


@pytest.mark.parametrize(
    "entries",
    [
        (
            _ArchiveEntry("resource", b"file"),
            _ArchiveEntry("resource/child", b"child"),
        ),
        (
            _ArchiveEntry("resource/child", b"child"),
            _ArchiveEntry("resource", b"file"),
        ),
    ],
)
def test_stage_rejects_file_directory_prefix_collisions(
    tmp_path: Path,
    entries: tuple[_ArchiveEntry, ...],
) -> None:
    archive = _archive_bytes(*entries)

    _assert_error(
        "marketplace.user_copy.archive_path_collision",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


def test_implicit_directories_count_toward_entry_limit(tmp_path: Path) -> None:
    archive = _archive_bytes(_ArchiveEntry("a/b/file.txt", b"value"))

    _assert_error(
        "marketplace.user_copy.archive_entry_limit_exceeded",
        lambda: _stage(
            UserCopySnapshotStager(
                tmp_path / "snapshots",
                limits=UserCopySnapshotLimits(max_entries=2),
            ),
            archive,
            "0" * 64,
        ),
    )


@pytest.mark.parametrize(
    "entry",
    [
        _ArchiveEntry("directory/", file_type=stat.S_IFREG),
        _ArchiveEntry("file", file_type=stat.S_IFDIR),
        _ArchiveEntry("file", file_type=stat.S_IFIFO),
        _ArchiveEntry("file", dos_directory=True),
        _ArchiveEntry(
            "directory/",
            content=b"not empty",
            file_type=stat.S_IFDIR,
            dos_directory=True,
        ),
    ],
)
def test_stage_rejects_external_entry_type_mismatch(
    tmp_path: Path,
    entry: _ArchiveEntry,
) -> None:
    archive = _archive_bytes(entry)

    _assert_error(
        "marketplace.user_copy.archive_entry_type_invalid",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


def test_stage_rejects_archive_symlink(tmp_path: Path) -> None:
    archive = _archive_bytes(
        _ArchiveEntry(
            "link",
            b"target",
            file_type=stat.S_IFLNK,
            mode=0o777,
        )
    )

    _assert_error(
        "marketplace.user_copy.archive_symlink_rejected",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


def test_stage_rejects_unsupported_compression(tmp_path: Path) -> None:
    archive = _archive_bytes(
        _ArchiveEntry(
            "skill.txt",
            b"value",
            compression=zipfile.ZIP_BZIP2,
        )
    )

    _assert_error(
        "marketplace.user_copy.archive_compression_unsupported",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots"),
            archive,
            "0" * 64,
        ),
    )


@pytest.mark.parametrize(
    ("entries", "limits", "expected_code"),
    [
        (
            (_ArchiveEntry("large", b"1234"),),
            UserCopySnapshotLimits(max_entry_bytes=3),
            "archive_entry_limit_exceeded",
        ),
        (
            (
                _ArchiveEntry("one", b"123"),
                _ArchiveEntry("two", b"456"),
            ),
            UserCopySnapshotLimits(max_total_bytes=5),
            "archive_total_limit_exceeded",
        ),
        (
            (_ArchiveEntry("compressed", b"0" * 2_048),),
            UserCopySnapshotLimits(max_compression_ratio=1),
            "archive_compression_ratio_exceeded",
        ),
    ],
)
def test_stage_enforces_entry_total_and_compression_limits(
    tmp_path: Path,
    entries: tuple[_ArchiveEntry, ...],
    limits: UserCopySnapshotLimits,
    expected_code: str,
) -> None:
    archive = _archive_bytes(*entries)

    _assert_error(
        f"marketplace.user_copy.{expected_code}",
        lambda: _stage(
            UserCopySnapshotStager(tmp_path / "snapshots", limits=limits),
            archive,
            "0" * 64,
        ),
    )


def test_existing_snapshot_rejects_oversized_metadata(tmp_path: Path) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)
    metadata_path = snapshot.package_root.parent / "snapshot.json"
    metadata_path.write_bytes(b" " * (stager.limits.max_metadata_bytes + 1))
    os.chmod(metadata_path, 0o600)

    error = _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: _stage(stager, archive, tree_digest),
    )
    assert error.http_status == 409


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entryCount", True),
        ("fileCount", -1),
        ("totalBytes", -1),
    ],
)
def test_existing_snapshot_rejects_invalid_metadata_counts(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)
    metadata_path = snapshot.package_root.parent / "snapshot.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata[field] = value
    metadata_path.write_text(
        json.dumps(metadata, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    os.chmod(metadata_path, 0o600)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: _stage(stager, archive, tree_digest),
    )


def test_existing_snapshot_rejects_unexpected_operation_child(
    tmp_path: Path,
) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)
    unexpected = snapshot.package_root.parent / "unexpected"
    unexpected.write_text("state", encoding="utf-8")
    os.chmod(unexpected, 0o600)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: _stage(stager, archive, tree_digest),
    )


@pytest.mark.parametrize("mutation", ["symlink", "fifo", "mode"])
def test_existing_snapshot_rejects_unsafe_tree_entries(
    tmp_path: Path,
    mutation: str,
) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)
    package_root = snapshot.package_root
    if mutation == "symlink":
        (package_root / "unsafe").symlink_to(tmp_path / "outside")
    elif mutation == "fifo":
        os.mkfifo(package_root / "unsafe")
    else:
        os.chmod(package_root / "skills/demo/SKILL.md", 0o644)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: _stage(stager, archive, tree_digest),
    )


def test_existing_snapshot_maps_directory_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stager, snapshot, archive, tree_digest = _stage_valid_snapshot(tmp_path)
    real_scandir = os.scandir

    def failing_scandir(path: str | os.PathLike[str]) -> object:
        if Path(path) == snapshot.package_root:
            raise PermissionError("denied")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", failing_scandir)
    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: _stage(stager, archive, tree_digest),
    )


def test_stage_rejects_stale_temp_until_remove_cleans_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    stale = root / f".{_OPERATION_ID}.abcdefgh.tmp"
    stale.mkdir(mode=0o700)
    partial = stale / "partial"
    partial.write_text("state", encoding="utf-8")
    archive = _archive_bytes(_ArchiveEntry("skill.txt", b"value"))
    tree_digest = _expected_tree_digest(
        tmp_path,
        _ArchiveEntry("skill.txt", b"value"),
    )
    stager = UserCopySnapshotStager(root)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: _stage(stager, archive, tree_digest),
    )
    assert stale.exists()

    stager.remove(_OPERATION_ID)
    assert not stale.exists()
    assert _stage(stager, archive, tree_digest).package_root.is_dir()


def test_startup_recovery_removes_safe_stale_temp_and_lists_operations(
    tmp_path: Path,
) -> None:
    stager, _snapshot, _archive, _tree_digest = _stage_valid_snapshot(tmp_path)
    stale = stager.root / f".{_OTHER_OPERATION_ID}.abcdefgh.tmp"
    nested = stale / "snapshot" / "nested"
    nested.mkdir(parents=True)
    (nested / "partial").write_text("state", encoding="utf-8")

    operation_ids = stager.recover_startup_state()

    assert operation_ids == (_OPERATION_ID,)
    assert not stale.exists()


@pytest.mark.parametrize(
    "invalid_entry",
    [
        "unknown",
        f"{_OTHER_OPERATION_ID}.tmp",
        f".{_OTHER_OPERATION_ID}.short.tmp",
    ],
)
def test_startup_recovery_rejects_unknown_root_entries(
    tmp_path: Path,
    invalid_entry: str,
) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    (root / invalid_entry).write_text("state", encoding="utf-8")

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: UserCopySnapshotStager(root).recover_startup_state(),
    )


@pytest.mark.parametrize("entry_kind", ["operation-symlink", "temp-symlink"])
def test_startup_recovery_rejects_symlink_without_following_it(
    tmp_path: Path,
    entry_kind: str,
) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    if entry_kind == "operation-symlink":
        entry = root / _OPERATION_ID
    else:
        entry = root / f".{_OPERATION_ID}.abcdefgh.tmp"
    entry.symlink_to(external, target_is_directory=True)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: UserCopySnapshotStager(root).recover_startup_state(),
    )
    assert entry.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_remove_rejects_stale_temp_symlink_without_following_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    stale = root / f".{_OPERATION_ID}.abcdefgh.tmp"
    stale.symlink_to(external, target_is_directory=True)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: UserCopySnapshotStager(root).remove(_OPERATION_ID),
    )
    assert stale.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_malformed_operation_temp_is_not_removed(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    malformed = root / f".{_OPERATION_ID}.short.tmp"
    malformed.mkdir()
    stager = UserCopySnapshotStager(root)

    _assert_error(
        "marketplace.user_copy.runtime_state_invalid",
        lambda: stager.remove(_OPERATION_ID),
    )
    assert malformed.is_dir()


def test_remove_leaves_unrelated_temp_state_untouched(tmp_path: Path) -> None:
    root = tmp_path / "snapshots"
    root.mkdir(mode=0o700)
    unrelated = root / f".{_OTHER_OPERATION_ID}.abcdefgh.tmp"
    unrelated.mkdir(mode=0o700)

    UserCopySnapshotStager(root).remove(_OPERATION_ID)

    assert unrelated.is_dir()
