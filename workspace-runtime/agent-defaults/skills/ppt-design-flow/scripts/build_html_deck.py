#!/usr/bin/env python3
"""Build a single-file HTML deck from generated full-page images."""

from __future__ import annotations

import argparse
import base64
import html
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))

import stage_state  # noqa: E402
from canvas_protocol import write_canvas_bundle  # noqa: E402
from stage_state import StageError, resolve_workspace  # noqa: E402

from deck_builder_common import (  # noqa: E402
    final_page_images,
    require_deck_ready,
    resolve_output_path,
)


ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "html_export"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build final standalone HTML deck from generated page PNGs.")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--inline-assets",
        action="store_true",
        help="Embed slide images as base64 data URIs instead of writing a sibling asset folder.",
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    workspace = resolve_workspace(args.workspace)
    state = require_deck_ready(workspace, args.session_id, "html")
    output = resolve_output_path(workspace, args.output, extension="html", state=state)
    images = final_page_images(workspace, args.session_id)
    if not images:
        raise stage_state.InvalidTransitionError(
            "no final page images found",
            {"path": str(stage_state.state_path(workspace, args.session_id).parent / "generation")},
        )

    title = output.stem.replace("-", " ").strip() or "Deck"
    rendered = _render_html(title, images, output=output, inline_assets=args.inline_assets)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    write_canvas_bundle(
        workspace_dir=workspace,
        session_id=args.session_id,
        phase="html-export",
        title=title,
        html_source=output,
        image_paths=[],
    )
    if not args.inline_assets:
        _copy_external_assets_to_canvas_bundle(output, workspace=workspace, session_id=args.session_id)
    sys.stdout.write(f"Wrote {output} ({len(images)} slides)\n")
    return 0


def _render_html(deck_title: str, images: list[Path], *, output: Path, inline_assets: bool) -> str:
    template = (ASSET_DIR / "template.html").read_text(encoding="utf-8")
    styles = (ASSET_DIR / "styles.css").read_text(encoding="utf-8")
    script = (ASSET_DIR / "present.js").read_text(encoding="utf-8")
    image_sources = (
        [_image_data_uri(path) for path in images]
        if inline_assets
        else _write_external_assets(output, images)
    )
    slide_sections = []
    thumbnail_list = []
    for index, (path, image_src) in enumerate(zip(images, image_sources, strict=True), start=1):
        label = f"Slide {index}"
        escaped_label = html.escape(label)
        escaped_src = html.escape(image_src, quote=True)
        slide_sections.append(
            "\n".join(
                [
                    f'<section id="slide-{index}" class="slide-section" data-slide-index="{index - 1}">',
                    f'  <h2>{escaped_label}</h2>',
                    f'  <img src="{escaped_src}" alt="{escaped_label}" loading="lazy" />',
                    "</section>",
                ]
            )
        )
        thumbnail_list.append(
            "\n".join(
                [
                    f'<a class="thumbnail-link" href="#slide-{index}" data-slide-index="{index - 1}">',
                    f'  <img class="thumbnail-preview" src="{escaped_src}" alt="{escaped_label}" loading="lazy" />',
                    f'  <span><strong>{index:02d}</strong>{html.escape(path.stem)}</span>',
                    "</a>",
                ]
            )
        )
    replacements = {
        "{{deck_title}}": html.escape(deck_title),
        "{{slide_sections}}": "\n".join(slide_sections),
        "{{thumbnail_list}}": "\n".join(thumbnail_list),
        "{{inline_styles}}": styles,
        "{{inline_script}}": script,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template


def _write_external_assets(output: Path, images: list[Path]) -> list[str]:
    assets_root = output.parent / "assets"
    slides_dir = assets_root / "slides"
    if assets_root.exists():
        shutil.rmtree(assets_root)
    slides_dir.mkdir(parents=True, exist_ok=True)

    sources = []
    for path in images:
        target = slides_dir / path.name
        shutil.copy2(path, target)
        sources.append(f"assets/slides/{target.name}")
    return sources


def _copy_external_assets_to_canvas_bundle(output: Path, *, workspace: Path, session_id: str) -> None:
    assets_root = output.parent / "assets"
    if not assets_root.exists():
        return
    bundle_dir = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "html-export"
    target = bundle_dir / assets_root.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(assets_root, target)


def _image_data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except StageError as exc:
        sys.stderr.write(exc.render() + "\n")
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
