"""Operation-bound canonical snapshot staging for one-shot user copies."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

from aileron_marketplace_core import PackageTreeError, package_tree_digest

from app.modules.cli_settings.user_scope.codecs import fsync_directory

from .errors import MarketplaceOperationError
from .state import write_json_atomic

_READ_CHUNK_BYTES = 1024 * 1024
_TEMPORARY_ROOT_PATTERN = re.compile(
    r"^\.(?P<operation_id>[0-9a-f]{32})\.[a-z0-9_]{8}\.tmp$"
)
_ARCHIVE_CORRUPTION_ERRORS = (
    EOFError,
    zipfile.BadZipFile,
    zlib.error,
)


@dataclass(frozen=True)
class UserCopySnapshotLimits:
    """Hard limits applied before and during ZIP extraction."""

    max_archive_bytes: int = 50 * 1024 * 1024
    max_entries: int = 2_000
    max_entry_bytes: int = 20 * 1024 * 1024
    max_total_bytes: int = 100 * 1024 * 1024
    max_compression_ratio: int = 100
    max_path_bytes: int = 1_024
    max_component_bytes: int = 255
    max_path_depth: int = 32
    max_metadata_bytes: int = 16 * 1024


@dataclass(frozen=True)
class UserCopySnapshot:
    """Verified sparse canonical package snapshot."""

    operation_id: str
    package_root: Path
    archive_digest: str
    package_tree_digest: str
    entry_count: int
    total_bytes: int


@dataclass(frozen=True)
class _PlannedArchiveEntry:
    info: zipfile.ZipInfo
    relative_path: str
    is_directory: bool
    executable: bool


class UserCopySnapshotStager:
    """Safely extract one authenticated Manager ZIP into Runtime state."""

    def __init__(
        self,
        root: Path,
        *,
        limits: UserCopySnapshotLimits | None = None,
    ) -> None:
        self.root = root
        self.limits = limits or UserCopySnapshotLimits()

    def stage(
        self,
        *,
        operation_id: str,
        archive: bytes,
        expected_archive_digest: str,
        expected_package_tree_digest: str,
    ) -> UserCopySnapshot:
        """Verify, extract, and rehash one operation-bound snapshot."""

        _validate_operation_id(operation_id)
        _validate_digest(expected_archive_digest)
        _validate_digest(expected_package_tree_digest)
        if len(archive) > self.limits.max_archive_bytes:
            raise _snapshot_error("archive_too_large")
        archive_digest = sha256(archive).hexdigest()
        if archive_digest != expected_archive_digest:
            raise _snapshot_error("archive_digest_mismatch", http_status=409)

        self._ensure_root()
        if self._temporary_roots(operation_id):
            raise _snapshot_error("runtime_state_invalid", http_status=409)

        operation_root = self.root / operation_id
        operation_stat = self._lstat(operation_root)
        if operation_stat is not None:
            if not stat.S_ISDIR(operation_stat.st_mode):
                raise _snapshot_error("operation_conflict", http_status=409)
            return self._existing_snapshot(
                operation_id,
                expected_archive_digest=expected_archive_digest,
                expected_package_tree_digest=expected_package_tree_digest,
            )

        try:
            temporary_root = Path(
                tempfile.mkdtemp(
                    prefix=f".{operation_id}.",
                    suffix=".tmp",
                    dir=str(self.root),
                )
            )
            os.chmod(temporary_root, 0o700)
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

        package_root = temporary_root / "snapshot"
        published = False
        try:
            package_root.mkdir(mode=0o700)
            os.chmod(package_root, 0o700)
            entry_count, file_count, total_bytes = self._extract(
                archive,
                package_root,
            )
            try:
                tree_digest = package_tree_digest(package_root)
            except PackageTreeError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc
            if tree_digest != expected_package_tree_digest:
                raise _snapshot_error(
                    "package_tree_digest_mismatch",
                    http_status=409,
                )
            write_json_atomic(
                temporary_root / "snapshot.json",
                {
                    "snapshotVersion": 1,
                    "operationId": operation_id,
                    "archiveDigest": archive_digest,
                    "packageTreeDigest": tree_digest,
                    "entryCount": entry_count,
                    "fileCount": file_count,
                    "totalBytes": total_bytes,
                },
            )
            try:
                os.replace(temporary_root, operation_root)
            except OSError as exc:
                if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise _snapshot_error(
                        "operation_conflict",
                        http_status=409,
                    ) from exc
                raise
            published = True
            fsync_directory(self.root)
        except MarketplaceOperationError:
            self._cleanup_failed_stage(
                temporary_root=temporary_root,
                operation_root=operation_root,
                published=published,
            )
            raise
        except OSError as exc:
            mapped = _snapshot_error("runtime_state_invalid", http_status=409)
            self._cleanup_failed_stage(
                temporary_root=temporary_root,
                operation_root=operation_root,
                published=published,
            )
            raise mapped from exc

        return UserCopySnapshot(
            operation_id=operation_id,
            package_root=operation_root / "snapshot",
            archive_digest=archive_digest,
            package_tree_digest=tree_digest,
            entry_count=entry_count,
            total_bytes=total_bytes,
        )

    def remove(self, operation_id: str) -> None:
        """Remove only this operation's verified or partial snapshot state."""

        _validate_operation_id(operation_id)
        if not self._validate_root(create=False):
            return

        operation_root = self.root / operation_id
        targets = list(self._temporary_roots(operation_id))
        operation_stat = self._lstat(operation_root)
        if operation_stat is not None:
            if not stat.S_ISDIR(operation_stat.st_mode):
                raise _snapshot_error("runtime_state_invalid", http_status=409)
            targets.append(operation_root)

        for target in targets:
            self._validate_removal_tree(target)
        try:
            for target in targets:
                shutil.rmtree(target)
            if targets:
                fsync_directory(self.root)
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

    def load(
        self,
        operation_id: str,
        *,
        expected_archive_digest: str,
        expected_package_tree_digest: str,
    ) -> UserCopySnapshot:
        """Load and fully reverify one snapshot retained for crash recovery."""

        _validate_operation_id(operation_id)
        _validate_digest(expected_archive_digest)
        _validate_digest(expected_package_tree_digest)
        if not self._validate_root(create=False):
            raise _snapshot_error("runtime_state_invalid", http_status=409)
        if self._temporary_roots(operation_id):
            raise _snapshot_error("runtime_state_invalid", http_status=409)
        operation_stat = self._lstat(self.root / operation_id)
        if operation_stat is None or not stat.S_ISDIR(operation_stat.st_mode):
            raise _snapshot_error("runtime_state_invalid", http_status=409)
        return self._existing_snapshot(
            operation_id,
            expected_archive_digest=expected_archive_digest,
            expected_package_tree_digest=expected_package_tree_digest,
        )

    def recover_startup_state(self) -> tuple[str, ...]:
        """Delete safe stale extraction roots and list retained operations."""

        if not self._validate_root(create=False):
            return ()
        try:
            entries = tuple(os.scandir(self.root))
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

        operation_ids: list[str] = []
        stale_roots: list[Path] = []
        for entry in entries:
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc
            if _is_operation_id(entry.name):
                if not stat.S_ISDIR(entry_stat.st_mode):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                operation_ids.append(entry.name)
                continue
            temporary_match = _TEMPORARY_ROOT_PATTERN.fullmatch(entry.name)
            if temporary_match is None or not stat.S_ISDIR(entry_stat.st_mode):
                raise _snapshot_error("runtime_state_invalid", http_status=409)
            stale_roots.append(Path(entry.path))

        for stale_root in stale_roots:
            self._validate_removal_tree(stale_root)
        try:
            for stale_root in stale_roots:
                shutil.rmtree(stale_root)
            if stale_roots:
                fsync_directory(self.root)
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc
        return tuple(sorted(operation_ids))

    def _ensure_root(self) -> None:
        self._validate_root(create=True)

    def _validate_root(self, *, create: bool) -> bool:
        root_stat = self._lstat(self.root)
        if root_stat is None:
            if not create:
                return False
            try:
                self.root.mkdir(parents=True, mode=0o700)
            except FileExistsError:
                pass
            except OSError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc
            root_stat = self._lstat(self.root)
        if root_stat is None or not stat.S_ISDIR(root_stat.st_mode):
            raise _snapshot_error("runtime_state_invalid", http_status=409)

        flags = os.O_RDONLY
        flags |= getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.root, flags)
            try:
                opened_stat = os.fstat(descriptor)
                if not stat.S_ISDIR(opened_stat.st_mode):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                os.fchmod(descriptor, 0o700)
            finally:
                os.close(descriptor)
        except MarketplaceOperationError:
            raise
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc
        return True

    def _existing_snapshot(
        self,
        operation_id: str,
        *,
        expected_archive_digest: str,
        expected_package_tree_digest: str,
    ) -> UserCopySnapshot:
        operation_root = self.root / operation_id
        metadata_path = operation_root / "snapshot.json"
        package_root = operation_root / "snapshot"
        operation_stat = self._lstat(operation_root)
        metadata_stat = self._lstat(metadata_path)
        package_stat = self._lstat(package_root)
        if (
            operation_stat is None
            or not stat.S_ISDIR(operation_stat.st_mode)
            or metadata_stat is None
            or not stat.S_ISREG(metadata_stat.st_mode)
            or metadata_stat.st_nlink != 1
            or package_stat is None
            or not stat.S_ISDIR(package_stat.st_mode)
        ):
            raise _snapshot_error("operation_conflict", http_status=409)
        if (
            stat.S_IMODE(operation_stat.st_mode) != 0o700
            or stat.S_IMODE(metadata_stat.st_mode) != 0o600
            or stat.S_IMODE(package_stat.st_mode) != 0o700
        ):
            raise _snapshot_error("runtime_state_invalid", http_status=409)

        metadata = self._read_metadata(metadata_path)
        if (
            not isinstance(metadata, dict)
            or set(metadata)
            != {
                "snapshotVersion",
                "operationId",
                "archiveDigest",
                "packageTreeDigest",
                "entryCount",
                "fileCount",
                "totalBytes",
            }
            or metadata.get("snapshotVersion") != 1
            or metadata.get("operationId") != operation_id
            or metadata.get("archiveDigest") != expected_archive_digest
            or metadata.get("packageTreeDigest") != expected_package_tree_digest
        ):
            raise _snapshot_error("operation_conflict", http_status=409)

        try:
            child_names = {child.name for child in os.scandir(operation_root)}
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc
        if child_names != {"snapshot", "snapshot.json"}:
            raise _snapshot_error("runtime_state_invalid", http_status=409)

        entry_count = metadata.get("entryCount")
        file_count = metadata.get("fileCount")
        total_bytes = metadata.get("totalBytes")
        if (
            type(entry_count) is not int
            or type(file_count) is not int
            or type(total_bytes) is not int
            or not 0 <= entry_count <= self.limits.max_entries
            or not 0 <= file_count <= entry_count
            or not 0 <= total_bytes <= self.limits.max_total_bytes
        ):
            raise _snapshot_error("runtime_state_invalid", http_status=409)

        (
            actual_entry_count,
            actual_file_count,
            actual_total_bytes,
        ) = self._validate_existing_tree(package_root)
        try:
            actual_tree_digest = package_tree_digest(package_root)
        except PackageTreeError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc
        if (
            actual_entry_count != entry_count
            or actual_file_count != file_count
            or actual_total_bytes != total_bytes
            or actual_tree_digest != expected_package_tree_digest
        ):
            raise _snapshot_error("runtime_state_invalid", http_status=409)
        return UserCopySnapshot(
            operation_id=operation_id,
            package_root=package_root,
            archive_digest=expected_archive_digest,
            package_tree_digest=expected_package_tree_digest,
            entry_count=entry_count,
            total_bytes=total_bytes,
        )

    def _read_metadata(self, metadata_path: Path) -> object:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(metadata_path, flags)
            try:
                opened_stat = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened_stat.st_mode)
                    or opened_stat.st_nlink != 1
                    or opened_stat.st_size > self.limits.max_metadata_bytes
                ):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                with os.fdopen(descriptor, "rb", closefd=False) as handle:
                    payload = handle.read(self.limits.max_metadata_bytes + 1)
            finally:
                os.close(descriptor)
        except MarketplaceOperationError:
            raise
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc
        if len(payload) > self.limits.max_metadata_bytes:
            raise _snapshot_error("runtime_state_invalid", http_status=409)
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

    def _extract(
        self,
        archive: bytes,
        package_root: Path,
    ) -> tuple[int, int, int]:
        try:
            zip_file = zipfile.ZipFile(_BytesReader(archive))
        except _ARCHIVE_CORRUPTION_ERRORS as exc:
            raise _snapshot_error("archive_invalid") from exc

        with zip_file:
            try:
                infos = zip_file.infolist()
            except _ARCHIVE_CORRUPTION_ERRORS as exc:
                raise _snapshot_error("archive_invalid") from exc
            planned, planned_entry_count, file_count, total_bytes = self._plan_entries(
                infos
            )
            try:
                for entry in planned:
                    destination = package_root.joinpath(
                        *PurePosixPath(entry.relative_path).parts
                    )
                    if entry.is_directory:
                        destination.mkdir(
                            parents=True,
                            exist_ok=True,
                            mode=0o700,
                        )
                        self._normalize_directory_chain(
                            destination,
                            package_root,
                        )
                        continue
                    destination.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                        mode=0o700,
                    )
                    self._normalize_directory_chain(
                        destination.parent,
                        package_root,
                    )
                    self._extract_file(
                        zip_file,
                        entry.info,
                        destination,
                        executable=entry.executable,
                    )
            except MarketplaceOperationError:
                raise
            except OSError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc

        actual_entry_count, actual_file_count, actual_total_bytes = (
            self._validate_existing_tree(package_root)
        )
        if (
            actual_entry_count != planned_entry_count
            or actual_file_count != file_count
            or actual_total_bytes != total_bytes
        ):
            raise _snapshot_error("archive_invalid")

        directories = [
            package_root,
            *(
                path
                for path in package_root.rglob("*")
                if path.is_dir() and not path.is_symlink()
            ),
        ]
        try:
            for directory in sorted(
                directories,
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                fsync_directory(directory)
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc
        return actual_entry_count, actual_file_count, actual_total_bytes

    def _plan_entries(
        self,
        infos: list[zipfile.ZipInfo],
    ) -> tuple[list[_PlannedArchiveEntry], int, int, int]:
        if len(infos) > self.limits.max_entries:
            raise _snapshot_error("archive_entry_limit_exceeded")

        planned: list[_PlannedArchiveEntry] = []
        explicit_paths: dict[str, str] = {}
        node_types: dict[str, tuple[str, bool]] = {}
        file_count = 0
        total_bytes = 0
        for info in infos:
            if info.flag_bits & 0x1:
                raise _snapshot_error("archive_encrypted")
            if info.compress_type not in {
                zipfile.ZIP_STORED,
                zipfile.ZIP_DEFLATED,
            }:
                raise _snapshot_error("archive_compression_unsupported")
            if (
                type(info.file_size) is not int
                or type(info.compress_size) is not int
                or info.file_size < 0
                or info.compress_size < 0
            ):
                raise _snapshot_error("archive_invalid")

            normalized = _normalize_entry(info.filename, limits=self.limits)
            folded = normalized.casefold()
            if folded in explicit_paths:
                raise _snapshot_error("archive_duplicate_path")
            explicit_paths[folded] = normalized

            unix_mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(unix_mode)
            if file_type == stat.S_IFLNK:
                raise _snapshot_error("archive_symlink_rejected")
            if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise _snapshot_error("archive_entry_type_invalid")
            is_directory = info.filename.endswith("/")
            dos_directory = bool(info.external_attr & 0x10)
            if (
                (file_type == stat.S_IFDIR and not is_directory)
                or (file_type == stat.S_IFREG and is_directory)
                or (dos_directory and not is_directory)
            ):
                raise _snapshot_error("archive_entry_type_invalid")
            if is_directory and info.file_size != 0:
                raise _snapshot_error("archive_entry_type_invalid")

            parts = PurePosixPath(normalized).parts
            for index in range(1, len(parts) + 1):
                node_path = "/".join(parts[:index])
                node_folded = node_path.casefold()
                node_is_directory = index < len(parts) or is_directory
                existing = node_types.get(node_folded)
                if existing is None:
                    node_types[node_folded] = (node_path, node_is_directory)
                    continue
                existing_path, existing_is_directory = existing
                if existing_path != node_path:
                    raise _snapshot_error("archive_duplicate_path")
                if existing_is_directory != node_is_directory:
                    raise _snapshot_error("archive_path_collision")

            if len(node_types) > self.limits.max_entries:
                raise _snapshot_error("archive_entry_limit_exceeded")
            if not is_directory:
                if info.file_size > self.limits.max_entry_bytes:
                    raise _snapshot_error("archive_entry_limit_exceeded")
                total_bytes += info.file_size
                if total_bytes > self.limits.max_total_bytes:
                    raise _snapshot_error("archive_total_limit_exceeded")
                compressed_size = max(info.compress_size, 1)
                if info.file_size > self.limits.max_compression_ratio * compressed_size:
                    raise _snapshot_error("archive_compression_ratio_exceeded")
                file_count += 1
            planned.append(
                _PlannedArchiveEntry(
                    info=info,
                    relative_path=normalized,
                    is_directory=is_directory,
                    executable=bool(unix_mode & 0o111),
                )
            )
        return planned, len(node_types), file_count, total_bytes

    def _validate_existing_tree(
        self,
        package_root: Path,
    ) -> tuple[int, int, int]:
        package_stat = self._lstat(package_root)
        if (
            package_stat is None
            or not stat.S_ISDIR(package_stat.st_mode)
            or stat.S_IMODE(package_stat.st_mode) != 0o700
        ):
            raise _snapshot_error("runtime_state_invalid", http_status=409)

        entry_count = 0
        file_count = 0
        total_bytes = 0
        seen_paths: dict[str, str] = {}
        pending = [package_root]
        while pending:
            directory = pending.pop()
            try:
                children = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc
            for child in children:
                try:
                    child_stat = child.stat(follow_symlinks=False)
                except OSError as exc:
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    ) from exc
                child_path = Path(child.path)
                relative_path = child_path.relative_to(package_root).as_posix()
                try:
                    canonical_path = _normalize_entry(
                        relative_path,
                        limits=self.limits,
                    )
                except MarketplaceOperationError as exc:
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    ) from exc
                folded = canonical_path.casefold()
                if folded in seen_paths:
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                seen_paths[folded] = canonical_path

                entry_count += 1
                if entry_count > self.limits.max_entries:
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                if stat.S_ISLNK(child_stat.st_mode):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                if stat.S_ISDIR(child_stat.st_mode):
                    if stat.S_IMODE(child_stat.st_mode) != 0o700:
                        raise _snapshot_error(
                            "runtime_state_invalid",
                            http_status=409,
                        )
                    pending.append(child_path)
                    continue
                if not stat.S_ISREG(child_stat.st_mode):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                if (
                    child_stat.st_nlink != 1
                    or stat.S_IMODE(child_stat.st_mode) not in {0o600, 0o700}
                    or child_stat.st_size > self.limits.max_entry_bytes
                ):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
                file_count += 1
                total_bytes += child_stat.st_size
                if (
                    file_count > self.limits.max_entries
                    or total_bytes > self.limits.max_total_bytes
                ):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )
        return entry_count, file_count, total_bytes

    def _extract_file(
        self,
        archive: zipfile.ZipFile,
        info: zipfile.ZipInfo,
        destination: Path,
        *,
        executable: bool,
    ) -> None:
        normalized_mode = 0o700 if executable else 0o600
        try:
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                normalized_mode,
            )
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

        try:
            with os.fdopen(descriptor, "wb") as target:
                try:
                    with archive.open(info, "r") as source:
                        written = 0
                        while True:
                            chunk = source.read(_READ_CHUNK_BYTES)
                            if not chunk:
                                break
                            written += len(chunk)
                            if (
                                written > info.file_size
                                or written > self.limits.max_entry_bytes
                            ):
                                raise _snapshot_error("archive_entry_limit_exceeded")
                            target.write(chunk)
                except _ARCHIVE_CORRUPTION_ERRORS as exc:
                    raise _snapshot_error("archive_invalid") from exc
                if written != info.file_size:
                    raise _snapshot_error("archive_invalid")
                target.flush()
                os.fchmod(target.fileno(), normalized_mode)
                os.fsync(target.fileno())
        except MarketplaceOperationError:
            self._unlink_failed_destination(destination)
            raise
        except OSError as exc:
            mapped = _snapshot_error("runtime_state_invalid", http_status=409)
            self._unlink_failed_destination(destination)
            raise mapped from exc

    def _temporary_roots(self, operation_id: str) -> tuple[Path, ...]:
        prefix = f".{operation_id}."
        try:
            entries = tuple(os.scandir(self.root))
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

        temporary_roots: list[Path] = []
        for entry in entries:
            if not entry.name.startswith(prefix) or not entry.name.endswith(".tmp"):
                continue
            match = _TEMPORARY_ROOT_PATTERN.fullmatch(entry.name)
            if match is None or match.group("operation_id") != operation_id:
                raise _snapshot_error("runtime_state_invalid", http_status=409)
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc
            if not stat.S_ISDIR(entry_stat.st_mode):
                raise _snapshot_error("runtime_state_invalid", http_status=409)
            temporary_roots.append(Path(entry.path))
        return tuple(sorted(temporary_roots))

    def _validate_removal_tree(self, root: Path) -> None:
        root_stat = self._lstat(root)
        if root_stat is None or not stat.S_ISDIR(root_stat.st_mode):
            raise _snapshot_error("runtime_state_invalid", http_status=409)
        pending = [root]
        while pending:
            directory = pending.pop()
            try:
                children = tuple(os.scandir(directory))
            except OSError as exc:
                raise _snapshot_error(
                    "runtime_state_invalid",
                    http_status=409,
                ) from exc
            for child in children:
                try:
                    child_stat = child.stat(follow_symlinks=False)
                except OSError as exc:
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    ) from exc
                if stat.S_ISDIR(child_stat.st_mode):
                    pending.append(Path(child.path))
                    continue
                if not stat.S_ISREG(child_stat.st_mode):
                    raise _snapshot_error(
                        "runtime_state_invalid",
                        http_status=409,
                    )

    def _normalize_directory_chain(
        self,
        directory: Path,
        package_root: Path,
    ) -> None:
        try:
            directory.relative_to(package_root)
        except ValueError as exc:
            raise _snapshot_error(
                "runtime_state_invalid",
                http_status=409,
            ) from exc
        current = directory
        while True:
            os.chmod(current, 0o700)
            if current == package_root:
                return
            if current == current.parent:
                raise _snapshot_error("runtime_state_invalid", http_status=409)
            current = current.parent

    def _cleanup_failed_stage(
        self,
        *,
        temporary_root: Path,
        operation_root: Path,
        published: bool,
    ) -> None:
        target = operation_root if published else temporary_root
        target_stat = self._lstat(target)
        if target_stat is None:
            return
        try:
            self._validate_removal_tree(target)
            shutil.rmtree(target)
            fsync_directory(self.root)
        except MarketplaceOperationError:
            raise
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

    def _unlink_failed_destination(
        self,
        destination: Path,
    ) -> None:
        try:
            destination.unlink(missing_ok=True)
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc

    def _lstat(self, path: Path) -> os.stat_result | None:
        try:
            return path.lstat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise _snapshot_error("runtime_state_invalid", http_status=409) from exc


class _BytesReader:
    """Minimal seekable bytes adapter accepted by zipfile."""

    def __init__(self, content: bytes) -> None:
        from io import BytesIO

        self._buffer: BinaryIO = BytesIO(content)

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buffer.seek(offset, whence)

    def tell(self) -> int:
        return self._buffer.tell()

    def seekable(self) -> bool:
        return True


def _normalize_entry(
    value: str,
    *,
    limits: UserCopySnapshotLimits,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or unicodedata.normalize("NFC", value) != value
    ):
        raise _snapshot_error("archive_entry_invalid")
    normalized = value[:-1] if value.endswith("/") else value
    if not normalized or normalized.endswith("/"):
        raise _snapshot_error("archive_entry_invalid")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(normalized)
    try:
        encoded_path = normalized.encode("utf-8")
        encoded_parts = tuple(part.encode("utf-8") for part in posix.parts)
    except UnicodeEncodeError as exc:
        raise _snapshot_error("archive_entry_invalid") from exc
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or any(part in {"", ".", ".."} for part in posix.parts)
        or normalized != posix.as_posix()
        or len(encoded_path) > limits.max_path_bytes
        or len(posix.parts) > limits.max_path_depth
        or any(len(part) > limits.max_component_bytes for part in encoded_parts)
    ):
        raise _snapshot_error("archive_entry_invalid")
    return posix.as_posix()


def _validate_operation_id(value: str) -> None:
    if not _is_operation_id(value):
        raise _snapshot_error("operation_id_invalid")


def _is_operation_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_digest(value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _snapshot_error("digest_invalid")


def _snapshot_error(
    suffix: str,
    *,
    http_status: int = 400,
) -> MarketplaceOperationError:
    return MarketplaceOperationError(
        f"marketplace.user_copy.{suffix}",
        http_status=http_status,
    )
