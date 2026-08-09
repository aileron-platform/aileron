from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_runtime_settings_start_with_canonical_platform_environment(tmp_path) -> None:
    database_url_file = tmp_path / "runtime-state-database-url"
    database_url_file.write_text(
        "  postgresql://runtime:password@postgres/runtime\n", encoding="utf-8"
    )
    control_token_file = tmp_path / "runtime-control-token"
    control_token_file.write_text("  generation-token\n", encoding="utf-8")

    settings = Settings(
        AILERON_WORKSPACE_ID="workspace-1",
        AILERON_WORKSPACE_PATH="/workspace",
        AILERON_RUNTIME_INSTANCE_ID="11111111-1111-4111-8111-111111111111",
        AILERON_RUNTIME_ACCESS_REVISION=7,
        AILERON_KB_MOUNT_REVISION=3,
        AILERON_WORKTREE_SUBDIR=".worktrees",
        AILERON_RUNTIME_STATE_DATABASE_URL_FILE=str(database_url_file),
        AILERON_RUNTIME_CONTROL_TOKEN_FILE=str(control_token_file),
        AILERON_MANAGER_INTERNAL_URL="http://workspace-manager:8000",
        AILERON_PLATFORM_PUBLIC_ORIGIN="https://aileron.example.com",
        AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE="/run/secrets/runtime-jwks.json",
        AILERON_RUNTIME_ASSERTION_ISSUER="workspace-manager",
        AILERON_BROWSER_SERVICE_NAME="workspace-browser",
        AILERON_BROWSER_WEBRTC_INTERNAL_URL="http://workspace-browser:6080",
        AILERON_BROWSER_CDP_URL="http://workspace-browser:9223",
        AILERON_CANVAS_SERVICE_NAME="workspace-canvas",
        AILERON_CANVAS_INTERNAL_URL="http://workspace-canvas:3003",
        AILERON_CANVAS_API_URL="http://workspace-canvas:3013",
    )

    assert settings.AILERON_WORKSPACE_ID == "workspace-1"
    assert settings.AILERON_WORKSPACE_PATH == "/workspace"
    assert (
        settings.AILERON_RUNTIME_STATE_DATABASE_URL_FILE.get_secret_value()
        == "postgresql://runtime:password@postgres/runtime"
    )
    assert (
        settings.AILERON_RUNTIME_CONTROL_TOKEN_FILE.get_secret_value()
        == "generation-token"
    )
    assert settings.effective_allowed_origins == ["https://aileron.example.com"]
    assert "WORKSPACE_ID" not in type(settings).model_fields
    assert "ALLOWED_ORIGINS" not in type(settings).model_fields


def _settings(tmp_path: Path, **values) -> Settings:
    database_url_file = tmp_path / "runtime-state-database-url"
    database_url_file.write_text(
        "postgresql://runtime:password@postgres/runtime", encoding="utf-8"
    )
    control_token_file = tmp_path / "runtime-control-token"
    control_token_file.write_text("generation-token", encoding="utf-8")
    settings_values = {
        "AILERON_WORKSPACE_ID": "workspace-1",
        "AILERON_WORKSPACE_PATH": "/workspace",
        "AILERON_RUNTIME_INSTANCE_ID": "11111111-1111-4111-8111-111111111111",
        "AILERON_RUNTIME_ACCESS_REVISION": 0,
        "AILERON_KB_MOUNT_REVISION": 0,
        "AILERON_WORKTREE_SUBDIR": ".worktrees",
        "AILERON_RUNTIME_STATE_DATABASE_URL_FILE": str(database_url_file),
        "AILERON_RUNTIME_CONTROL_TOKEN_FILE": str(control_token_file),
        "AILERON_MANAGER_INTERNAL_URL": "http://workspace-manager:8000",
        "AILERON_PLATFORM_PUBLIC_ORIGIN": "https://aileron.example.com",
        "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": "/run/secrets/runtime-jwks.json",
        "AILERON_RUNTIME_ASSERTION_ISSUER": "workspace-manager",
        "AILERON_BROWSER_SERVICE_NAME": "workspace-browser",
        "AILERON_BROWSER_WEBRTC_INTERNAL_URL": "http://workspace-browser:6080",
        "AILERON_BROWSER_CDP_URL": "http://workspace-browser:9223",
        "AILERON_CANVAS_SERVICE_NAME": "workspace-canvas",
        "AILERON_CANVAS_INTERNAL_URL": "http://workspace-canvas:3003",
        "AILERON_CANVAS_API_URL": "http://workspace-canvas:3013",
    }
    settings_values.update(values)
    return Settings(**settings_values)


def test_effective_allowed_origins_uses_exact_platform_origin(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    assert settings.effective_allowed_origins == ["https://aileron.example.com"]


def test_runtime_settings_do_not_load_service_dotenv() -> None:
    assert Settings.model_config.get("env_file") is None


def test_runtime_process_settings_are_typed(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        TERMINAL_PORT=3104,
        RUNTIME_ROUTE_INVENTORY_PATH="/run/aileron/runtime-routes.json",
        GIT_STALE_LOCK_THRESHOLD_SECONDS=41,
        LOG_LEVEL="warning",
    )

    assert settings.TERMINAL_PORT == 3104
    assert settings.RUNTIME_ROUTE_INVENTORY_PATH == "/run/aileron/runtime-routes.json"
    assert settings.GIT_STALE_LOCK_THRESHOLD_SECONDS == 41
    assert settings.LOG_LEVEL == "WARNING"


@pytest.mark.parametrize(
    "value",
    ["runtime-routes.json", " /run/aileron/runtime-routes.json"],
)
def test_runtime_route_inventory_override_requires_exact_absolute_path(
    tmp_path: Path,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, RUNTIME_ROUTE_INVENTORY_PATH=value)


@pytest.mark.parametrize("value", [0, 65536])
def test_terminal_port_must_be_valid(tmp_path: Path, value: int) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, TERMINAL_PORT=value)


def test_git_stale_lock_threshold_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, GIT_STALE_LOCK_THRESHOLD_SECONDS=0)


def test_log_level_rejects_unknown_value(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, LOG_LEVEL="verbose")


@pytest.mark.parametrize(
    "origin",
    [
        "https://aileron.example.com/",
        "https://aileron.example.com/path",
        "https://user@aileron.example.com",
        "https://aileron.example.com?query=1",
        "https://aileron.example.com:65536",
        "ftp://aileron.example.com",
    ],
)
def test_platform_public_origin_must_be_exact(
    tmp_path: Path,
    origin: str,
) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, AILERON_PLATFORM_PUBLIC_ORIGIN=origin)


def test_marketplace_operation_journal_defaults_to_user_state_home(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MARKETPLACE_OPERATION_JOURNAL_DIR", raising=False)
    monkeypatch.setenv("HOME", "/home/developer")
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    settings = _settings(tmp_path)

    assert (
        settings.MARKETPLACE_OPERATION_JOURNAL_DIR
        == "/home/developer/.local/state/aileron/marketplace-operations"
    )


def test_marketplace_operation_journal_uses_xdg_state_home(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MARKETPLACE_OPERATION_JOURNAL_DIR", raising=False)
    monkeypatch.setenv("HOME", "/home/developer")
    monkeypatch.setenv("XDG_STATE_HOME", "/state")
    settings = _settings(tmp_path)

    assert (
        settings.MARKETPLACE_OPERATION_JOURNAL_DIR
        == "/state/aileron/marketplace-operations"
    )


@pytest.mark.parametrize("value", [0, 4])
def test_automation_concurrency_must_stay_within_workspace_limit(
    tmp_path: Path,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, AUTOMATION_MAX_CONCURRENT_EXECUTIONS=value)


@pytest.mark.parametrize(
    "missing_field",
    [
        "AILERON_RUNTIME_STATE_DATABASE_URL_FILE",
        "AILERON_RUNTIME_CONTROL_TOKEN_FILE",
        "AILERON_RUNTIME_INSTANCE_ID",
    ],
)
def test_runtime_scoped_credentials_are_required(
    monkeypatch,
    tmp_path: Path,
    missing_field: str,
) -> None:
    monkeypatch.delenv(missing_field, raising=False)
    with pytest.raises(ValidationError):
        _settings(tmp_path, **{missing_field: None})


@pytest.mark.parametrize(
    "value",
    [
        "",
        "instance-a",
        "{11111111-1111-4111-8111-111111111111}",
        "11111111111141118111111111111111",
        "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
        " 11111111-1111-4111-8111-111111111111",
    ],
)
def test_runtime_instance_id_requires_canonical_uuid(
    tmp_path: Path,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, AILERON_RUNTIME_INSTANCE_ID=value)


def test_resource_telemetry_defaults_to_fifteen_minute_capacity_probes(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    assert settings.RESOURCE_TELEMETRY_INTERVAL_SECONDS == 900
    assert settings.RESOURCE_TELEMETRY_PROBE_TIMEOUT_SECONDS == 30


@pytest.mark.parametrize("value", [0, 59])
def test_resource_telemetry_interval_rejects_sub_minute_scans(
    tmp_path: Path,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, RESOURCE_TELEMETRY_INTERVAL_SECONDS=value)
