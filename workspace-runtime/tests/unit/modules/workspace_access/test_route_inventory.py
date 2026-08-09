from __future__ import annotations

import json

import pytest

from app.modules.workspace_access.route_inventory import (
    DEFAULT_INVENTORY_PATH,
    RuntimeRouteClassificationError,
    RuntimeRouteInventory,
)
from scripts.generate_runtime_route_inventory import build_inventory


@pytest.fixture
def inventory() -> RuntimeRouteInventory:
    return RuntimeRouteInventory.load(DEFAULT_INVENTORY_PATH)


def test_committed_inventory_matches_every_registered_http_route() -> None:
    committed = json.loads(DEFAULT_INVENTORY_PATH.read_text(encoding="utf-8"))

    assert committed == build_inventory()


@pytest.mark.parametrize(
    ("path", "method"),
    [
        (
            "/api/v1/workspaces/workspace-a/claude-code/settings/raw",
            "GET",
        ),
        (
            "/api/v1/workspaces/workspace-a/claude-code/mcp-servers/project/"
            "server-a/export",
            "GET",
        ),
        (
            "/api/v1/workspaces/workspace-a/codex/config/model-providers",
            "PUT",
        ),
        (
            "/api/v1/workspaces/workspace-a/opencode/mcp-servers/project/server-a",
            "DELETE",
        ),
    ],
)
def test_sensitive_agent_settings_map_to_workspace_settings(
    inventory: RuntimeRouteInventory,
    path: str,
    method: str,
) -> None:
    assert inventory.classify(path=path, method=method) == "workspace_settings"


def test_sensitive_exact_route_wins_over_generic_path_wildcard(
    inventory: RuntimeRouteInventory,
) -> None:
    assert (
        inventory.classify(
            path=(
                "/api/v1/workspaces/workspace-a/codex/plugins/provider/plugin-a/"
                "mcp-servers/server-a/policy"
            ),
            method="PATCH",
        )
        == "workspace_settings"
    )


@pytest.mark.parametrize(
    ("path", "method", "raw_path"),
    [
        ("/api/v1/files/not-registered", "GET", None),
        ("/api/v1/files/tree/", "GET", None),
        ("/api/v1/files/tree", "PATCH", None),
        (
            "/api/v1/workspaces/workspace-a/claude-code/settings/raw",
            "GET",
            (b"/api/v1/workspaces/workspace-a/claude-code/settings%2Fraw"),
        ),
    ],
)
def test_unknown_method_path_trailing_slash_and_encoding_fail_closed(
    inventory: RuntimeRouteInventory,
    path: str,
    method: str,
    raw_path: bytes | None,
) -> None:
    with pytest.raises(RuntimeRouteClassificationError):
        inventory.classify(path=path, method=method, raw_path=raw_path)


def test_same_priority_overlap_fails_closed(tmp_path) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "routes": [
                    {
                        "routeTemplate": "/api/{tail:path}",
                        "methods": ["GET"],
                        "action": "runtime_read",
                        "matchPriority": 10,
                        "sensitive": False,
                    },
                    {
                        "routeTemplate": "/api/{name}",
                        "methods": ["GET"],
                        "action": "runtime_read",
                        "matchPriority": 10,
                        "sensitive": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    inventory = RuntimeRouteInventory.load(inventory_path)

    with pytest.raises(RuntimeRouteClassificationError):
        inventory.classify(path="/api/value", method="GET")
