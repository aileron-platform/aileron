#!/usr/bin/env python3
"""Find one newly generated file-backed imagegen output."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class FindImagegenError(Exception):
    """Raised when an imagegen output cannot be selected."""


def main() -> int:
    parser = argparse.ArgumentParser(description="Find one unadopted imagegen output without full-sort shell scans.")
    parser.add_argument("--root", required=True, type=Path, help="Generated images root or session directory.")
    parser.add_argument("--after", help="Only consider files newer than this epoch timestamp or ISO datetime.")
    parser.add_argument("--exclude-manifest", type=Path, help="imagegen-assets.json with adopted source paths to exclude.")
    parser.add_argument("--timeout", type=float, default=0.0, help="Seconds to wait for a matching output.")
    parser.add_argument("--poll-interval", type=float, default=0.5, help="Seconds between timeout polling attempts.")
    args = parser.parse_args()

    deadline = time.monotonic() + max(args.timeout, 0.0)
    last_error: FindImagegenError | None = None
    while True:
        try:
            selected = find_output(
                root=args.root,
                after=_parse_after(args.after),
                exclude_manifest=args.exclude_manifest,
            )
        except FindImagegenError as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                print(f"[find-imagegen] {exc}", file=sys.stderr)
                return 2
            time.sleep(max(args.poll_interval, 0.1))
            continue
        print(selected)
        return 0


def find_output(*, root: Path, after: float | None = None, exclude_manifest: Path | None = None) -> Path:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FindImagegenError(f"root directory not found: {root}")

    excluded = _excluded_sources(exclude_manifest)
    matches: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        resolved = path.resolve()
        if str(resolved) in excluded:
            continue
        if after is not None and resolved.stat().st_mtime <= after:
            continue
        if not _looks_like_image(resolved):
            continue
        matches.append(resolved)

    if not matches:
        raise FindImagegenError(f"no matching imagegen output found in {root}")
    if len(matches) > 1:
        names = ", ".join(str(path) for path in sorted(matches)[:5])
        raise FindImagegenError(f"ambiguous imagegen outputs: {names}")
    return matches[0]


def _excluded_sources(manifest_path: Path | None) -> set[str]:
    if manifest_path is None:
        return set()
    manifest_path = manifest_path.expanduser().resolve()
    if not manifest_path.exists():
        return set()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        return set()
    sources = set()
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("source"), str):
            sources.add(str(Path(entry["source"]).expanduser().resolve()))
    return sources


def _parse_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp()


def _looks_like_image(path: Path) -> bool:
    header = path.read_bytes()[:16]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
