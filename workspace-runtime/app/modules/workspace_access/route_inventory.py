"""Closed HTTP route-to-action classification for Workspace Runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from re import Pattern
from typing import Literal, cast

from starlette.routing import compile_path

from app.config.settings import get_settings

RuntimeAccessAction = Literal[
    "runtime_read",
    "runtime_write",
    "workspace_settings",
    "agent",
    "automation",
    "browser_automation",
]

RUNTIME_ACCESS_ACTIONS = frozenset(
    {
        "runtime_read",
        "runtime_write",
        "workspace_settings",
        "agent",
        "automation",
        "browser_automation",
    }
)

DEFAULT_INVENTORY_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "authorization"
    / "runtime-route-inventory.json"
)


@dataclass(frozen=True)
class RuntimeRouteClassificationError(Exception):
    error_code: str = "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"


@dataclass(frozen=True)
class RuntimeRouteInventoryError(Exception):
    error_code: str = "WORKSPACE_RUNTIME_ACCESS_CONFIGURATION_INVALID"


@dataclass(frozen=True)
class RuntimeRouteRule:
    route_template: str
    methods: frozenset[str]
    action: RuntimeAccessAction
    match_priority: int
    sensitive: bool
    path_regex: Pattern[str]

    def matches(self, path: str, method: str) -> bool:
        return method in self.methods and bool(self.path_regex.fullmatch(path))


class RuntimeRouteInventory:
    """Classify protected HTTP requests from the committed route inventory."""

    def __init__(self, rules: tuple[RuntimeRouteRule, ...]) -> None:
        if not rules:
            raise RuntimeRouteInventoryError()
        self._rules = rules

    @classmethod
    def load(cls, path: Path) -> "RuntimeRouteInventory":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeRouteInventoryError() from exc
        if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
            raise RuntimeRouteInventoryError()
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list):
            raise RuntimeRouteInventoryError()

        rules: list[RuntimeRouteRule] = []
        seen_route_methods: set[tuple[str, str]] = set()
        for raw_route in raw_routes:
            if not isinstance(raw_route, dict):
                raise RuntimeRouteInventoryError()
            route_template = raw_route.get("routeTemplate")
            methods = raw_route.get("methods")
            action = raw_route.get("action")
            match_priority = raw_route.get("matchPriority")
            sensitive = raw_route.get("sensitive")
            if (
                not isinstance(route_template, str)
                or not route_template.startswith("/")
                or not isinstance(methods, list)
                or not methods
                or action not in RUNTIME_ACCESS_ACTIONS
                or not isinstance(match_priority, int)
                or match_priority < 0
                or not isinstance(sensitive, bool)
            ):
                raise RuntimeRouteInventoryError()
            normalized_methods = frozenset(
                method.upper() for method in methods if isinstance(method, str)
            )
            if len(normalized_methods) != len(methods):
                raise RuntimeRouteInventoryError()
            for method in normalized_methods:
                route_method = (route_template, method)
                if route_method in seen_route_methods:
                    raise RuntimeRouteInventoryError()
                seen_route_methods.add(route_method)
            try:
                path_regex, _, _ = compile_path(route_template)
            except (AssertionError, ValueError) as exc:
                raise RuntimeRouteInventoryError() from exc
            rules.append(
                RuntimeRouteRule(
                    route_template=route_template,
                    methods=normalized_methods,
                    action=cast(RuntimeAccessAction, action),
                    match_priority=match_priority,
                    sensitive=sensitive,
                    path_regex=path_regex,
                )
            )
        return cls(tuple(rules))

    def classify(
        self,
        *,
        path: str,
        method: str,
        raw_path: bytes | None = None,
    ) -> RuntimeAccessAction:
        if raw_path is not None and b"%" in raw_path:
            raise RuntimeRouteClassificationError()
        matches = [rule for rule in self._rules if rule.matches(path, method.upper())]
        if not matches:
            raise RuntimeRouteClassificationError()
        highest_priority = max(rule.match_priority for rule in matches)
        winners = [rule for rule in matches if rule.match_priority == highest_priority]
        if len(winners) != 1:
            raise RuntimeRouteClassificationError()
        return winners[0].action


@lru_cache(maxsize=1)
def get_runtime_route_inventory() -> RuntimeRouteInventory:
    configured_path = get_settings().RUNTIME_ROUTE_INVENTORY_PATH
    path = Path(configured_path) if configured_path else DEFAULT_INVENTORY_PATH
    return RuntimeRouteInventory.load(path)


__all__ = [
    "RuntimeRouteClassificationError",
    "RuntimeRouteInventory",
    "RuntimeRouteInventoryError",
    "RuntimeRouteRule",
    "get_runtime_route_inventory",
]
