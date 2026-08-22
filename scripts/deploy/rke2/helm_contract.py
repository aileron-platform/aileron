#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

MINIMUM_HELM_VERSION = (3, 13, 0)
MAXIMUM_HELM_VERSION = (4, 0, 0)
HELM_VERSION_PATTERN = re.compile(
    r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def validate_version(value: str) -> tuple[int, int, int]:
    match = HELM_VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("Helm version must be a stable semantic version")
    version = tuple(int(part) for part in match.groups())
    if not MINIMUM_HELM_VERSION <= version < MAXIMUM_HELM_VERSION:
        raise ValueError("Helm version must be >=3.13.0 and <4.0.0")
    return version


def release_deployment_mode(
    inventory: Any,
    *,
    namespace: str,
    release: str,
) -> str:
    if not isinstance(inventory, list) or len(inventory) > 1:
        raise ValueError("Helm release inventory must contain at most one release")
    if not inventory:
        return "clean-install"
    entry = inventory[0]
    if (
        not isinstance(entry, dict)
        or entry.get("name") != release
        or entry.get("namespace") != namespace
    ):
        raise ValueError("Helm release inventory does not match the target release")
    return "upgrade"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    version_parser = subparsers.add_parser("validate-version")
    version_parser.add_argument("version")
    release_parser = subparsers.add_parser("release-mode")
    release_parser.add_argument("inventory", type=Path)
    release_parser.add_argument("--namespace", required=True)
    release_parser.add_argument("--release", required=True)
    args = parser.parse_args()

    try:
        if args.action == "validate-version":
            version = validate_version(args.version)
            print(".".join(str(part) for part in version))
        else:
            print(
                release_deployment_mode(
                    _load_json(args.inventory),
                    namespace=args.namespace,
                    release=args.release,
                )
            )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
