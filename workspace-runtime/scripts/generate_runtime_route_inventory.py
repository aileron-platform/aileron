"""Generate the closed Runtime HTTP route authorization inventory."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.main import app

READ_METHODS = frozenset({"GET", "HEAD"})
IGNORED_METHODS = frozenset({"OPTIONS"})
PUBLIC_ROUTES = frozenset(
    {
        "/health",
        "/api/v1/client-browser-relay/health",
    }
)
INTERNAL_PREFIXES = (
    "/internal/",
    "/api/v1/internal/",
)


def _is_sensitive_route(route_template: str) -> bool:
    return (
        "/mcp-servers" in route_template
        or route_template.endswith("/mcp-import")
        or "/claude-code/settings" in route_template
        or "/codex/config" in route_template
        or route_template.endswith("/agent-settings/cache/refresh")
    )


def _route_policy(route_template: str, method: str) -> tuple[str, int, bool]:
    specificity = len(
        "".join(
            segment
            for segment in route_template.split("/")
            if segment and not segment.startswith("{")
        )
    )
    if _is_sensitive_route(route_template):
        priority = (3500 if ":path}" in route_template else 4000) + specificity
        return "workspace_settings", priority, True
    if route_template.startswith("/api/v1/client-browser-relay"):
        return "browser_automation", 3000 + specificity, False
    if route_template.startswith("/api/v1/threads") or route_template == (
        "/api/v1/audio/transcriptions"
    ):
        return "agent", 3000 + specificity, False
    if route_template.startswith("/api/v1/automation"):
        return "automation", 3000 + specificity, False
    if method in READ_METHODS:
        return "runtime_read", 1000 + specificity, False
    return "runtime_write", 2000 + specificity, False


def build_inventory() -> dict[str, Any]:
    grouped_methods: dict[tuple[str, str, int, bool], set[str]] = defaultdict(set)
    seen_route_methods: set[tuple[str, str]] = set()

    for route in app.routes:
        route_template = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not isinstance(route_template, str) or not methods:
            continue
        if route_template in PUBLIC_ROUTES or route_template.startswith(
            INTERNAL_PREFIXES
        ):
            continue

        for method_value in methods:
            method = str(method_value).upper()
            if method in IGNORED_METHODS:
                continue
            route_method = (route_template, method)
            if route_method in seen_route_methods:
                raise ValueError(
                    f"Duplicate Runtime route and method: {method} {route_template}"
                )
            seen_route_methods.add(route_method)
            action, priority, sensitive = _route_policy(route_template, method)
            grouped_methods[(route_template, action, priority, sensitive)].add(method)

    routes = [
        {
            "routeTemplate": route_template,
            "methods": sorted(methods),
            "action": action,
            "matchPriority": priority,
            "sensitive": sensitive,
        }
        for (
            route_template,
            action,
            priority,
            sensitive,
        ), methods in grouped_methods.items()
    ]
    routes.sort(
        key=lambda route: (
            -route["matchPriority"],
            route["routeTemplate"],
            route["action"],
            route["methods"],
        )
    )
    return {"schemaVersion": 1, "routes": routes}


def _serialized_inventory() -> str:
    return json.dumps(build_inventory(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = _serialized_inventory()
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(f"{args.output.suffix}.tmp")
        temporary.write_text(expected, encoding="utf-8")
        temporary.replace(args.output)
        return 0

    try:
        current = args.output.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 1
    if current != expected:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
