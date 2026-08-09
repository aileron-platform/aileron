from __future__ import annotations

import base64
import json

import pytest

from app.modules.workspace.browser_credentials import (
    BROWSER_CREDENTIAL_ALGORITHM,
    BrowserCredentialConfigurationError,
    BrowserCredentialService,
)


def _keyring(tmp_path):
    path = tmp_path / "browser-keyring.json"
    path.write_text(
        json.dumps(
            {
                "algorithm": BROWSER_CREDENTIAL_ALGORITHM,
                "activeKeyId": "browser-key-1",
                "keys": {
                    "browser-key-1": base64.urlsafe_b64encode(b"a" * 32)
                    .rstrip(b"=")
                    .decode("ascii"),
                    "browser-key-previous": base64.urlsafe_b64encode(b"b" * 32)
                    .rstrip(b"=")
                    .decode("ascii"),
                },
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def test_browser_credentials_are_deterministic_role_and_revision_bound(tmp_path):
    service = BrowserCredentialService(_keyring(tmp_path))
    first = service.derive(
        workspace_id="11111111-1111-4111-8111-111111111111",
        revision=1,
        key_id=service.active_key_id,
        algorithm=BROWSER_CREDENTIAL_ALGORITHM,
    )
    repeated = service.derive(
        workspace_id="11111111-1111-4111-8111-111111111111",
        revision=1,
        key_id=service.active_key_id,
        algorithm=BROWSER_CREDENTIAL_ALGORITHM,
    )
    rotated = service.derive(
        workspace_id="11111111-1111-4111-8111-111111111111",
        revision=2,
        key_id=service.active_key_id,
        algorithm=BROWSER_CREDENTIAL_ALGORITHM,
    )

    assert repeated == first
    assert first.user_password != first.admin_password
    assert first.user_password != rotated.user_password
    assert "=" not in first.user_password
    assert service.loaded_key_ids == ("browser-key-1", "browser-key-previous")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(activeKeyId="missing"),
        lambda payload: payload.update(algorithm="unknown"),
        lambda payload: payload["keys"].update({"browser-key-1": "short"}),
    ],
)
def test_browser_keyring_fails_closed_on_invalid_schema(tmp_path, mutation):
    path = _keyring(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutation(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(BrowserCredentialConfigurationError):
        BrowserCredentialService(path)


def test_browser_keyring_rejects_world_permissions(tmp_path):
    path = _keyring(tmp_path)
    path.chmod(0o604)
    with pytest.raises(
        BrowserCredentialConfigurationError,
        match="BROWSER_CREDENTIAL_KEYRING_PERMISSIONS_INVALID",
    ):
        BrowserCredentialService(path)
