"""Clean-cutover contract for Workspace execution-plane endpoints."""

from dataclasses import fields

from app.db.models import Workspace
from app.modules.workspace.orchestrator.models import RuntimeContext, RuntimeInfo
from app.modules.workspace.public_urls import WorkspacePublicUrls


REMOVED_WORKSPACE_COLUMNS = {
    "runtime_external_url",
    "runtime_external_port",
    "browser_webrtc_external_url",
    "browser_webrtc_external_port",
    "browser_cdp_external_port",
    "canvas_external_url",
    "canvas_external_port",
    "canvas_api_external_port",
    "terminal_external_url",
    "terminal_external_port",
}


def test_workspace_schema_has_no_external_endpoint_storage() -> None:
    assert REMOVED_WORKSPACE_COLUMNS.isdisjoint(Workspace.__table__.columns.keys())


def test_orchestrator_contract_has_no_host_port_or_external_url_projection() -> None:
    assert "ports" not in {field.name for field in fields(RuntimeContext)}
    assert "external_url" not in {field.name for field in fields(RuntimeInfo)}


def test_public_projection_uses_only_same_origin_workspace_paths() -> None:
    urls = WorkspacePublicUrls.for_workspace(
        "e0e4aba0-8442-4851-a9c4-5c45f9e74fb6"
    )

    assert urls.runtime == (
        "/workspaces/e0e4aba0-8442-4851-a9c4-5c45f9e74fb6/runtime"
    )
    assert urls.browser == (
        "/workspaces/e0e4aba0-8442-4851-a9c4-5c45f9e74fb6/browser"
    )
    assert urls.canvas == (
        "/workspaces/e0e4aba0-8442-4851-a9c4-5c45f9e74fb6/canvas"
    )
