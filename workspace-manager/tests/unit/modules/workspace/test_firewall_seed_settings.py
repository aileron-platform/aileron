import json

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_firewall_seed_file_loads_complete_normalized_config(tmp_path) -> None:
    seed_file = tmp_path / "firewall-seed.json"
    seed_file.write_text(
        json.dumps(
            {
                "workspace": {
                    "egressMode": "allowlist",
                    "allowedDomains": [" GitHub.com. "],
                },
                "browser": {
                    "egressMode": "blocked",
                    "allowedDomains": [],
                },
            }
        ),
        encoding="utf-8",
    )

    settings = Settings(FIREWALL_SEED_FILE=str(seed_file))

    assert settings.firewall_seed.workspace.allowed_domains == ["github.com"]
    assert settings.firewall_seed.browser.egress_mode == "blocked"


def test_firewall_seed_file_rejects_invalid_shape(tmp_path) -> None:
    seed_file = tmp_path / "firewall-seed.json"
    seed_file.write_text(
        json.dumps(
            {
                "workspace": {
                    "egressMode": "invalid",
                    "allowedDomains": [],
                },
                "browser": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        Settings(FIREWALL_SEED_FILE=str(seed_file))


def test_firewall_seed_file_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(ValidationError, match="Invalid FIREWALL_SEED_FILE"):
        Settings(FIREWALL_SEED_FILE=str(tmp_path / "missing.json"))


def test_firewall_seed_file_rejects_incomplete_rule(tmp_path) -> None:
    seed_file = tmp_path / "firewall-seed.json"
    seed_file.write_text(
        json.dumps(
            {
                "workspace": {
                    "allowedDomains": ["github.com"],
                },
                "browser": {
                    "egressMode": "allowlist",
                    "allowedDomains": ["google.com"],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="workspace rule must be complete"):
        Settings(FIREWALL_SEED_FILE=str(seed_file))
