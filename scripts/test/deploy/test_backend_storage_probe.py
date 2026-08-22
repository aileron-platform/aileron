from __future__ import annotations

import importlib.util
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = ROOT.parent / "workspace-manager/scripts/backend_storage_probe.py"
SPEC = importlib.util.spec_from_file_location("backend_storage_probe", PROBE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DIGEST = "a" * 64
PROFILE_DIGEST = "b" * 64
PROFILE_CANONICAL_DIGEST = "c" * 64
RUN_ID = "run-20260808"
CLOCK = lambda: datetime(2026, 8, 9, 8, 0, tzinfo=UTC)


def _probe(action: str, root: Path, relative_path: str) -> dict:
    return MODULE.probe_backend(
        action=action,
        mount_root=root,
        relative_path=relative_path,
        locator_sha256=DIGEST,
        profile_raw_sha256=PROFILE_DIGEST,
        profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
        run_id=RUN_ID,
        clock=CLOCK,
    )


def test_cleanup_removes_only_the_exact_relative_backend(tmp_path: Path) -> None:
    target = tmp_path / "workspaces" / "target"
    sibling = tmp_path / "workspaces" / "sibling"
    target.mkdir(parents=True)
    sibling.mkdir()
    (target / "data.txt").write_text("delete")
    (sibling / "data.txt").write_text("preserve")

    result = _probe("cleanup", tmp_path, "workspaces/target")

    assert result == {
        "schemaVersion": "aileron-backend-storage-probe/v1",
        "action": "cleanup",
        "runId": RUN_ID,
        "locatorSha256": DIGEST,
        "profileRawSha256": PROFILE_DIGEST,
        "profileCanonicalSha256": PROFILE_CANONICAL_DIGEST,
        "state": "absent",
        "cleanupPerformed": True,
        "checkedAt": "2026-08-09T08:00:00Z",
    }
    assert not target.exists()
    assert (sibling / "data.txt").read_text() == "preserve"


def test_cleanup_is_idempotent_and_verify_reports_present_without_mutation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()

    present = _probe("verify", tmp_path, "target")
    assert present["state"] == "present"
    assert present["cleanupPerformed"] is False
    assert target.is_dir()

    _probe("cleanup", tmp_path, "target")
    absent = _probe("cleanup", tmp_path, "target")
    assert absent["state"] == "absent"
    assert absent["cleanupPerformed"] is False


def test_cleanup_unlinks_leaf_symlink_without_following_it(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "preserve.txt").write_text("preserve")
    root = tmp_path / "mount"
    root.mkdir()
    (root / "target").symlink_to(outside, target_is_directory=True)

    result = _probe("cleanup", root, "target")

    assert result["state"] == "absent"
    assert not (root / "target").exists()
    assert (outside / "preserve.txt").read_text() == "preserve"


def test_probe_rejects_symlink_parent_and_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "mount"
    root.mkdir()
    (root / "linked-parent").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        _probe("cleanup", root, "linked-parent/target")
    with pytest.raises(ValueError, match="relative path"):
        _probe("cleanup", root, "../outside")


def test_probe_rejects_symlink_in_mount_root_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    mount = outside / "mount"
    target = mount / "target"
    target.mkdir(parents=True)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        _probe("cleanup", linked_parent / "mount", "target")

    assert target.is_dir()


def test_probe_rejects_nested_mount_from_safely_decoded_mountinfo(
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "backend"
    target = mount_root / "workspace"
    nested = target / "nested mount"
    nested.mkdir(parents=True)
    sentinel = target / "keep"
    sentinel.write_text("preserve")
    mountinfo = tmp_path / "mountinfo"
    escaped_mount = str(nested).replace(" ", r"\040")
    mountinfo.write_text(
        f"42 31 0:99 / {escaped_mount} rw,relatime - tmpfs tmpfs rw\n"
    )

    with pytest.raises(ValueError, match="nested mount"):
        MODULE.probe_backend(
            action="cleanup",
            mount_root=mount_root,
            relative_path="workspace",
            locator_sha256=DIGEST,
            profile_raw_sha256=PROFILE_DIGEST,
            profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
            run_id=RUN_ID,
            clock=CLOCK,
            mountinfo_path=mountinfo,
        )

    assert sentinel.read_text() == "preserve"


def test_probe_rejects_ancestor_bind_mount_but_allows_root_and_sibling(
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "backend"
    target = mount_root / "tenant" / "workspace"
    target.mkdir(parents=True)
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        f"40 31 0:90 / {mount_root} rw - tmpfs tmpfs rw\n"
        f"41 40 0:91 / {mount_root / 'sibling'} rw - tmpfs tmpfs rw\n"
    )

    result = MODULE.probe_backend(
        action="verify",
        mount_root=mount_root,
        relative_path="tenant/workspace",
        locator_sha256=DIGEST,
        profile_raw_sha256=PROFILE_DIGEST,
        profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
        run_id=RUN_ID,
        clock=CLOCK,
        mountinfo_path=mountinfo,
    )
    assert result["state"] == "present"

    mountinfo.write_text(
        f"42 40 0:92 / {mount_root / 'tenant'} rw - tmpfs tmpfs rw\n"
    )
    with pytest.raises(ValueError, match="nested mount"):
        MODULE.probe_backend(
            action="verify",
            mount_root=mount_root,
            relative_path="tenant/workspace",
            locator_sha256=DIGEST,
            profile_raw_sha256=PROFILE_DIGEST,
            profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
            run_id=RUN_ID,
            clock=CLOCK,
            mountinfo_path=mountinfo,
        )


@pytest.mark.parametrize(
    "run_id",
    (
        "run-Uppercase01",
        "run-under_score01",
        "run-too",
        "run-" + "a" * 60,
    ),
)
def test_probe_rejects_noncanonical_or_64_character_run_id(
    tmp_path: Path, run_id: str
) -> None:
    (tmp_path / "target").mkdir()
    with pytest.raises(ValueError, match="identity"):
        MODULE.probe_backend(
            action="verify",
            mount_root=tmp_path,
            relative_path="target",
            locator_sha256=DIGEST,
            profile_raw_sha256=PROFILE_DIGEST,
            profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
            run_id=run_id,
            clock=CLOCK,
        )


def test_probe_accepts_63_character_run_id(tmp_path: Path) -> None:
    (tmp_path / "target").mkdir()
    result = MODULE.probe_backend(
        action="verify",
        mount_root=tmp_path,
        relative_path="target",
        locator_sha256=DIGEST,
        profile_raw_sha256=PROFILE_DIGEST,
        profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
        run_id="run-" + "a" * 59,
        clock=CLOCK,
    )
    assert result["state"] == "present"


@pytest.mark.parametrize(
    "mount_point",
    (
        r"/backend/workspace/bad\000escape",
        r"/backend/workspace/bad\777escape",
        r"relative/path",
    ),
)
def test_probe_rejects_malformed_mountinfo_fail_closed(
    tmp_path: Path, mount_point: str
) -> None:
    mount_root = tmp_path / "backend"
    (mount_root / "workspace").mkdir(parents=True)
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        f"42 31 0:99 / {mount_point} rw,relatime - tmpfs tmpfs rw\n"
    )

    with pytest.raises(ValueError, match="mountinfo"):
        MODULE.probe_backend(
            action="verify",
            mount_root=mount_root,
            relative_path="workspace",
            locator_sha256=DIGEST,
            profile_raw_sha256=PROFILE_DIGEST,
            profile_canonical_sha256=PROFILE_CANONICAL_DIGEST,
            run_id=RUN_ID,
            clock=CLOCK,
            mountinfo_path=mountinfo,
        )


@pytest.mark.skipif(
    os.environ.get("AILERON_RUN_PRIVILEGED_MOUNT_TEST") != "1",
    reason="requires an isolated privileged Linux container",
)
def test_probe_rejects_real_nested_bind_mount(tmp_path: Path) -> None:
    mount_root = tmp_path / "backend"
    target = mount_root / "workspace"
    nested = target / "nested"
    source = tmp_path / "source"
    nested.mkdir(parents=True)
    source.mkdir()
    (source / "must-survive").write_text("preserve")
    subprocess.run(["mount", "--bind", str(source), str(nested)], check=True)
    try:
        with pytest.raises(ValueError, match="nested mount"):
            _probe("cleanup", mount_root, "workspace")
        assert (source / "must-survive").read_text() == "preserve"
    finally:
        subprocess.run(["umount", str(nested)], check=True)


@pytest.mark.skipif(
    os.environ.get("AILERON_RUN_PRIVILEGED_MOUNT_TEST") != "1",
    reason="requires an isolated privileged Linux container",
)
def test_probe_rejects_real_ancestor_bind_mount(tmp_path: Path) -> None:
    mount_root = tmp_path / "backend"
    ancestor = mount_root / "tenant"
    source = tmp_path / "source"
    workspace = source / "workspace"
    ancestor.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (workspace / "must-survive").write_text("preserve")
    subprocess.run(["mount", "--bind", str(source), str(ancestor)], check=True)
    try:
        with pytest.raises(ValueError, match="nested mount"):
            _probe("cleanup", mount_root, "tenant/workspace")
        assert (workspace / "must-survive").read_text() == "preserve"
    finally:
        subprocess.run(["umount", str(ancestor)], check=True)


def test_workspace_manager_image_packages_probe_without_redundant_copy() -> None:
    dockerfile = (ROOT.parent / "workspace-manager/Dockerfile").read_text()

    assert "COPY workspace-manager/scripts/ ./scripts/" in dockerfile
    assert (
        "COPY workspace-manager/scripts/acceptance_oracle.py "
        "workspace-manager/scripts/acceptance_transport_probe.py "
        "workspace-manager/scripts/backend_storage_probe.py ./scripts/"
    ) not in dockerfile
