from __future__ import annotations

import json
from pathlib import Path

from deck_test_helpers import advance_to_review, approve_for_formats, run_cli, write_final_pages
from stage_state import pass_gate, set_flag


def test_html_refuses_without_review_approved(workspace: Path, session_id: str, build_html_cli: Path) -> None:
    advance_to_review(workspace, session_id)
    write_final_pages(workspace, session_id)
    output = workspace / "deck.html"
    result = run_cli(build_html_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 2
    assert not output.exists()
    assert "missing         : [review_approved" in result.stderr


def test_html_refuses_without_format_flag(workspace: Path, session_id: str, build_html_cli: Path) -> None:
    state = advance_to_review(workspace, session_id)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["pptx"]')
    write_final_pages(workspace, session_id)
    output = workspace / "deck.html"
    result = run_cli(build_html_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 2
    assert "missing         : [output_formats contains html]" in result.stderr


def test_html_success_builds_external_asset_deck_by_default(
    workspace: Path, session_id: str, build_html_cli: Path
) -> None:
    approve_for_formats(workspace, session_id, ["html"])
    output = workspace / "custom-run" / "deck.html"
    result = run_cli(build_html_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assets_dir = output.parent / "assets" / "slides"
    assert assets_dir.exists()
    slide_assets = sorted(assets_dir.glob("*.png"))
    assert len(slide_assets) == 2
    assert '<link rel="stylesheet"' not in text
    assert "<script src=" not in text
    assert "data:image/png;base64," not in text
    assert text.count("assets/slides/S01.png") == 2
    assert text.count("assets/slides/S02.png") == 2
    assert text.count('class="thumbnail-preview"') == 2
    assert text.count('class="slide-section"') == 2
    assert text.count("<nav") == 1
    assert text.count("<main") == 1
    assert text.count("<section") == 2
    assert 'id="mode-toggle"' in text
    assert "ArrowRight" in text
    assert "PageDown" in text
    assert "clientX < window.innerWidth / 2" in text
    assert "Math.abs(deltaX) < 40" in text


def test_html_inline_assets_keeps_single_file_output(
    workspace: Path, session_id: str, build_html_cli: Path
) -> None:
    approve_for_formats(workspace, session_id, ["html"])
    output = workspace / "custom-run" / "deck.html"
    result = run_cli(
        build_html_cli,
        ["--session-id", session_id, "--output", str(output), "--inline-assets"],
        workspace,
    )
    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert not (output.parent / "assets").exists()
    assert '<link rel="stylesheet"' not in text
    assert "<script src=" not in text
    assert text.count("data:image/png;base64,") == 4


def test_html_success_publishes_final_deck_to_web_canvas(
    workspace: Path, session_id: str, build_html_cli: Path
) -> None:
    approve_for_formats(workspace, session_id, ["html"])
    output = workspace / "custom-run" / "deck.html"
    result = run_cli(build_html_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 0, result.stderr

    bundle_index = (
        workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "html-export" / "index.html"
    )
    assert bundle_index.exists()
    assert bundle_index.read_text(encoding="utf-8") == output.read_text(encoding="utf-8")
    assert (output.parent / "assets" / "slides" / "S01.png").exists()
    assert (
        workspace
        / ".aileron"
        / "canvases"
        / "ppt-design-flow"
        / session_id
        / "html-export"
        / "assets"
        / "slides"
        / "S01.png"
    ).exists()

    manifest = json.loads((workspace / ".aileron" / "canvas.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "static"
    assert manifest["contentDir"].endswith("/html-export")
    assert manifest["contentDir"].startswith("./canvases/ppt-design-flow/")
    assert manifest["title"] == "deck"
    assert manifest["owner"] == {"skillName": "ppt-design-flow"}


def test_html_uses_current_final_page_mapping_instead_of_stale_files(
    workspace: Path, session_id: str, build_html_cli: Path
) -> None:
    approve_for_formats(workspace, session_id, ["html"])
    session_dir = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id
    final_dir = session_dir / "generation" / "final-pages"
    (final_dir / "S01-v2.png").write_bytes((final_dir / "S01.png").read_bytes())
    (session_dir / "generation" / "final-pages.json").write_text(
        json.dumps(
            {
                "version": 1,
                "pages": [
                    {"slide_id": "S01", "path": "generation/final-pages/S01-v2.png"},
                    {"slide_id": "S02", "path": "generation/final-pages/S02.png"},
                ],
            }
        ),
        encoding="utf-8",
    )

    output = workspace / "custom-run" / "deck.html"
    result = run_cli(build_html_cli, ["--session-id", session_id, "--output", str(output)], workspace)

    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    assert "assets/slides/S01-v2.png" in text
    assert "assets/slides/S01.png" not in text
    assert len(list((output.parent / "assets" / "slides").glob("*.png"))) == 2
