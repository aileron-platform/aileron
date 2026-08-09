"""Shared helpers for final deck exporters."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))

import stage_state  # noqa: E402
from stage_state import FlagContains  # noqa: E402


REQUIRED_GATES = (
    "needs_confirmed",
    "style_locked",
    "style_breakdown_confirmed",
    "pre_generation_confirmed",
    "review_approved",
)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
OUTPUT_RUN_FILENAME = "output-run.json"
FINAL_PAGES_MANIFEST = Path("generation") / "final-pages.json"


def require_deck_ready(workspace: Path, session_id: str, output_format: str) -> stage_state.State:
    return stage_state.require(
        workspace,
        session_id,
        phase_label=f"{output_format} deck",
        gates=REQUIRED_GATES,
        flags={"pages_ready": True},
        flag_contains=(FlagContains("output_formats", output_format),),
        next_action=(
            "python3 scripts/stage.py pass review_approved --session-id <YYYY-MM-DD-title-slug> --workspace /workspace\n"
            f"                    python3 scripts/stage.py set-flag output_formats '[\"{output_format}\"]' --session-id <YYYY-MM-DD-title-slug> --workspace /workspace"
        ),
    )


def final_page_images(workspace: Path, session_id: str) -> list[Path]:
    session_dir = stage_state.state_path(workspace, session_id).parent
    manifest_images = _final_page_images_from_manifest(session_dir)
    if manifest_images is not None:
        return manifest_images
    generation_dir = session_dir / "generation" / "final-pages"
    if not generation_dir.exists():
        return []
    candidates = [
        path
        for path in generation_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and "_marked" not in path.stem
    ]
    return sorted(candidates, key=_natural_sort_key)


def _final_page_images_from_manifest(session_dir: Path) -> list[Path] | None:
    manifest_path = session_dir / FINAL_PAGES_MANIFEST
    if not manifest_path.exists():
        return None
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        raise stage_state.InvalidTransitionError(
            "final page manifest must contain a pages array",
            {"path": str(manifest_path)},
        )
    images: list[Path] = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("path"), str):
            raise stage_state.InvalidTransitionError(
                "final page manifest entries must contain path",
                {"path": str(manifest_path)},
            )
        image_path = Path(page["path"]).expanduser()
        if not image_path.is_absolute():
            image_path = session_dir / image_path
        image_path = image_path.resolve()
        if not image_path.exists() or not image_path.is_file():
            raise stage_state.InvalidTransitionError(
                "final page image from manifest not found",
                {"image": str(image_path), "manifest": str(manifest_path)},
            )
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS or "_marked" in image_path.stem:
            raise stage_state.InvalidTransitionError(
                "final page manifest points to an unsupported image",
                {"image": str(image_path), "manifest": str(manifest_path)},
            )
        images.append(image_path)
    return images


def resolve_output_path(
    workspace: Path,
    requested_output: Path | None,
    *,
    extension: str,
    state: stage_state.State,
) -> Path:
    workspace = workspace.expanduser().resolve()
    output_dir = resolve_run_output_dir(workspace, state, requested_output=requested_output)
    if requested_output is None:
        output = output_dir / f"{default_deck_name(workspace, state)}.{extension}"
    else:
        output = requested_output.expanduser()
        if not output.is_absolute():
            output = output_dir / output
    output = output.resolve()
    if output.parent != output_dir:
        raise stage_state.InvalidTransitionError(
            "deck output must be written directly under the run output folder",
            {"output": str(output), "run_output": str(output_dir)},
        )
    if workspace.joinpath(".aileron") in output.parents:
        raise stage_state.InvalidTransitionError(
            "deck output must not be written under .aileron",
            {"output": str(output)},
        )
    if output.suffix.lower() != f".{extension}":
        raise stage_state.InvalidTransitionError(
            f"deck output must use .{extension}",
            {"output": str(output)},
        )
    return output


def resolve_run_output_dir(
    workspace: Path,
    state: stage_state.State,
    *,
    requested_output: Path | None = None,
) -> Path:
    workspace = workspace.expanduser().resolve()
    root = workspace
    session_dir = stage_state.state_path(workspace, state.session_id).parent
    run_state_path = session_dir / OUTPUT_RUN_FILENAME

    if run_state_path.exists():
        data = json.loads(run_state_path.read_text(encoding="utf-8"))
        run_slug = str(data.get("run_slug", "")).strip()
        if run_slug:
            return (root / run_slug).resolve()

    requested_run_dir = _requested_run_dir(workspace, requested_output)
    if requested_run_dir is not None:
        run_dir = requested_run_dir
        run_slug = run_dir.name
    else:
        run_slug = _allocate_run_slug(root, _base_run_slug(workspace, state))
        run_dir = root / run_slug

    run_dir.mkdir(parents=True, exist_ok=True)
    run_state_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_state_path,
        {
            "version": 1,
            "run_slug": run_slug,
            "run_dir": str(run_dir),
            "relative_run_dir": str(run_dir.relative_to(workspace)),
        },
    )
    return run_dir.resolve()


def default_deck_name(workspace: Path, state: stage_state.State) -> str:
    topic = _extract_topic(workspace, state) or "deck"
    slug = _slugify(topic)
    if state.flags.get("fast_mode"):
        slug = f"{slug}-ai-generated"
    return slug


def _extract_topic(workspace: Path, state: stage_state.State) -> str | None:
    for path in _topic_sources(workspace, state):
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:80]
    return None


def _topic_sources(workspace: Path, state: stage_state.State) -> Iterable[Path]:
    session_dir = stage_state.state_path(workspace, state.session_id).parent
    yield session_dir / "intake.md"
    yield session_dir / "content_report.md"
    yield workspace / "content_report.md"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.strip().lower(), flags=re.UNICODE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "deck"


def _natural_sort_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def _requested_run_dir(workspace: Path, requested_output: Path | None) -> Path | None:
    if requested_output is None:
        return None
    output = requested_output.expanduser()
    if not output.is_absolute():
        return None
    resolved = output.resolve()
    root = workspace
    if root not in resolved.parents:
        raise stage_state.InvalidTransitionError(
            "deck output must live under /workspace/<run-slug>",
            {"output": str(resolved), "root": str(root)},
        )
    if resolved.parent == root or resolved.parent.parent != root:
        raise stage_state.InvalidTransitionError(
            "deck output must be written directly under one run folder",
            {"output": str(resolved), "root": str(root)},
        )
    return resolved.parent


def _base_run_slug(workspace: Path, state: stage_state.State) -> str:
    run_date = os.environ.get("PPT_DESIGN_FLOW_RUN_DATE") or date.today().isoformat()
    topic_slug = _slugify(_extract_topic(workspace, state) or "deck")
    return f"{run_date}-{topic_slug}"


def _allocate_run_slug(root: Path, base_slug: str) -> str:
    if not (root / base_slug).exists():
        return base_slug
    index = 2
    while (root / f"{base_slug}-{index}").exists():
        index += 1
    return f"{base_slug}-{index}"


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)
