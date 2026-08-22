"""Tests for provider-owned email snapshot validation."""

from __future__ import annotations

from typing import Optional

import email_validator
import pytest
from pydantic import TypeAdapter, ValidationError

from app.modules.identity.provider_email import ProviderEmailStr
from app.modules.identity.user_models import UserBase
from app.modules.settings.models import UserProfile

provider_email_adapter = TypeAdapter(ProviderEmailStr)


@pytest.mark.parametrize(
    ("candidate", "normalized"),
    [
        ("USER@EXAMPLE.COM", "USER@example.com"),
        (" user@example.com ", "user@example.com"),
    ],
)
def test_public_email_preserves_email_str_normalization(
    candidate: str, normalized: str
) -> None:
    assert provider_email_adapter.validate_python(candidate) == normalized


@pytest.mark.parametrize("terminal", email_validator.SPECIAL_USE_DOMAIN_NAMES)
def test_special_use_provider_domain_is_accepted(terminal: str) -> None:
    candidate = f"person@identity.{terminal.upper()}"

    assert provider_email_adapter.validate_python(candidate) == (
        f"person@identity.{terminal}"
    )


def test_single_label_special_use_provider_domain_is_accepted() -> None:
    assert provider_email_adapter.validate_python("person@LOCALHOST") == (
        "person@localhost"
    )


def test_single_label_internal_provider_domain_is_accepted() -> None:
    assert provider_email_adapter.validate_python("Person@IDENTITY") == (
        "Person@identity"
    )


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "not-an-email",
        "person name@identity",
        "person@identity ",
        "person@@identity",
        ".person@identity",
        "person@-identity",
        "person@example.123",
        f"{'a' * 65}@identity",
        f"person@{'a' * 64}",
    ],
)
def test_malformed_provider_email_is_rejected(candidate: str) -> None:
    with pytest.raises(ValidationError):
        provider_email_adapter.validate_python(candidate)


def test_optional_provider_email_preserves_none() -> None:
    assert TypeAdapter(Optional[ProviderEmailStr]).validate_python(None) is None


def test_provider_email_json_schema_keeps_email_format() -> None:
    schema = provider_email_adapter.json_schema()

    assert schema["type"] == "string"
    assert schema["format"] == "email"
    assert UserProfile.model_json_schema()["properties"]["email"]["format"] == "email"
    user_email_schema = UserBase.model_json_schema()["properties"]["email"]
    assert {"type": "string", "format": "email"} in user_email_schema["anyOf"]


def test_model_validation_error_redacts_candidate_and_validator_detail() -> None:
    candidate = "private person @identity"

    errors: list[ValidationError] = []
    with pytest.raises(ValidationError) as user_error:
        UserBase(username="person", email=candidate)
    errors.append(user_error.value)

    with pytest.raises(ValidationError) as profile_error:
        UserProfile(userId="user-123", username="person", email=candidate)
    errors.append(profile_error.value)

    for error in errors:
        rendered = str(error)
        assert candidate not in rendered
        assert "invalid characters" not in rendered
        assert "SPACE" not in rendered
        assert "Input must be a valid provider email address" in rendered


def test_validation_does_not_change_email_validator_global_policy() -> None:
    original_policy = (
        tuple(email_validator.SPECIAL_USE_DOMAIN_NAMES),
        email_validator.GLOBALLY_DELIVERABLE,
        email_validator.TEST_ENVIRONMENT,
        email_validator.CHECK_DELIVERABILITY,
    )

    assert provider_email_adapter.validate_python("person@identity.invalid") == (
        "person@identity.invalid"
    )
    assert (
        tuple(email_validator.SPECIAL_USE_DOMAIN_NAMES),
        email_validator.GLOBALLY_DELIVERABLE,
        email_validator.TEST_ENVIRONMENT,
        email_validator.CHECK_DELIVERABILITY,
    ) == original_policy
