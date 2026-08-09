#!/usr/bin/env python3
"""Adopt a generated image into the ppt-design-flow workspace tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))

from canvas_protocol import _atomic_write_json, skill_session_dir, validate_asset_name  # noqa: E402


SLOT_DIRS = {
    "style-preview": Path("style") / "candidates",
    "final-page": Path("generation") / "final-pages",
    "final-candidate": Path("generation") / "candidates",
    "review-export": Path("review") / "exports",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MANIFEST_NAME = "imagegen-assets.json"
FINAL_PAGES_MANIFEST = Path("generation") / "final-pages.json"
SLIDE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class AdoptionError(Exception):
    """Raised when an image cannot be adopted."""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move or copy a file-backed imagegen output into a ppt-design-flow session directory.",
    )
    parser.add_argument("--source", required=True, help="Generated image path to adopt.")
    parser.add_argument("--workspace", required=True, help="Workspace root, normally /workspace.")
    parser.add_argument("--session-id", required=True, help="ppt-design-flow session id.")
    parser.add_argument("--slot", required=True, choices=sorted(SLOT_DIRS), help="Destination slot.")
    parser.add_argument("--name", help="Workspace-relative filename inside the slot. Defaults to source name.")
    parser.add_argument("--slide-id", help="Stable slide id to update in generation/final-pages.json for final-page assets.")
    parser.add_argument("--copy", action="store_true", help="Copy instead of moving the source file.")
    args = parser.parse_args()

    try:
        target = adopt_image(
            source=Path(args.source),
            workspace=Path(args.workspace),
            session_id=args.session_id,
            slot=args.slot,
            name=args.name,
            slide_id=args.slide_id,
            move=not args.copy,
        )
    except (AdoptionError, OSError, ValueError) as exc:
        print(f"[adopt-imagegen] {exc}", file=sys.stderr)
        return 2

    print(target)
    return 0


def adopt_image(
    *,
    source: Path,
    workspace: Path,
    session_id: str,
    slot: str,
    name: str | None = None,
    slide_id: str | None = None,
    move: bool = True,
) -> Path:
    source = source.expanduser().resolve()
    workspace = workspace.expanduser().resolve()
    if slot not in SLOT_DIRS:
        raise AdoptionError(f"unsupported slot: {slot}")
    if not source.exists() or not source.is_file():
        raise AdoptionError(f"source image not found: {source}")
    if source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise AdoptionError(f"unsupported image extension: {source.suffix}")
    if not _looks_like_image(source):
        raise AdoptionError(f"source does not look like a supported image: {source}")

    asset_name = validate_asset_name(name or source.name)
    target_dir = skill_session_dir(workspace, session_id) / SLOT_DIRS[slot]
    target = (target_dir / asset_name).resolve()
    if target_dir not in target.parents and target != target_dir:
        raise AdoptionError(f"target escapes slot directory: {target}")
    if target.exists():
        raise AdoptionError(f"target already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    operation = "move" if move else "copy"
    if move:
        shutil.move(str(source), target)
    else:
        shutil.copy2(source, target)

    _record_manifest(
        workspace=workspace,
        session_id=session_id,
        entry={
            "created_at": _now(),
            "slot": slot,
            "operation": operation,
            "source": str(source),
            "target": str(target),
            "relative_target": str(target.relative_to(workspace)),
        },
    )
    if slot == "final-page":
        _record_current_final_page(
            workspace=workspace,
            session_id=session_id,
            slide_id=slide_id or _derive_slide_id(asset_name),
            target=target,
        )
    return target


def _looks_like_image(path: Path) -> bool:
    header = path.read_bytes()[:16]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    return False


def _record_manifest(*, workspace: Path, session_id: str, entry: dict[str, Any]) -> None:
    manifest_path = skill_session_dir(workspace, session_id) / MANIFEST_NAME
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            entries = []
    else:
        data = {
            "version": 1,
            "skill": "ppt-design-flow",
            "session_id": session_id,
            "entries": [],
        }
        entries = data["entries"]
    entries.append(entry)
    data["entries"] = entries
    data["updated_at"] = _now()
    _atomic_write_json(manifest_path, data)


def _record_current_final_page(*, workspace: Path, session_id: str, slide_id: str, target: Path) -> None:
    if not SLIDE_ID_RE.fullmatch(slide_id):
        raise AdoptionError("slide id must match ^[A-Za-z0-9_-]{1,64}$")
    session_dir = skill_session_dir(workspace, session_id)
    manifest_path = session_dir / FINAL_PAGES_MANIFEST
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = data.get("pages", [])
        if not isinstance(pages, list):
            pages = []
    else:
        data = {
            "version": 1,
            "skill": "ppt-design-flow",
            "session_id": session_id,
            "pages": [],
        }
        pages = data["pages"]

    relative_target = str(target.resolve().relative_to(session_dir.resolve()))
    updated = False
    next_pages: list[dict[str, str]] = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("slide_id"), str):
            continue
        page_slide_id = page["slide_id"]
        if page_slide_id == slide_id:
            next_pages.append({"slide_id": slide_id, "path": relative_target})
            updated = True
        elif isinstance(page.get("path"), str):
            next_pages.append({"slide_id": page_slide_id, "path": page["path"]})
    if not updated:
        next_pages.append({"slide_id": slide_id, "path": relative_target})

    data["pages"] = sorted(next_pages, key=lambda item: _natural_slide_key(item["slide_id"]))
    data["updated_at"] = _now()
    _atomic_write_json(manifest_path, data)


def _derive_slide_id(asset_name: str) -> str:
    stem = Path(asset_name).stem
    match = re.match(r"^(S\d+)", stem, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return re.split(r"[-_]", stem, maxsplit=1)[0] or stem


def _natural_slide_key(value: str) -> list[int | str]:
    parts = re.split(r"(\d+)", value.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
