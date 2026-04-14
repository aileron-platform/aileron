"""KeycloakConfig 單元測試"""

from __future__ import annotations

from unittest.mock import patch

from app.modules.auth.config import KeycloakConfig


def test_keycloak_config_distinguishes_internal_and_external_urls():
    with patch.dict(
        "os.environ",
        {
            "KEYCLOAK_SERVER_URL": "http://keycloak.internal:8080",
            "KEYCLOAK_EXTERNAL_SERVER_URL": "https://keycloak.example.com",
            "KEYCLOAK_REALM": "aileron",
            "KEYCLOAK_CLIENT_ID": "aileron-frontend",
        },
        clear=False,
    ):
        config = KeycloakConfig.from_env()

    assert config.server_url == "http://keycloak.internal:8080/realms/aileron"
    assert config.external_server_url == "https://keycloak.example.com/realms/aileron"
    assert (
        config.get_openid_configuration()["authorization_endpoint"]
        == "https://keycloak.example.com/realms/aileron/protocol/openid-connect/auth"
    )
    assert (
        config.get_openid_configuration()["token_endpoint"]
        == "http://keycloak.internal:8080/realms/aileron/protocol/openid-connect/token"
    )
