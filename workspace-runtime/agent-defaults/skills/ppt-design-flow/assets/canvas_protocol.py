from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path


SKILL_NAME = "ppt-design-flow"
SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
ASSET_NAME_RE = re.compile(r"^[a-zA-Z0-9_./-]+$")


def canvas_artifact_arguments(title: str, route: str = "/") -> dict[str, str]:
    """Return recommended arguments for mcp__aileron__show_canvas_artifact."""
    return {"title": title, "route": route}


def validate_session_id(session_id: str) -> str:
    """Validate a session identifier before it is used as a path segment."""
    if not SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("session_id must match ^[a-zA-Z0-9_-]{1,64}$")
    return session_id


def validate_asset_name(asset_name: str) -> str:
    """Validate a bundle-relative asset name."""
    if not asset_name or not ASSET_NAME_RE.fullmatch(asset_name):
        raise ValueError("asset name must match ^[a-zA-Z0-9_./-]+$")
    if asset_name.startswith("/") or ".." in Path(asset_name).parts:
        raise ValueError("asset name must be relative and must not contain '..'")
    return asset_name


def skill_canvas_root(workspace_dir: Path) -> Path:
    """Return this skill's internal Aileron canvas namespace root."""
    return Path(workspace_dir).resolve() / ".aileron" / "canvases" / SKILL_NAME


def skill_session_dir(workspace_dir: Path, session_id: str) -> Path:
    """Return the internal session directory for this skill."""
    return skill_canvas_root(workspace_dir) / validate_session_id(session_id)


def _copy_asset(source_path: Path, bundle_dir: Path, asset_name: str) -> str:
    validate_asset_name(asset_name)
    target_path = bundle_dir / asset_name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)
    return asset_name


def _reference_asset(source_path: Path, workspace_dir: Path, session_dir: Path) -> str:
    resolved_source = source_path.resolve()
    resolved_workspace = workspace_dir.resolve()
    if resolved_source != resolved_workspace and resolved_workspace not in resolved_source.parents:
        raise ValueError("reference-mode images must live under the workspace root")
    return os.path.relpath(resolved_source, session_dir.resolve()).replace(os.sep, "/")


def _atomic_write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def _build_review_slides(copied_assets: list[str]) -> list[dict[str, str]]:
    slides = []
    for asset_name in copied_assets:
        page_id = Path(asset_name).stem
        slides.append(
            {
                "id": page_id,
                "code": page_id,
                "title": page_id,
                "role": "",
                "image": asset_name,
            }
        )
    return slides


def _inject_review_slides(html_text: str, copied_assets: list[str]) -> str:
    if not copied_assets:
        return html_text

    start_marker = "    const sampleSlides = "
    end_marker = "    const defaultState = "
    start_index = html_text.index(start_marker)
    end_index = html_text.index(end_marker, start_index)
    slides_json = json.dumps(
        _build_review_slides(copied_assets),
        ensure_ascii=False,
        indent=6,
    )
    return (
        html_text[:start_index]
        + start_marker
        + slides_json
        + ";\n\n"
        + html_text[end_index:]
    )


def _inject_preview_images(html_text: str, copied_assets: list[str]) -> str:
    if not copied_assets:
        return html_text

    asset_iter = iter(copied_assets)

    def replace_src(match: re.Match[str]) -> str:
        try:
            asset_name = next(asset_iter)
        except StopIteration:
            return match.group(0)
        return f'{match.group(1)}src="{asset_name}"'

    return re.sub(
        r'(<img\b(?=[^>]*\bclass="[^"]*\bpreview-image\b[^"]*")[^>]*?)src="[^"]*"',
        replace_src,
        html_text,
        count=len(copied_assets),
    )


def write_canvas_bundle(
    *,
    workspace_dir: Path,
    session_id: str,
    phase: str,
    title: str,
    html_source: Path,
    image_paths: list[Path],
    asset_mode: str = "copy",
) -> Path:
    """Write a static Aileron Canvas bundle and atomically activate it."""
    if asset_mode not in {"copy", "reference"}:
        raise ValueError("asset_mode must be copy or reference")
    session_id = validate_session_id(session_id)
    validate_asset_name(f"{session_id}/{phase}/index.html")

    workspace_dir = Path(workspace_dir).resolve()
    html_source = Path(html_source)
    if not html_source.exists():
        raise FileNotFoundError(f"HTML source not found: {html_source}")

    aileron_dir = workspace_dir / ".aileron"
    session_dir = skill_session_dir(workspace_dir, session_id)
    bundle_dir = session_dir / phase

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    bundle_assets = []
    for image_path in image_paths:
        source_image = Path(image_path)
        if not source_image.exists():
            raise FileNotFoundError(f"Image source not found: {source_image}")
        if asset_mode == "copy":
            bundle_assets.append(_copy_asset(source_image, bundle_dir, f"images/{source_image.name}"))
        else:
            bundle_assets.append(_reference_asset(source_image, workspace_dir, session_dir))

    html_text = html_source.read_text(encoding="utf-8")
    if phase == "style-preview":
        html_text = _inject_preview_images(html_text, bundle_assets)
    if phase in {"review", "revision"}:
        html_text = _inject_review_slides(html_text, bundle_assets)
    (bundle_dir / "index.html").write_text(html_text, encoding="utf-8")
    if asset_mode == "reference":
        (session_dir / "index.html").write_text(html_text, encoding="utf-8")


    if asset_mode == "reference":
        content_dir = f"./canvases/{SKILL_NAME}/{session_id}"
        routes = [{"path": "/", "label": title}]
    else:
        content_dir = f"./canvases/{SKILL_NAME}/{session_id}/{phase}"
        routes = [{"path": "/", "label": title}]
    manifest = {
        "version": 1,
        "kind": "static",
        "contentDir": content_dir,
        "title": title,
        "owner": {"skillName": SKILL_NAME},
        "routes": routes,
        "defaultPath": "/",
    }
    manifest_path = aileron_dir / "canvas.json"
    _atomic_write_json(manifest_path, manifest)
    return manifest_path
