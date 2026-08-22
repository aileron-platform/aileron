"""Platform installation secret artifact contract tests."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from scripts.generate_platform_installation_secrets import (
    PlatformSecretArtifactError,
    ensure_platform_secret_artifacts,
)

REGISTRY = Path("/contracts/platform-installation/secret-registry.json")
TURN_URL = "turn:turn.example.test:3478"


def _generated_paths() -> set[str]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {
        artifact["path"]
        for artifact in registry["artifacts"]
        if artifact["source"] == "generated" or artifact["source"] == "selected"
    }


def test_generates_complete_private_artifact_set_and_reuses_it(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)

    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert {
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == _generated_paths()
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    before = {path: (tmp_path / path).read_bytes() for path in _generated_paths()}
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)
    after = {path: (tmp_path / path).read_bytes() for path in _generated_paths()}
    assert after == before


def test_database_url_uses_generated_url_safe_credentials(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)

    username = (tmp_path / "platform/postgres-username").read_text(encoding="utf-8")
    password = (tmp_path / "platform/postgres-password").read_text(encoding="utf-8")
    database_url = (tmp_path / "platform/database-url").read_text(encoding="utf-8")

    assert username.replace("_", "").isalnum()
    assert password.replace("_", "").replace("-", "").isalnum()
    assert database_url == (
        f"postgresql://{username}:{password}@aileron-postgres:5432/aileron"
    )


def test_external_postgres_mode_does_not_generate_bundled_artifacts(
    tmp_path: Path,
) -> None:
    ensure_platform_secret_artifacts(
        tmp_path,
        REGISTRY,
        TURN_URL,
        postgres_enabled=False,
    )

    assert not (tmp_path / "platform/postgres-username").exists()
    assert not (tmp_path / "platform/postgres-password").exists()
    assert not (tmp_path / "platform/database-url").exists()
    assert (tmp_path / "platform/runtime-database-credential-key").is_file()


def test_switching_to_external_postgres_removes_only_bundled_artifacts(
    tmp_path: Path,
) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)
    runtime_key = (tmp_path / "platform/runtime-database-credential-key").read_bytes()

    ensure_platform_secret_artifacts(
        tmp_path,
        REGISTRY,
        TURN_URL,
        postgres_enabled=False,
    )

    assert not (tmp_path / "platform/postgres-username").exists()
    assert not (tmp_path / "platform/postgres-password").exists()
    assert not (tmp_path / "platform/database-url").exists()
    assert (
        tmp_path / "platform/runtime-database-credential-key"
    ).read_bytes() == runtime_key


def test_switching_to_bundled_postgres_adds_only_bundled_artifacts(
    tmp_path: Path,
) -> None:
    ensure_platform_secret_artifacts(
        tmp_path,
        REGISTRY,
        TURN_URL,
        postgres_enabled=False,
    )
    runtime_key = (tmp_path / "platform/runtime-database-credential-key").read_bytes()

    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)

    assert (tmp_path / "platform/postgres-username").is_file()
    assert (tmp_path / "platform/postgres-password").is_file()
    assert (tmp_path / "platform/database-url").is_file()
    assert (
        tmp_path / "platform/runtime-database-credential-key"
    ).read_bytes() == runtime_key


def test_turn_and_connectivity_artifacts_are_consistent(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)

    backend = json.loads((tmp_path / "turn/backend-ice-servers-json").read_text())
    frontend = json.loads((tmp_path / "turn/frontend-ice-servers-json").read_text())
    probe = json.loads((tmp_path / "connectivity/probe-ice-servers-json").read_text())
    agent_tokens = json.loads((tmp_path / "connectivity/agent-tokens-json").read_text())

    assert backend == [{"urls": [TURN_URL]}]
    assert frontend == backend
    assert probe == frontend
    assert agent_tokens == {
        "host": (tmp_path / "connectivity/agent-host-token").read_text()
    }


def test_rejects_partial_existing_artifact_set(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    (tmp_path / "platform").mkdir(mode=0o700)
    (tmp_path / "platform/postgres-password").write_text("partial", encoding="utf-8")
    (tmp_path / "platform/postgres-password").chmod(0o600)

    with pytest.raises(PlatformSecretArtifactError, match="complete set"):
        ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)


def test_rejects_broad_directory_or_file_permissions(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)
    tmp_path.chmod(0o755)

    with pytest.raises(PlatformSecretArtifactError, match="0700"):
        ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)

    tmp_path.chmod(0o700)
    (tmp_path / "platform/postgres-password").chmod(0o644)
    with pytest.raises(PlatformSecretArtifactError, match="0600"):
        ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)


def test_rejects_modified_derived_artifact(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)
    (tmp_path / "platform/database-url").write_text("changed", encoding="utf-8")
    (tmp_path / "platform/database-url").chmod(0o600)

    with pytest.raises(PlatformSecretArtifactError, match="database URL"):
        ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)


def test_rejects_invalid_existing_browser_keyring(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)
    keyring = tmp_path / "browser/keyring.json"
    keyring.write_text('{"activeKeyId":"workspace-manager-browser-credential-v1"}')
    keyring.chmod(0o600)

    with pytest.raises(PlatformSecretArtifactError, match="invalid"):
        ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)


@pytest.mark.parametrize(
    "turn_url",
    [
        "https://turn.example.test",
        "turn:",
        "turn:host:70000",
        "turn:host value:3478",
    ],
)
def test_rejects_invalid_turn_url(tmp_path: Path, turn_url: str) -> None:
    with pytest.raises(PlatformSecretArtifactError, match="TURN URL"):
        ensure_platform_secret_artifacts(tmp_path, REGISTRY, turn_url)


def test_rejects_existing_artifacts_for_a_different_turn_url(tmp_path: Path) -> None:
    ensure_platform_secret_artifacts(tmp_path, REGISTRY, TURN_URL)

    with pytest.raises(PlatformSecretArtifactError, match="inconsistent"):
        ensure_platform_secret_artifacts(
            tmp_path, REGISTRY, "turns:turn.other-domain.test:5349?transport=tcp"
        )
