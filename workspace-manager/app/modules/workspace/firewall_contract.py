import ipaddress
import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.core.pydantic import CamelModel

FirewallEgressMode = Literal["blocked", "allowlist", "unrestricted"]
FirewallSyncStatus = Literal["pending", "applying", "applied", "error", "unavailable"]
FIREWALL_DOMAIN_LIMIT = 128
FIREWALL_DOMAIN_BYTES_LIMIT = 16 * 1024
_DOMAIN_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_firewall_domain(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.endswith("."):
        normalized = normalized[:-1]
    if (
        not normalized
        or "://" in normalized
        or any(character in normalized for character in "/*?#:@")
    ):
        raise PydanticCustomError(
            "FIREWALL_DOMAIN_INVALID",
            "firewall.domain.invalid",
        )
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise PydanticCustomError(
            "FIREWALL_DOMAIN_INVALID",
            "firewall.domain.invalid",
        )
    try:
        ascii_domain = normalized.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise PydanticCustomError(
            "FIREWALL_DOMAIN_INVALID",
            "firewall.domain.invalid",
        ) from exc
    if len(ascii_domain) > 253 or any(
        not _DOMAIN_LABEL_PATTERN.fullmatch(label) for label in ascii_domain.split(".")
    ):
        raise PydanticCustomError(
            "FIREWALL_DOMAIN_INVALID",
            "firewall.domain.invalid",
        )
    return ascii_domain


class FirewallRuleConfig(CamelModel):
    egress_mode: FirewallEgressMode = Field("unrestricted", alias="egressMode")
    allowed_domains: list[str] = Field(default_factory=list, alias="allowedDomains")

    model_config = ConfigDict(extra="forbid")

    @field_validator("allowed_domains")
    @classmethod
    def normalize_allowed_domains(cls, value: list[str]) -> list[str]:
        if len(value) > FIREWALL_DOMAIN_LIMIT:
            raise PydanticCustomError(
                "FIREWALL_DOMAIN_LIMIT_EXCEEDED",
                "firewall.domain.limitExceeded",
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for domain in value:
            normalized_domain = normalize_firewall_domain(domain)
            if normalized_domain in seen:
                raise PydanticCustomError(
                    "FIREWALL_DOMAIN_DUPLICATE",
                    "firewall.domain.duplicate",
                )
            seen.add(normalized_domain)
            normalized.append(normalized_domain)
        if sum(len(domain.encode("ascii")) for domain in normalized) > (
            FIREWALL_DOMAIN_BYTES_LIMIT
        ):
            raise PydanticCustomError(
                "FIREWALL_DOMAIN_LIMIT_EXCEEDED",
                "firewall.domain.limitExceeded",
            )
        return normalized

    @model_validator(mode="after")
    def validate_allowed_domains_for_mode(self) -> "FirewallRuleConfig":
        if self.egress_mode == "allowlist" and not self.allowed_domains:
            raise PydanticCustomError(
                "FIREWALL_ALLOWLIST_EMPTY",
                "firewall.domain.allowlistRequired",
            )
        if self.egress_mode != "allowlist" and self.allowed_domains:
            raise PydanticCustomError(
                "FIREWALL_DOMAINS_NOT_ALLOWED",
                "firewall.domain.notAllowedForEgressMode",
            )
        return self


class FirewallConfig(CamelModel):
    workspace: FirewallRuleConfig = Field(default_factory=FirewallRuleConfig)
    browser: FirewallRuleConfig = Field(default_factory=FirewallRuleConfig)

    model_config = ConfigDict(extra="forbid")


class FirewallReplacementRequest(CamelModel):
    revision: int = Field(ge=1)
    workspace: FirewallRuleConfig
    browser: FirewallRuleConfig

    model_config = ConfigDict(extra="forbid")


class FirewallResource(CamelModel):
    revision: int
    observed_revision: int = Field(alias="observedRevision")
    sync_status: FirewallSyncStatus = Field(alias="syncStatus")
    error_code: str | None = Field(default=None, alias="errorCode")
    workspace: FirewallRuleConfig
    browser: FirewallRuleConfig

    model_config = ConfigDict(extra="forbid")


def validate_firewall_seed_payload(payload: object) -> FirewallConfig:
    if not isinstance(payload, dict) or set(payload) != {"workspace", "browser"}:
        raise ValueError("Firewall seed must define workspace and browser")
    required_rule_fields = {
        "egressMode",
        "allowedDomains",
    }
    for group in ("workspace", "browser"):
        rule = payload[group]
        if not isinstance(rule, dict) or set(rule) != required_rule_fields:
            raise ValueError(f"Firewall seed {group} rule must be complete")
    return FirewallConfig.model_validate(payload)
