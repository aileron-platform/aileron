"""Workspace Manager platform OIDC settings contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def _settings(secret_file: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "ENV": "production",
        "PLATFORM_PUBLIC_ORIGIN": "https://aileron.example.com:8443",
        "OIDC_ISSUER_URL": "https://identity.example.com/realms/aileron",
        "OIDC_CLIENT_ID": "aileron-manager",
        "OIDC_CLIENT_SECRET_FILE": str(secret_file),
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.unit
def test_oidc_urls_are_derived_from_canonical_settings(tmp_path: Path) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")

    settings = _settings(secret_file)

    assert settings.oidc_discovery_url == (
        "https://identity.example.com/realms/aileron/"
        ".well-known/openid-configuration"
    )
    assert settings.oidc_callback_url == (
        "https://aileron.example.com:8443/api/v1/oauth2/callback"
    )
    assert settings.oidc_post_logout_redirect_url == (
        "https://aileron.example.com:8443/login"
    )
    assert settings.cors_allowed_origins == ["https://aileron.example.com:8443"]


@pytest.mark.unit
def test_development_oidc_issuer_allows_compose_service_host(
    tmp_path: Path,
) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")

    settings = _settings(
        secret_file,
        ENV="development",
        PLATFORM_PUBLIC_ORIGIN="http://127.0.0.1:8082",
        OIDC_ISSUER_URL="http://workspace-manager:8080/realms/aileron",
    )

    assert settings.OIDC_ISSUER_URL == (
        "http://workspace-manager:8080/realms/aileron"
    )


@pytest.mark.unit
def test_development_public_origin_still_requires_loopback_http(
    tmp_path: Path,
) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="PLATFORM_PUBLIC_ORIGIN"):
        _settings(
            secret_file,
            ENV="development",
            PLATFORM_PUBLIC_ORIGIN="http://frontend:8082",
        )


@pytest.mark.unit
def test_oidc_client_secret_is_loaded_only_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "legacy-value-secret")

    settings = _settings(secret_file)

    assert settings.oidc_client_secret == "file-secret"
    assert "OIDC_CLIENT_SECRET" not in Settings.model_fields


@pytest.mark.unit
@pytest.mark.parametrize(
    "origin",
    [
        "https://user@example.com",
        "https://aileron.example.com/",
        "https://aileron.example.com/path",
        "https://aileron.example.com?mode=test",
        "https://aileron.example.com#fragment",
    ],
)
def test_platform_public_origin_rejects_non_origin_urls(
    tmp_path: Path,
    origin: str,
) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="PLATFORM_PUBLIC_ORIGIN"):
        _settings(secret_file, PLATFORM_PUBLIC_ORIGIN=origin)


@pytest.mark.unit
def test_removed_oidc_aliases_are_not_settings_fields() -> None:
    removed_names = {
        "ALLOWED_ORIGINS",
        "FRONTEND_ORIGIN",
        "OIDC_CLIENT_SECRET",
        "OIDC_DISCOVERY_URL",
        "OIDC_POST_LOGOUT_REDIRECT_URI",
        "OIDC_REDIRECT_URI",
    }

    assert removed_names.isdisjoint(Settings.model_fields)


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing_field",
    ["PLATFORM_PUBLIC_ORIGIN", "OIDC_ISSUER_URL", "OIDC_CLIENT_ID"],
)
def test_platform_identity_inputs_are_required(
    monkeypatch: pytest.MonkeyPatch,
    missing_field: str,
) -> None:
    values: dict[str, object] = {
        "PLATFORM_PUBLIC_ORIGIN": "https://aileron.example.com",
        "OIDC_ISSUER_URL": "https://identity.example.com/realms/aileron",
        "OIDC_CLIENT_ID": "aileron-manager",
    }
    values.pop(missing_field)
    monkeypatch.delenv(missing_field, raising=False)

    with pytest.raises(ValidationError, match=missing_field):
        Settings(**values)
