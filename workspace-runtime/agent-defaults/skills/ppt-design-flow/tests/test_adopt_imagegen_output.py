"""Tests for imagegen output adoption."""

from __future__ import annotations

import json
from pathlib import Path

from deck_test_helpers import PNG_BYTES, run_cli


def test_adopt_imagegen_output_moves_final_page(
    adopt_imagegen_cli: Path,
    workspace: Path,
    session_id: str,
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated.png"
    source.write_bytes(PNG_BYTES)

    result = run_cli(
        adopt_imagegen_cli,
        [
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--session-id",
            session_id,
            "--slot",
            "final-page",
            "--name",
            "S01.png",
        ],
        workspace,
    )

    target = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "generation" / "final-pages" / "S01.png"
    manifest = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "imagegen-assets.json"
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(target)
    assert target.read_bytes() == PNG_BYTES
    assert not source.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["entries"][0]["slot"] == "final-page"
    assert data["entries"][0]["operation"] == "move"
    assert data["entries"][0]["relative_target"].endswith("generation/final-pages/S01.png")
    final_pages = json.loads(
        (
            workspace
            / ".aileron"
            / "canvases"
            / "ppt-design-flow"
            / session_id
            / "generation"
            / "final-pages.json"
        ).read_text(encoding="utf-8")
    )
    assert final_pages["pages"] == [
        {
            "slide_id": "S01",
            "path": "generation/final-pages/S01.png",
        }
    ]


def test_adopt_imagegen_output_updates_current_final_page_mapping(
    adopt_imagegen_cli: Path,
    workspace: Path,
    session_id: str,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(PNG_BYTES)
    second.write_bytes(PNG_BYTES)

    first_result = run_cli(
        adopt_imagegen_cli,
        [
            "--source",
            str(first),
            "--workspace",
            str(workspace),
            "--session-id",
            session_id,
            "--slot",
            "final-page",
            "--name",
            "S01.png",
        ],
        workspace,
    )
    second_result = run_cli(
        adopt_imagegen_cli,
        [
            "--source",
            str(second),
            "--workspace",
            str(workspace),
            "--session-id",
            session_id,
            "--slot",
            "final-page",
            "--name",
            "S01-v2.png",
            "--slide-id",
            "S01",
        ],
        workspace,
    )

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    manifest = json.loads(
        (
            workspace
            / ".aileron"
            / "canvases"
            / "ppt-design-flow"
            / session_id
            / "generation"
            / "final-pages.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["pages"] == [
        {
            "slide_id": "S01",
            "path": "generation/final-pages/S01-v2.png",
        }
    ]


def test_adopt_revision_pages_preserves_non_revised_mappings(
    adopt_imagegen_cli: Path,
    workspace: Path,
    session_id: str,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    third = tmp_path / "third.png"
    revised = tmp_path / "revised.png"
    for source in [first, second, third, revised]:
        source.write_bytes(PNG_BYTES)

    for source, slide_id in [(first, "S01"), (second, "S02"), (third, "S03")]:
        result = run_cli(
            adopt_imagegen_cli,
            [
                "--source",
                str(source),
                "--workspace",
                str(workspace),
                "--session-id",
                session_id,
                "--slot",
                "final-page",
                "--name",
                f"{slide_id}.png",
                "--slide-id",
                slide_id,
            ],
            workspace,
        )
        assert result.returncode == 0, result.stderr

    revision_result = run_cli(
        adopt_imagegen_cli,
        [
            "--source",
            str(revised),
            "--workspace",
            str(workspace),
            "--session-id",
            session_id,
            "--slot",
            "final-page",
            "--name",
            "S02-rev001.png",
            "--slide-id",
            "S02",
        ],
        workspace,
    )

    assert revision_result.returncode == 0, revision_result.stderr
    manifest = json.loads(
        (
            workspace
            / ".aileron"
            / "canvases"
            / "ppt-design-flow"
            / session_id
            / "generation"
            / "final-pages.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["pages"] == [
        {"slide_id": "S01", "path": "generation/final-pages/S01.png"},
        {"slide_id": "S02", "path": "generation/final-pages/S02-rev001.png"},
        {"slide_id": "S03", "path": "generation/final-pages/S03.png"},
    ]


def test_adopt_imagegen_output_refuses_existing_target(
    adopt_imagegen_cli: Path,
    workspace: Path,
    session_id: str,
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated.png"
    source.write_bytes(PNG_BYTES)
    target = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "style" / "candidates" / "preview.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(PNG_BYTES)

    result = run_cli(
        adopt_imagegen_cli,
        [
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--session-id",
            session_id,
            "--slot",
            "style-preview",
            "--name",
            "preview.png",
        ],
        workspace,
    )

    assert result.returncode == 2
    assert "target already exists" in result.stderr
    assert source.exists()


def test_adopt_imagegen_output_refuses_non_image(
    adopt_imagegen_cli: Path,
    workspace: Path,
    session_id: str,
    tmp_path: Path,
) -> None:
    source = tmp_path / "generated.png"
    source.write_text("not an image", encoding="utf-8")

    result = run_cli(
        adopt_imagegen_cli,
        [
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--session-id",
            session_id,
            "--slot",
            "final-page",
        ],
        workspace,
    )

    assert result.returncode == 2
    assert "does not look like a supported image" in result.stderr
