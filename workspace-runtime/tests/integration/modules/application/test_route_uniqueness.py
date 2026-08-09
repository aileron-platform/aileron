from __future__ import annotations

from fastapi.routing import APIRoute, APIWebSocketRoute

from app.main import app


def _routes() -> list[APIRoute]:
    return [route for route in app.routes if isinstance(route, APIRoute)]


def test_no_duplicate_routes() -> None:
    pairs = [
        (route.path, method)
        for route in _routes()
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    ]
    assert len(set(pairs)) == len(pairs)


def test_claude_code_skills_owned_by_cli_settings_module() -> None:
    routes = [
        route
        for route in _routes()
        if route.path.startswith("/api/v1/workspaces/{workspace_id}/claude-code/skills")
    ]
    assert routes
    assert all(
        route.endpoint.__module__.startswith("app.modules.cli_settings.skills")
        for route in routes
    )


def test_scripts_routes_are_removed_from_openapi() -> None:
    schema = app.openapi()

    assert not any("/claude-code/scripts" in path for path in schema["paths"])
    assert all(tag["name"] != "Claude Code - Scripts" for tag in schema["tags"])


def test_claude_md_owned_by_cli_settings_module() -> None:
    routes = [
        route
        for route in _routes()
        if route.path == "/api/v1/workspaces/{workspace_id}/claude-code/claude-md"
    ]
    assert routes
    assert all(
        route.endpoint.__module__.startswith("app.modules.cli_settings.agents_md")
        for route in routes
    )


def test_non_claude_cli_routes_owned_by_cli_settings_module() -> None:
    prefixes = (
        "/api/v1/workspaces/{workspace_id}/codex",
        "/api/v1/workspaces/{workspace_id}/opencode",
    )
    routes = [route for route in _routes() if route.path.startswith(prefixes)]
    assert routes
    assert all(
        route.endpoint.__module__.startswith("app.modules.cli_settings")
        for route in routes
    )


def test_removed_legacy_and_duplicate_routes_are_not_registered() -> None:
    registered = {
        (route.path, method) for route in _routes() for method in route.methods
    }

    assert ("/api/v1/canvases/{workspace_id}/manifest", "DELETE") not in registered
    assert (
        "/api/v1/workspaces/{workspace_id}/claude-code/memory/{_legacy_path:path}",
        "GET",
    ) not in registered
    assert (
        "/api/v1/workspaces/{workspace_id}/codex/agents-md/{scope}",
        "GET",
    ) not in registered
    assert (
        "/api/v1/workspaces/{workspace_id}/codex/agents-md",
        "GET",
    ) in registered


def test_legacy_agent_session_routes_are_not_registered() -> None:
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute))
    }

    assert not any("agent-sessions" in path for path in paths)
    assert not any("agent-tasks" in path for path in paths)
    assert not any("agent-messages" in path for path in paths)


def test_collection_routes_do_not_use_trailing_slash() -> None:
    registered = {
        (route.path, method) for route in _routes() for method in route.methods
    }

    assert ("/api/v1/client-browser-relay/", "GET") not in registered
    assert ("/api/v1/client-browser-relay", "GET") in registered
