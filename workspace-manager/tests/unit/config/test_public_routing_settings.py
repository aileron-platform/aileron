"""Public routing 設定測試"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


@pytest.mark.unit
def test_public_routing_defaults_are_valid() -> None:
    settings = Settings()

    assert settings.PUBLIC_SCHEME == "http"
    assert settings.resolve_public_host(settings.PUBLIC_FRONTEND_HOST) == "aileron.aileron.localhost"
    assert settings.resolve_public_host(
        settings.PUBLIC_RUNTIME_HOST_PATTERN,
        workspace_id="ws-123",
    ) == "workspace-runtime-ws-123.aileron.localhost"


@pytest.mark.unit
def test_public_routing_replaces_base_domain_placeholder() -> None:
    settings = Settings(
        PUBLIC_SCHEME="https",
        PUBLIC_BASE_DOMAIN="example.com",
        PUBLIC_FRONTEND_HOST="aileron.{baseDomain}",
        PUBLIC_WORKSPACE_MANAGER_HOST="workspace-manager.{baseDomain}",
        PUBLIC_KEYCLOAK_HOST="keycloak.{baseDomain}",
        PUBLIC_RUNTIME_HOST_PATTERN="workspace-runtime-{workspaceId}.{baseDomain}",
        PUBLIC_BROWSER_HOST_PATTERN="workspace-browser-{workspaceId}.{baseDomain}",
        PUBLIC_CANVAS_HOST_PATTERN="workspace-canvas-{workspaceId}.{baseDomain}",
    )

    assert settings.build_public_url(settings.PUBLIC_FRONTEND_HOST) == "https://aileron.example.com"
    assert (
        settings.build_public_url(settings.PUBLIC_WORKSPACE_MANAGER_HOST)
        == "https://workspace-manager.example.com"
    )
    assert (
        settings.build_public_url(settings.PUBLIC_RUNTIME_HOST_PATTERN, workspace_id="abc")
        == "https://workspace-runtime-abc.example.com"
    )


@pytest.mark.unit
def test_public_routing_rejects_pattern_without_workspace_id() -> None:
    with pytest.raises(ValidationError):
        Settings(PUBLIC_RUNTIME_HOST_PATTERN="workspace-runtime.example.com")


@pytest.mark.unit
def test_public_routing_rejects_invalid_scheme() -> None:
    with pytest.raises(ValidationError):
        Settings(PUBLIC_SCHEME="ftp")


@pytest.mark.unit
def test_resolve_public_host_requires_workspace_id_for_workspace_pattern() -> None:
    settings = Settings()

    with pytest.raises(ValueError, match="workspace_id is required"):
        settings.resolve_public_host(settings.PUBLIC_RUNTIME_HOST_PATTERN)


@pytest.mark.unit
def test_allowed_origins_list_includes_public_frontend_hosts() -> None:
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:3000",
        PUBLIC_SCHEME="http",
        PUBLIC_BASE_DOMAIN="example.com",
        PUBLIC_FRONTEND_HOST="aileron.{baseDomain}",
        PUBLIC_WORKSPACE_MANAGER_HOST="workspace-manager.{baseDomain}",
        PUBLIC_KEYCLOAK_HOST="keycloak.{baseDomain}",
        PUBLIC_RUNTIME_HOST_PATTERN="workspace-runtime-{workspaceId}.{baseDomain}",
        PUBLIC_BROWSER_HOST_PATTERN="workspace-browser-{workspaceId}.{baseDomain}",
        PUBLIC_CANVAS_HOST_PATTERN="workspace-canvas-{workspaceId}.{baseDomain}",
    )

    assert settings.allowed_origins_list == [
        "http://localhost:3000",
        "http://aileron.example.com",
    ]
