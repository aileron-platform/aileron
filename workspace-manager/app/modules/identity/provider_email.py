"""Validation for provider-owned email identity snapshots."""

from __future__ import annotations

from typing import Annotated, NoReturn, Optional

from email_validator import (
    SPECIAL_USE_DOMAIN_NAMES,
    EmailNotValidError,
)
from email_validator import validate_email as validate_email_syntax
from pydantic import AfterValidator, WithJsonSchema
from pydantic.networks import validate_email as validate_pydantic_email
from pydantic_core import PydanticCustomError

_SPECIAL_USE_DOMAINS = frozenset(SPECIAL_USE_DOMAIN_NAMES)
_ERROR_CODE = "provider_email"
_ERROR_MESSAGE = "Input must be a valid provider email address"


def _raise_invalid_provider_email() -> NoReturn:
    raise PydanticCustomError(_ERROR_CODE, _ERROR_MESSAGE)


def _special_use_surrogate(domain: str, terminal: str) -> str:
    """Keep length and syntax checks while avoiding global policy changes."""
    if "." in domain:
        return f"{domain[: -len(terminal)]}{'x' * len(terminal)}"

    # All email-validator special-use names are at least four characters long.
    # A two-label surrogate keeps the original length while satisfying the
    # globally-deliverable shape check.
    return f"{'x' * (len(terminal) - 2)}.x"


def _validate_special_use_email(
    local_part: str, domain: str, terminal: str
) -> Optional[str]:
    surrogate_domain = _special_use_surrogate(domain, terminal)
    try:
        result = validate_email_syntax(
            f"{local_part}@{surrogate_domain}",
            check_deliverability=False,
            strict=True,
        )
    except EmailNotValidError:
        return None

    if "." in domain:
        normalized_prefix = result.domain.rsplit(".", 1)[0]
        normalized_domain = f"{normalized_prefix}.{terminal}"
    else:
        normalized_domain = terminal
    return f"{result.local_part}@{normalized_domain}"


def _validate_internal_email(value: str) -> Optional[str]:
    if not value or any(character.isspace() for character in value):
        return None
    if value.count("@") != 1:
        return None

    local_part, domain = value.rsplit("@", 1)
    if not local_part or not domain:
        return None

    terminal = domain.rsplit(".", 1)[-1].lower()
    if terminal in _SPECIAL_USE_DOMAINS:
        return _validate_special_use_email(local_part, domain, terminal)

    if "." in domain:
        return None

    try:
        result = validate_email_syntax(
            value,
            check_deliverability=False,
            globally_deliverable=False,
            strict=True,
        )
    except EmailNotValidError:
        return None

    if result.ascii_domain is None or "." in result.ascii_domain:
        return None
    return result.normalized


def _validate_provider_email(value: str) -> str:
    try:
        return validate_pydantic_email(value)[1]
    except PydanticCustomError:
        pass

    normalized = _validate_internal_email(value)
    if normalized is None:
        _raise_invalid_provider_email()
    return normalized


ProviderEmailStr = Annotated[
    str,
    AfterValidator(_validate_provider_email),
    WithJsonSchema({"type": "string", "format": "email"}),
]


__all__ = ["ProviderEmailStr"]
