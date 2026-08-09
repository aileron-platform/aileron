from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.modules.workspace.browser_credential_models import BrowserIceServer
from app.modules.workspace.browser_turn_credentials import BrowserTurnCredentialIssuer


def test_turn_rest_issuer_returns_expiring_workspace_scoped_credentials() -> None:
    issuer = BrowserTurnCredentialIssuer(
        ice_servers=(
            BrowserIceServer(urls=["turns:turn.example.test:5349?transport=tcp"]),
        ),
        shared_secret="shared-secret",
        ttl_seconds=300,
    )

    result = issuer.issue(workspace_id="workspace-1", now=1_700_000_000)

    username = "1700000300:browser:workspace-1"
    expected_credential = base64.b64encode(
        hmac.new(b"shared-secret", username.encode(), hashlib.sha1).digest()
    ).decode()
    assert result == [
        BrowserIceServer(
            urls=["turns:turn.example.test:5349?transport=tcp"],
            username=username,
            credential=expected_credential,
        )
    ]


@pytest.mark.parametrize(
    "servers",
    [
        "[]",
        '[{"urls": []}]',
        '[{"urls": ["https://turn.example.test"]}]',
    ],
)
def test_turn_rest_issuer_rejects_invalid_ice_servers(
    tmp_path: Path,
    servers: str,
) -> None:
    secret_file = tmp_path / "turn-rest-shared-secret"
    secret_file.write_text("shared-secret\n", encoding="utf-8")
    servers_file = tmp_path / "turn-frontend-ice-servers.json"
    servers_file.write_text(servers, encoding="utf-8")
    settings = Settings(
        TURN_BROWSER_CREDENTIAL_ISSUER_KIND="turnRest",
        TURN_BROWSER_CREDENTIAL_TTL_SECONDS=300,
        TURN_FRONTEND_ICE_SERVERS_JSON_FILE=str(servers_file),
        TURN_REST_SHARED_SECRET_FILE=str(secret_file),
    )

    with pytest.raises(RuntimeError, match="settings are invalid"):
        BrowserTurnCredentialIssuer.from_settings(settings)


def test_turn_rest_issuer_requires_mounted_secret_file(tmp_path: Path) -> None:
    servers_file = tmp_path / "turn-frontend-ice-servers.json"
    servers_file.write_text(
        '[{"urls":["turns:turn.example.test:5349?transport=tcp"]}]',
        encoding="utf-8",
    )
    settings = Settings(
        TURN_BROWSER_CREDENTIAL_ISSUER_KIND="turnRest",
        TURN_FRONTEND_ICE_SERVERS_JSON_FILE=str(servers_file),
        TURN_REST_SHARED_SECRET_FILE=str(tmp_path / "missing-secret"),
    )

    with pytest.raises(RuntimeError, match="shared secret file is unreadable"):
        BrowserTurnCredentialIssuer.from_settings(settings)
