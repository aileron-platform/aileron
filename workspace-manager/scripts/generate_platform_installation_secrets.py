#!/usr/bin/env python3
"""Generate or validate the complete core platform installation secret set."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

try:
    from scripts.generate_runtime_assertion_keys import (
        BROWSER_CREDENTIAL_KEYRING_FILENAME,
        PRIVATE_KEY_FILENAME,
        PUBLIC_KEY_SET_FILENAME,
        ensure_browser_credential_keyring,
        ensure_runtime_assertion_keys,
    )
except ModuleNotFoundError:  # Direct execution inside the published image.
    from generate_runtime_assertion_keys import (  # type: ignore[no-redef]
        BROWSER_CREDENTIAL_KEYRING_FILENAME,
        PRIVATE_KEY_FILENAME,
        PUBLIC_KEY_SET_FILENAME,
        ensure_browser_credential_keyring,
        ensure_runtime_assertion_keys,
    )

DEFAULT_REGISTRY = Path("/contracts/platform-installation/secret-registry.json")
RUNTIME_ASSERTION_KEY_ID = "workspace-manager-ed25519-v1"
BROWSER_KEY_ID = "workspace-manager-browser-credential-v1"
URL_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TURN_URL_PATTERN = re.compile(
    r"^(?:turn|turns):"
    r"(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)"
    r"(?::([0-9]{1,5}))?(?:\?transport=(?:udp|tcp))?$"
)


class PlatformSecretArtifactError(RuntimeError):
    """Raised when platform installation artifacts are partial or unsafe."""


def _load_registry(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlatformSecretArtifactError(
            "Secret registry is unreadable or invalid"
        ) from exc
    if document.get("version") != "platform-secret-installation/v1":
        raise PlatformSecretArtifactError("Secret registry version is unsupported")
    return document


def _write_private(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        value = content.encode("utf-8") if isinstance(content, str) else content
        os.write(descriptor, value)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _condition_matches(condition: str | None, selectors: dict[str, bool]) -> bool:
    if condition is None:
        return True
    name, separator, raw_value = condition.partition("=")
    if separator != "=" or name not in selectors or raw_value not in {"true", "false"}:
        raise PlatformSecretArtifactError("Secret registry condition is invalid")
    return selectors[name] is (raw_value == "true")


def _expected_paths(
    registry: dict[str, Any], selectors: dict[str, bool]
) -> dict[str, Path]:
    return {
        artifact["id"]: Path(artifact["path"])
        for artifact in registry["artifacts"]
        if _condition_matches(artifact.get("when"), selectors)
        and (
            artifact["source"] == "generated"
            or (
                artifact["source"] == "selected"
                and selectors.get(artifact.get("selector")) is True
            )
        )
    }


def _validate_modes(output_directory: Path, paths: dict[str, Path]) -> None:
    if output_directory.stat().st_mode & 0o777 != 0o700:
        raise PlatformSecretArtifactError(
            "Artifact output directory must use mode 0700"
        )
    for relative_path in paths.values():
        path = output_directory / relative_path
        if path.stat().st_mode & 0o777 != 0o600:
            raise PlatformSecretArtifactError(
                f"Artifact file must use mode 0600: {relative_path}"
            )


def _read_text(output_directory: Path, paths: dict[str, Path], artifact_id: str) -> str:
    try:
        value = (output_directory / paths[artifact_id]).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PlatformSecretArtifactError(
            f"Artifact is unreadable: {artifact_id}"
        ) from exc
    if not value:
        raise PlatformSecretArtifactError(f"Artifact is empty: {artifact_id}")
    return value


def _validate_turn_url(turn_url: str) -> None:
    match = TURN_URL_PATTERN.fullmatch(turn_url)
    if match is None:
        raise PlatformSecretArtifactError(
            "TURN URL must be a valid turn: or turns: URI"
        )
    port = match.group(1)
    if port is not None and not 1 <= int(port) <= 65535:
        raise PlatformSecretArtifactError("TURN URL port is invalid")


def _validate_complete_set(
    output_directory: Path,
    paths: dict[str, Path],
    turn_url: str,
    *,
    postgres_enabled: bool,
) -> None:
    actual_files = {
        path.relative_to(output_directory)
        for path in output_directory.rglob("*")
        if path.is_file()
    }
    if actual_files != set(paths.values()):
        raise PlatformSecretArtifactError(
            "Artifact directory must contain the exact complete set"
        )
    _validate_modes(output_directory, paths)
    if postgres_enabled:
        username = _read_text(output_directory, paths, "postgres-username")
        password = _read_text(output_directory, paths, "postgres-password")
        if not URL_SAFE_PATTERN.fullmatch(username) or not URL_SAFE_PATTERN.fullmatch(
            password
        ):
            raise PlatformSecretArtifactError("PostgreSQL credentials are not URL-safe")
        expected_url = (
            f"postgresql://{username}:{password}@aileron-postgres:5432/aileron"
        )
        if _read_text(output_directory, paths, "database-url") != expected_url:
            raise PlatformSecretArtifactError(
                "Existing database URL does not match credentials"
            )
    runtime_key = _read_text(output_directory, paths, "runtime-database-credential-key")
    if len(runtime_key) != 64 or not URL_SAFE_PATTERN.fullmatch(runtime_key):
        raise PlatformSecretArtifactError("Runtime database credential key is invalid")

    with TemporaryDirectory() as temporary:
        validation_dir = Path(temporary)
        (validation_dir / PRIVATE_KEY_FILENAME).write_bytes(
            (output_directory / paths["runtime-assertion-private-key"]).read_bytes()
        )
        (validation_dir / PUBLIC_KEY_SET_FILENAME).write_bytes(
            (output_directory / paths["runtime-assertion-public-jwks"]).read_bytes()
        )
        ensure_runtime_assertion_keys(validation_dir, RUNTIME_ASSERTION_KEY_ID)

    with TemporaryDirectory() as temporary:
        validation_dir = Path(temporary)
        validation_keyring = validation_dir / BROWSER_CREDENTIAL_KEYRING_FILENAME
        validation_keyring.write_bytes(
            (output_directory / paths["browser-credential-keyring"]).read_bytes()
        )
        validation_keyring.chmod(0o600)
        ensure_browser_credential_keyring(validation_dir, BROWSER_KEY_ID)
    frontend = json.loads(
        _read_text(output_directory, paths, "turn-frontend-ice-servers")
    )
    backend = json.loads(
        _read_text(output_directory, paths, "turn-backend-ice-servers")
    )
    probe = json.loads(
        _read_text(output_directory, paths, "connectivity-probe-ice-servers")
    )
    if frontend != [{"urls": [turn_url]}] or backend != frontend or probe != frontend:
        raise PlatformSecretArtifactError("TURN ICE server artifacts are inconsistent")
    agent_token = _read_text(output_directory, paths, "connectivity-agent-host-token")
    agent_tokens = json.loads(
        _read_text(output_directory, paths, "connectivity-agent-tokens")
    )
    if agent_tokens != {"host": agent_token}:
        raise PlatformSecretArtifactError(
            "Connectivity agent token artifacts are inconsistent"
        )
    for artifact_id in (
        "turn-rest-shared-secret",
        "coturn-probe-credential",
        "connectivity-internal-token",
        "connectivity-agent-host-token",
    ):
        if not URL_SAFE_PATTERN.fullmatch(
            _read_text(output_directory, paths, artifact_id)
        ):
            raise PlatformSecretArtifactError(
                f"Generated token is invalid: {artifact_id}"
            )


def _generate(
    output_directory: Path,
    paths: dict[str, Path],
    turn_url: str,
    *,
    postgres_enabled: bool,
) -> None:
    shared_secret = secrets.token_urlsafe(48)
    host_token = secrets.token_urlsafe(48)
    ice_servers = json.dumps([{"urls": [turn_url]}], separators=(",", ":"))
    values = {
        "runtime-database-credential-key": secrets.token_urlsafe(48),
        "turn-rest-shared-secret": shared_secret,
        "turn-backend-ice-servers": ice_servers,
        "turn-frontend-ice-servers": ice_servers,
        "coturn-probe-username": "aileron-probe",
        "coturn-probe-credential": secrets.token_urlsafe(48),
        "connectivity-internal-token": secrets.token_urlsafe(48),
        "connectivity-agent-host-token": host_token,
        "connectivity-agent-tokens": json.dumps(
            {"host": host_token}, separators=(",", ":")
        ),
        "connectivity-probe-ice-servers": ice_servers,
    }
    for artifact_id, value in values.items():
        _write_private(output_directory / paths[artifact_id], value)

    if postgres_enabled:
        _generate_postgres_artifacts(output_directory, paths)

    assertion_directory = (
        output_directory / paths["runtime-assertion-private-key"].parent
    )
    assertion_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    ensure_runtime_assertion_keys(assertion_directory, RUNTIME_ASSERTION_KEY_ID)
    (assertion_directory / PUBLIC_KEY_SET_FILENAME).chmod(0o600)

    with TemporaryDirectory() as temporary:
        temporary_directory = Path(temporary)
        ensure_browser_credential_keyring(temporary_directory, BROWSER_KEY_ID)
        _write_private(
            output_directory / paths["browser-credential-keyring"],
            (temporary_directory / BROWSER_CREDENTIAL_KEYRING_FILENAME).read_bytes(),
        )


def _generate_postgres_artifacts(
    output_directory: Path,
    paths: dict[str, Path],
) -> None:
    username = f"aileron_{secrets.token_hex(6)}"
    password = secrets.token_urlsafe(36)
    values = {
        "postgres-username": username,
        "postgres-password": password,
        "database-url": (
            f"postgresql://{username}:{password}@aileron-postgres:5432/aileron"
        ),
    }
    for artifact_id, value in values.items():
        _write_private(output_directory / paths[artifact_id], value)


def _remove_postgres_artifacts(
    output_directory: Path,
    paths: dict[str, Path],
) -> None:
    for artifact_id in ("postgres-username", "postgres-password", "database-url"):
        (output_directory / paths[artifact_id]).unlink()


def _validate_existing_complete_set(
    output_directory: Path,
    paths: dict[str, Path],
    turn_url: str,
    *,
    postgres_enabled: bool,
) -> None:
    try:
        _validate_complete_set(
            output_directory,
            paths,
            turn_url,
            postgres_enabled=postgres_enabled,
        )
    except PlatformSecretArtifactError:
        raise
    except Exception as exc:
        raise PlatformSecretArtifactError("Existing artifact set is invalid") from exc


def ensure_platform_secret_artifacts(
    output_directory: Path,
    registry_path: Path,
    turn_url: str,
    *,
    postgres_enabled: bool = True,
) -> None:
    """Create or reconcile one complete validated platform artifact set."""

    _validate_turn_url(turn_url)
    registry = _load_registry(registry_path)
    selectors = {"postgres.enabled": postgres_enabled, "redis.enabled": True}
    paths = _expected_paths(registry, selectors)
    alternate_paths = _expected_paths(
        registry,
        {"postgres.enabled": not postgres_enabled, "redis.enabled": True},
    )
    actual_files = (
        {
            path.relative_to(output_directory)
            for path in output_directory.rglob("*")
            if path.is_file()
        }
        if output_directory.exists()
        else set()
    )
    if output_directory.exists():
        if actual_files == set(paths.values()):
            _validate_existing_complete_set(
                output_directory,
                paths,
                turn_url,
                postgres_enabled=postgres_enabled,
            )
            return
        if actual_files == set(alternate_paths.values()):
            _validate_existing_complete_set(
                output_directory,
                alternate_paths,
                turn_url,
                postgres_enabled=not postgres_enabled,
            )
            if postgres_enabled:
                _generate_postgres_artifacts(output_directory, paths)
            else:
                _remove_postgres_artifacts(output_directory, alternate_paths)
            _validate_existing_complete_set(
                output_directory,
                paths,
                turn_url,
                postgres_enabled=postgres_enabled,
            )
            return
        if actual_files:
            raise PlatformSecretArtifactError(
                "Existing artifacts must contain the complete set"
            )
        if any(output_directory.iterdir()):
            raise PlatformSecretArtifactError(
                "Artifact output directory contains unknown files"
            )
    else:
        output_directory.mkdir(mode=0o700, parents=True)
    output_directory.chmod(0o700)
    try:
        _generate(
            output_directory,
            paths,
            turn_url,
            postgres_enabled=postgres_enabled,
        )
        _validate_complete_set(
            output_directory,
            paths,
            turn_url,
            postgres_enabled=postgres_enabled,
        )
    except Exception as exc:
        for path in paths.values():
            (output_directory / path).unlink(missing_ok=True)
        directories = sorted(
            {output_directory / path.parent for path in paths.values()},
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
        if isinstance(exc, PlatformSecretArtifactError):
            raise
        raise PlatformSecretArtifactError(
            "Artifact generation or validation failed"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--turn-url", required=True)
    parser.add_argument("--values", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        values = json.loads(arguments.values.read_text(encoding="utf-8"))
        postgres_enabled = values["postgres"]["enabled"]
        if not isinstance(postgres_enabled, bool):
            raise PlatformSecretArtifactError("Core values postgres.enabled is invalid")
        ensure_platform_secret_artifacts(
            arguments.output_directory,
            arguments.registry,
            arguments.turn_url,
            postgres_enabled=postgres_enabled,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        parser.error("Core values are unreadable or invalid")
    except PlatformSecretArtifactError as exc:
        parser.error(str(exc))
    print("Core platform secret artifacts are ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
