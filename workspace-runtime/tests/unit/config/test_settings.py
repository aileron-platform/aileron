from __future__ import annotations

from app.config.settings import Settings


def test_effective_allowed_origins_includes_frontend_public_url() -> None:
    settings = Settings(
        ENV="production",
        ALLOWED_ORIGINS=["https://custom.example.com"],
        FRONTEND_PUBLIC_URL="https://app.example.com/",
    )

    assert settings.effective_allowed_origins == [
        "https://custom.example.com",
        "https://app.example.com",
    ]


def test_effective_allowed_origins_falls_back_to_localhost_in_development() -> None:
    settings = Settings(ENV="development")

    assert settings.effective_allowed_origins == [
        "http://localhost:8082",
        "http://127.0.0.1:8082",
    ]


def test_effective_allowed_origins_is_empty_in_production_without_configuration() -> None:
    settings = Settings(ENV="production")

    assert settings.effective_allowed_origins == []
