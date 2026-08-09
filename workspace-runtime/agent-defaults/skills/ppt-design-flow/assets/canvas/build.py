#!/usr/bin/env python3
"""Unified canvas-bundle builder for the ppt-design-flow skill.

One CLI replaces the previous three near-identical builder scripts. The
``--phase`` flag dispatches to the correct shell HTML, runs the per-phase
pre-flight via ``stage_state.require(...)``, and on success delegates the
bundle write to ``canvas_protocol.write_canvas_bundle``.

Pre-flight failures exit with status 2 and emit an LLM-readable stderr block
(see ``canvas-bundles/spec.md``). All other state errors exit with status 3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow ``python3 assets/canvas/build.py`` to import sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stage_state  # noqa: E402
from canvas_protocol import canvas_artifact_arguments, write_canvas_bundle  # noqa: E402
from stage_state import StageError, resolve_workspace  # noqa: E402


SHELL_DIR = Path(__file__).resolve().parent


PHASE_SPECS: dict[str, dict[str, object]] = {
    "preview": {
        "shell": SHELL_DIR / "preview_shell" / "index.html",
        "title": "PPT style preview",
        "manifest_phase": "style-preview",
        "phases": ("style",),
        "gates": ("needs_confirmed",),
        "flags": {},
        "next_action": "python3 scripts/stage.py enter style --session-id <YYYY-MM-DD-title-slug>",
    },
    "candidate-picker": {
        "shell": SHELL_DIR / "candidate_picker_shell" / "index.html",
        "title": "PPT candidate picker",
        "manifest_phase": "candidate-picker",
        "phases": ("generation", "review"),
        "gates": (
            "needs_confirmed",
            "style_locked",
            "style_breakdown_confirmed",
            "pre_generation_confirmed",
        ),
        "flags": {"candidate_mode": "multi"},
        "next_action": "python3 scripts/stage.py set-flag candidate_mode multi --session-id <YYYY-MM-DD-title-slug>",
    },
    "review": {
        "shell": SHELL_DIR / "review_shell" / "index.html",
        "title": "PPT review",
        "manifest_phase": "review",
        "phases": ("review",),
        "gates": (
            "needs_confirmed",
            "style_locked",
            "style_breakdown_confirmed",
            "pre_generation_confirmed",
        ),
        "flags": {"pages_ready": True},
        "next_action": "python3 scripts/stage.py set-flag pages_ready true --session-id <YYYY-MM-DD-title-slug>",
    },
    "revision": {
        "shell": SHELL_DIR / "review_shell" / "index.html",
        "title": "PPT revision review",
        "manifest_phase": "revision",
        "phases": ("revision",),
        "gates": ("review_approved",),
        "flags": {"revision_active": True},
        "next_action": "python3 scripts/stage.py revise --session-id <YYYY-MM-DD-title-slug> --workspace /workspace",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Build a static Aileron Canvas bundle for the ppt-design-flow skill.",
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=sorted(PHASE_SPECS.keys()),
        help="Which canvas surface to build.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (falls back to WORKSPACE_DIR env var).",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Canvas session id; must match ^[a-zA-Z0-9_-]{1,64}$.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Override canvas title stored in canvas.json.",
    )
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        type=Path,
        help="Image file to copy into the canvas bundle. Repeat for multiple images.",
    )
    parser.add_argument(
        "--image-list",
        action="append",
        default=[],
        type=Path,
        help="JSON file listing image paths to include, preserving order.",
    )
    parser.add_argument(
        "--asset-mode",
        choices=("copy", "reference"),
        default="copy",
        help="How to attach image assets to the canvas bundle.",
    )
    parser.add_argument(
        "--print-artifact",
        action="store_true",
        help="Print the chat artifact tool arguments after writing the canvas bundle.",
    )
    parser.add_argument(
        "--revision-id",
        default=None,
        help="Revision id to build when --phase=revision.",
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    spec = PHASE_SPECS[args.phase]
    workspace = resolve_workspace(args.workspace)

    state = stage_state.require(
        workspace,
        args.session_id,
        phase_label=args.phase,
        phases=spec["phases"],  # type: ignore[arg-type]
        gates=spec["gates"],    # type: ignore[arg-type]
        flags=spec["flags"],    # type: ignore[arg-type]
        next_action=spec["next_action"],  # type: ignore[arg-type]
    )
    if args.phase == "revision":
        expected_revision_id = state.flags.get("revision_id")
        if args.revision_id and expected_revision_id and args.revision_id != expected_revision_id:
            raise ValueError(f"revision id mismatch: expected {expected_revision_id}, received {args.revision_id}")
        filter_pages = set(state.flags.get("revision_pages") or [])
    else:
        filter_pages = set()

    image_paths = _image_paths_from_lists(
        workspace=workspace,
        session_id=args.session_id,
        image_lists=list(args.image_list),
        filter_pages=filter_pages,
    )
    image_paths.extend(args.image)

    manifest_path = write_canvas_bundle(
        workspace_dir=workspace,
        session_id=args.session_id,
        phase=spec["manifest_phase"],  # type: ignore[arg-type]
        title=args.title or spec["title"],  # type: ignore[arg-type]
        html_source=spec["shell"],  # type: ignore[arg-type]
        image_paths=image_paths,
        asset_mode=args.asset_mode,
    )
    sys.stdout.write(f"Wrote {manifest_path}\n")
    if args.print_artifact:
        sys.stdout.write(json.dumps(canvas_artifact_arguments(args.title or str(spec["title"])), ensure_ascii=False) + "\n")
    return 0


def _image_paths_from_lists(
    *,
    workspace: Path,
    session_id: str,
    image_lists: list[Path],
    filter_pages: set[str] | None = None,
) -> list[Path]:
    session_dir = stage_state.state_path(workspace, session_id).parent
    images: list[Path] = []
    filter_pages = filter_pages or set()
    for image_list in image_lists:
        image_list = image_list.expanduser()
        if not image_list.is_absolute():
            image_list = session_dir / image_list
        image_list = image_list.resolve()
        if not image_list.exists():
            raise FileNotFoundError(f"Image list not found: {image_list}")
        data = json.loads(image_list.read_text(encoding="utf-8"))
        entries = data.get("pages", data) if isinstance(data, dict) else data
        if not isinstance(entries, list):
            raise ValueError("image list must be a JSON array or an object with a pages array")
        for entry in entries:
            if filter_pages:
                slide_id = _image_slide_id(entry)
                if slide_id not in filter_pages:
                    continue
            path_value = _image_path_value(entry)
            image_path = Path(path_value).expanduser()
            if not image_path.is_absolute():
                image_path = session_dir / image_path
            images.append(image_path.resolve())
    return images


def _image_slide_id(entry: object) -> str:
    if isinstance(entry, dict) and isinstance(entry.get("slide_id"), str):
        return entry["slide_id"]
    path_value = _image_path_value(entry)
    return Path(path_value).stem.split("-", maxsplit=1)[0]


def _image_path_value(entry: object) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("path", "relative_path", "target"):
            value = entry.get(key)
            if isinstance(value, str):
                return value
    raise ValueError("image list entries must be strings or objects with path, relative_path, or target")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except StageError as exc:
        sys.stderr.write(exc.render() + "\n")
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
