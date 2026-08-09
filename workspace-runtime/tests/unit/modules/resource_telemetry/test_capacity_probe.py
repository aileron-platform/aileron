from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.modules.resource_telemetry.capacity import (
    CapacityProbeInProgress,
    FilesystemCapacityProbe,
)


@pytest.mark.asyncio
async def test_probe_measures_only_workspace_and_runtime_home_without_following_symlinks(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    runtime_home = tmp_path / "runtime-home"
    knowledge = tmp_path / "knowledge"
    workspace.mkdir()
    runtime_home.mkdir()
    knowledge.mkdir()
    (workspace / "project.bin").write_bytes(b"workspace")
    (runtime_home / "settings.bin").write_bytes(b"home")
    (knowledge / "content.bin").write_bytes(b"knowledge-content")
    (workspace / "knowledge-link").symlink_to(knowledge, target_is_directory=True)

    measurements = await FilesystemCapacityProbe(
        workspace_path=workspace,
        runtime_home_path=runtime_home,
        timeout_seconds=1,
    ).measure()

    by_kind = {item.storage_kind: item for item in measurements}
    assert set(by_kind) == {"workspace_data", "runtime_home"}
    assert by_kind["workspace_data"].used_bytes == len(b"workspace")
    assert by_kind["runtime_home"].used_bytes == len(b"home")
    assert all(item.capacity_bytes > 0 for item in measurements)
    assert all(item.available_bytes >= 0 for item in measurements)


@pytest.mark.asyncio
async def test_probe_times_out_as_one_bounded_operation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    runtime_home = tmp_path / "runtime-home"
    workspace.mkdir()
    runtime_home.mkdir()

    def blocked_reader(path: Path) -> tuple[int, int, int]:
        del path
        import time

        time.sleep(0.1)
        return (0, 1, 1)

    probe = FilesystemCapacityProbe(
        workspace_path=workspace,
        runtime_home_path=runtime_home,
        timeout_seconds=0.01,
        root_reader=blocked_reader,
    )

    with pytest.raises(TimeoutError):
        await probe.measure()

    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_probe_excludes_nested_mount_points(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    runtime_home = tmp_path / "runtime-home"
    mounted = workspace / "mounted"
    workspace.mkdir()
    runtime_home.mkdir()
    mounted.mkdir()
    (workspace / "project.bin").write_bytes(b"project")
    (mounted / "external.bin").write_bytes(b"external")
    original_is_mount = __import__("os").path.ismount
    monkeypatch.setattr(
        "app.modules.resource_telemetry.capacity.os.path.ismount",
        lambda path: Path(path) == mounted or original_is_mount(path),
    )

    measurements = await FilesystemCapacityProbe(
        workspace_path=workspace,
        runtime_home_path=runtime_home,
        timeout_seconds=1,
    ).measure()

    assert measurements[0].used_bytes == len(b"project")


@pytest.mark.asyncio
async def test_timed_out_scan_cannot_overlap_its_still_running_worker(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    runtime_home = tmp_path / "runtime-home"
    workspace.mkdir()
    runtime_home.mkdir()
    release = __import__("threading").Event()

    def blocked_reader(path: Path) -> tuple[int, int, int]:
        del path
        release.wait(timeout=1)
        return (0, 1, 1)

    probe = FilesystemCapacityProbe(
        workspace_path=workspace,
        runtime_home_path=runtime_home,
        timeout_seconds=0.01,
        root_reader=blocked_reader,
    )

    with pytest.raises(TimeoutError):
        await probe.measure()
    with pytest.raises(CapacityProbeInProgress):
        await probe.measure()
    release.set()
    await asyncio.sleep(0.02)
