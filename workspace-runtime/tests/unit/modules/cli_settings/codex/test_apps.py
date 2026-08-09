from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.modules.cli_settings.codex.settings as codex_service_module
from app.modules.cli_settings.router import router
from app.modules.cli_settings.codex.settings import (
    CodexAgentSettings,
    get_codex_agent_settings,
)


def _service(tmp_path: Path, monkeypatch) -> tuple[CodexAgentSettings, Path]:
    package_root = (
        tmp_path / "home" / ".codex" / "plugins" / "cache" / "local" / "demo" / "1.2.3"
    )
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "name": "demo",
                "version": "1.2.3",
                "apps": "./apps/github.json",
            }
        ),
        encoding="utf-8",
    )
    app_definition = package_root / "apps" / "github.json"
    app_definition.parent.mkdir()
    app_definition.write_text(
        json.dumps(
            {
                "command": str(package_root / "bin" / "connector"),
                "env": {
                    "ACCESS_TOKEN": "secret-token",
                    "MODE": "safe",
                },
            }
        ),
        encoding="utf-8",
    )
    service = CodexAgentSettings(
        user_home=tmp_path / "home",
        workspace_root=tmp_path / "workspace",
        plugin_inventory=lambda: [
            {
                "pluginId": "demo@local",
                "name": "demo",
                "marketplaceName": "local",
                "version": "1.2.3",
                "installed": True,
                "enabled": True,
                "source": {"source": "local", "path": str(package_root)},
            }
        ],
    )
    gate = MagicMock()
    gate.generation.return_value = 17
    monkeypatch.setattr(
        codex_service_module,
        "get_marketplace_provider_gate",
        MagicMock(return_value=gate),
    )
    return service, package_root


def test_codex_apps_api_reads_installed_root_and_sanitizes_definition(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, package_root = _service(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_codex_agent_settings] = lambda: service
    client = TestClient(app)

    listed = client.get(
        "/api/v1/workspaces/workspace-1/codex/apps",
        params={"pluginId": "demo@local"},
    )
    detail = client.get(
        "/api/v1/workspaces/workspace-1/codex/apps/github",
        params={"pluginId": "demo@local"},
    )

    assert listed.status_code == 200
    assert detail.status_code == 200
    assert listed.json()["providerResourceGeneration"] == 17
    resource = listed.json()["apps"][0]
    assert resource["scope"] == "plugin"
    assert resource["readOnly"] is True
    assert resource["editable"] is False
    assert resource["generation"] == 17
    assert resource["relativeSourcePath"] == "apps/github.json"
    assert resource["definition"] == {
        "command": "${PLUGIN_ROOT}/bin/connector",
        "env": {
            "ACCESS_TOKEN": "[REDACTED]",
            "MODE": "[REDACTED]",
        },
    }
    assert resource["provenance"] == {
        "origin": "marketplace-plugin",
        "provider": "codex",
        "pluginId": "demo@local",
        "marketplaceId": "local",
    }
    serialized = json.dumps(detail.json(), sort_keys=True)
    assert str(package_root) not in serialized
    assert "secret-token" not in serialized


def test_codex_apps_detail_uses_canonical_not_found_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, _package_root = _service(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_codex_agent_settings] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/api/v1/workspaces/workspace-1/codex/apps/missing",
        params={"pluginId": "demo@local"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["errorCode"] == (
        "marketplace.settings.plugin_resource_not_found"
    )
