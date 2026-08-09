from __future__ import annotations

from pathlib import Path

from deck_test_helpers import approve_for_formats, run_cli


def _write_topic(workspace: Path, session_id: str, title: str) -> None:
    session_dir = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "content_report.md").write_text(f"# {title}\n", encoding="utf-8")


def test_html_output_uses_dated_title_run_folder_and_session_id(
    workspace: Path,
    build_html_cli: Path,
    monkeypatch,
) -> None:
    session_id = "2026-05-19-superpowers-bridge-api-intro"
    _write_topic(workspace, session_id, "Superpowers Bridge API Intro")
    approve_for_formats(workspace, session_id, ["html"], fast_mode=True)
    monkeypatch.setenv("PPT_DESIGN_FLOW_RUN_DATE", "2026-05-19")

    result = run_cli(build_html_cli, ["--session-id", session_id], workspace)

    assert result.returncode == 0, result.stderr
    run_dir = workspace / "2026-05-19-superpowers-bridge-api-intro"
    html = run_dir / "superpowers-bridge-api-intro-ai-generated.html"
    assert html.exists()
    assert (
        workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "html-export" / "index.html"
    ).exists()
    assert (run_dir / "assets" / "slides" / "S01.png").exists()
    assert not (workspace / "superpowers-bridge-api-intro-ai-generated.html").exists()


def test_pptx_output_reuses_existing_session_run_folder(
    workspace: Path,
    session_id: str,
    build_html_cli: Path,
    build_pptx_cli: Path,
    monkeypatch,
) -> None:
    _write_topic(workspace, session_id, "Superpowers Bridge API Intro")
    approve_for_formats(workspace, session_id, ["html", "pptx"], fast_mode=True)
    monkeypatch.setenv("PPT_DESIGN_FLOW_RUN_DATE", "2026-05-19")

    html_result = run_cli(build_html_cli, ["--session-id", session_id], workspace)
    pptx_result = run_cli(build_pptx_cli, ["--session-id", session_id], workspace)

    assert html_result.returncode == 0, html_result.stderr
    assert pptx_result.returncode == 0, pptx_result.stderr
    run_dir = workspace / "2026-05-19-superpowers-bridge-api-intro"
    assert (run_dir / "superpowers-bridge-api-intro-ai-generated.html").exists()
    assert (run_dir / "superpowers-bridge-api-intro-ai-generated.pptx").exists()


def test_run_folder_uses_non_overwriting_suffix(
    workspace: Path,
    session_id: str,
    build_html_cli: Path,
    monkeypatch,
) -> None:
    _write_topic(workspace, session_id, "Superpowers Bridge API Intro")
    existing = workspace / "2026-05-19-superpowers-bridge-api-intro"
    existing.mkdir(parents=True)
    approve_for_formats(workspace, session_id, ["html"], fast_mode=True)
    monkeypatch.setenv("PPT_DESIGN_FLOW_RUN_DATE", "2026-05-19")

    result = run_cli(build_html_cli, ["--session-id", session_id], workspace)

    assert result.returncode == 0, result.stderr
    assert (
        workspace
        / "2026-05-19-superpowers-bridge-api-intro-2"
        / "superpowers-bridge-api-intro-ai-generated.html"
    ).exists()


def test_run_folder_does_not_create_user_facing_output_manifest(
    workspace: Path,
    session_id: str,
    build_html_cli: Path,
    monkeypatch,
) -> None:
    _write_topic(workspace, session_id, "Superpowers Bridge API Intro")
    approve_for_formats(workspace, session_id, ["html"], fast_mode=True)
    monkeypatch.setenv("PPT_DESIGN_FLOW_RUN_DATE", "2026-05-19")

    result = run_cli(build_html_cli, ["--session-id", session_id], workspace)

    assert result.returncode == 0, result.stderr
    run_dir = workspace / "2026-05-19-superpowers-bridge-api-intro"
    assert (run_dir / "superpowers-bridge-api-intro-ai-generated.html").exists()
    assert not (run_dir / "output_manifest.json").exists()
    assert not (run_dir / "imagegen-assets.json").exists()
