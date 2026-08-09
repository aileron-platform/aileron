"""Bounded capacity measurement for Runtime-owned filesystem roots."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .models import CapacityMeasurement, StorageKind

RootReader = Callable[[Path], tuple[int, int, int]]


class CapacityProbe(Protocol):
    async def measure(self) -> tuple[CapacityMeasurement, ...]: ...


class CapacityProbeInProgress(RuntimeError):
    pass


def _read_root_usage(root: Path) -> tuple[int, int, int]:
    root_stat = root.stat(follow_symlinks=False)
    root_device = root_stat.st_dev
    used_bytes = 0
    pending = [root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if os.path.ismount(entry.path):
                    continue
                entry_stat = entry.stat(follow_symlinks=False)
                if entry_stat.st_dev != root_device:
                    continue
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    used_bytes += entry_stat.st_size

    filesystem = os.statvfs(root)
    capacity_bytes = filesystem.f_blocks * filesystem.f_frsize
    available_bytes = filesystem.f_bavail * filesystem.f_frsize
    return used_bytes, capacity_bytes, available_bytes


class FilesystemCapacityProbe:
    """Measure project data and Runtime HOME without crossing filesystem seams."""

    def __init__(
        self,
        *,
        workspace_path: Path,
        runtime_home_path: Path,
        timeout_seconds: float,
        root_reader: RootReader = _read_root_usage,
    ) -> None:
        self._workspace_path = workspace_path
        self._runtime_home_path = runtime_home_path
        self._timeout_seconds = timeout_seconds
        self._root_reader = root_reader
        self._scan_task: asyncio.Task[tuple[CapacityMeasurement, ...]] | None = None

    async def measure(self) -> tuple[CapacityMeasurement, ...]:
        if self._scan_task is not None and not self._scan_task.done():
            raise CapacityProbeInProgress("Capacity probe is already running")
        self._scan_task = asyncio.create_task(
            asyncio.to_thread(self._measure_synchronously)
        )
        task = self._scan_task
        task.add_done_callback(self._clear_finished_task)
        return await asyncio.wait_for(
            asyncio.shield(task),
            timeout=self._timeout_seconds,
        )

    def _clear_finished_task(
        self, task: asyncio.Task[tuple[CapacityMeasurement, ...]]
    ) -> None:
        with suppress(asyncio.CancelledError, Exception):
            task.exception()
        if self._scan_task is task:
            self._scan_task = None

    def _measure_synchronously(self) -> tuple[CapacityMeasurement, ...]:
        observed_at = datetime.now(timezone.utc)
        values: list[CapacityMeasurement] = []
        roots: tuple[tuple[StorageKind, Path], ...] = (
            ("workspace_data", self._workspace_path),
            ("runtime_home", self._runtime_home_path),
        )
        for storage_kind, root in roots:
            used_bytes, capacity_bytes, available_bytes = self._root_reader(root)
            values.append(
                CapacityMeasurement(
                    storage_kind=storage_kind,
                    used_bytes=used_bytes,
                    capacity_bytes=capacity_bytes,
                    available_bytes=available_bytes,
                    observed_at=observed_at,
                )
            )
        return tuple(values)


__all__ = [
    "CapacityProbe",
    "CapacityProbeInProgress",
    "FilesystemCapacityProbe",
]
