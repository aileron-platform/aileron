from __future__ import annotations

from fastapi.routing import APIRoute

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


def test_claude_code_skills_owned_by_claude_code_module() -> None:
    routes = [
        route
        for route in _routes()
        if route.path.startswith("/api/v1/workspaces/{workspace_id}/claude-code/skills")
    ]
    assert routes
    assert all(
        route.endpoint.__module__.startswith("app.modules.claude_code.file_collections")
        for route in routes
    )


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
        "/api/v1/workspaces/{workspace_id}/gemini",
        "/api/v1/workspaces/{workspace_id}/codex",
        "/api/v1/workspaces/{workspace_id}/opencode",
    )
    routes = [route for route in _routes() if route.path.startswith(prefixes)]
    assert routes
    assert all(
        route.endpoint.__module__.startswith("app.modules.cli_settings")
        for route in routes
    )
