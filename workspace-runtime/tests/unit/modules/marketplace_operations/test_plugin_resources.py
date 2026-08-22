from pathlib import Path

from app.modules.marketplace_operations.plugin_resources import (
    sanitize_plugin_definition,
)


def test_sanitizer_redacts_root_secrets_and_url_credentials() -> None:
    installed_root = Path("/home/developer/.local/state/aileron/plugins/demo")

    result = sanitize_plugin_definition(
        {
            "command": ("/home/developer/.local/state/aileron/plugins/demo/bin/server"),
            "args": [
                "--config=/home/developer/.local/state/aileron/plugins/demo/config.json"
            ],
            "env": {
                "ACCESS_TOKEN": "secret-token",
                "PUBLIC_MODE": "safe",
            },
            "headers": {
                "Authorization": "Bearer secret-token",
                "X-Mode": "safe",
            },
            "endpoint": (
                "https://user:password@example.test/api"
                "?access_token=secret-token&mode=safe"
            ),
        },
        installed_root=installed_root,
    )

    assert result == {
        "command": "${PLUGIN_ROOT}/bin/server",
        "args": ["--config=${PLUGIN_ROOT}/config.json"],
        "env": {
            "ACCESS_TOKEN": "[REDACTED]",
            "PUBLIC_MODE": "[REDACTED]",
        },
        "headers": {
            "Authorization": "[REDACTED]",
            "X-Mode": "safe",
        },
        "endpoint": (
            "https://%5BREDACTED%5D@example.test/api"
            "?access_token=%5BREDACTED%5D&mode=safe"
        ),
    }


def test_sanitizer_normalizes_target_client_root_placeholders() -> None:
    result = sanitize_plugin_definition(
        {
            "claude": "${CLAUDE_PLUGIN_ROOT}/bin/server",
            "codex": "${CODEX_PLUGIN_ROOT}/bin/server",
        },
        installed_root=Path("/home/developer/.local/state/aileron/plugins/demo"),
    )

    assert result == {
        "claude": "${PLUGIN_ROOT}/bin/server",
        "codex": "${PLUGIN_ROOT}/bin/server",
    }
