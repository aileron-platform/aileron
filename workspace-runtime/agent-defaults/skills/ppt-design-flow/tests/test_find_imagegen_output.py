from __future__ import annotations

import json
import os
from pathlib import Path

from deck_test_helpers import PNG_BYTES, run_cli


def _write_png(path: Path, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_BYTES)
    os.utime(path, (mtime, mtime))


def test_find_imagegen_output_returns_single_new_file(workspace: Path, find_imagegen_cli: Path) -> None:
    root = workspace / "generated_images"
    _write_png(root / "old.png", 100)
    _write_png(root / "new.png", 200)

    result = run_cli(find_imagegen_cli, ["--root", str(root), "--after", "150"], workspace)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(root / "new.png")


def test_find_imagegen_output_excludes_manifest_sources(workspace: Path, find_imagegen_cli: Path) -> None:
    root = workspace / "generated_images"
    adopted = root / "adopted.png"
    fresh = root / "fresh.png"
    _write_png(adopted, 200)
    _write_png(fresh, 210)
    manifest = (
        workspace
        / ".aileron"
        / "canvases"
        / "ppt-design-flow"
        / "2026-05-19-test-session"
        / "imagegen-assets.json"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"entries": [{"source": str(adopted)}]}), encoding="utf-8")

    result = run_cli(find_imagegen_cli, ["--root", str(root), "--exclude-manifest", str(manifest)], workspace)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(fresh)


def test_find_imagegen_output_fails_on_ambiguous_outputs(workspace: Path, find_imagegen_cli: Path) -> None:
    root = workspace / "generated_images"
    _write_png(root / "one.png", 200)
    _write_png(root / "two.png", 210)

    result = run_cli(find_imagegen_cli, ["--root", str(root), "--after", "150"], workspace)

    assert result.returncode == 2
    assert "ambiguous" in result.stderr
