"""Workspace request model validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.workspace.firewall_contract import FirewallRuleConfig
from app.modules.workspace.models import (
    SETUP_SCRIPT_MAX_BYTES,
    WorkspaceCreateRequest,
    WorkspaceSensitiveSettingsReplaceRequest,
    WorkspaceUpdateRequest,
)


def _create_request(**overrides: object) -> WorkspaceCreateRequest:
    payload: dict[str, object] = {
        "name": "workspace",
        "runtime": "workspace-runtime:latest",
    }
    payload.update(overrides)
    return WorkspaceCreateRequest.model_validate(payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("key", "error_type"),
    [
        ("AILERON_RUNTIME_INSTANCE_ID", "WORKSPACE_ENV_RESERVED"),
        ("AILERON_PUBLISH_GITLAB_TOKEN", "WORKSPACE_ENV_RESERVED"),
        ("HOME", "WORKSPACE_ENV_RESERVED"),
        ("PATH", "WORKSPACE_ENV_RESERVED"),
        ("CODEX_HOME", "WORKSPACE_ENV_RESERVED"),
        ("XDG_STATE_HOME", "WORKSPACE_ENV_RESERVED"),
        ("NPM_CONFIG_PREFIX", "WORKSPACE_ENV_RESERVED"),
        ("UV_CACHE_DIR", "WORKSPACE_ENV_RESERVED"),
        ("invalid-name", "WORKSPACE_ENV_NAME_INVALID"),
    ],
)
def test_workspace_sensitive_settings_rejects_platform_or_invalid_env_keys(
    key: str,
    error_type: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceSensitiveSettingsReplaceRequest.model_validate(
            {"envVars": [{"key": key, "value": "value"}]}
        )

    assert exc_info.value.errors()[0]["type"] == error_type


@pytest.mark.unit
def test_workspace_sensitive_settings_rejects_duplicate_env_keys() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceSensitiveSettingsReplaceRequest.model_validate(
            {
                "envVars": [
                    {"key": "CUSTOM_VALUE", "value": "first"},
                    {"key": "CUSTOM_VALUE", "value": "second"},
                ]
            }
        )

    assert exc_info.value.errors()[0]["type"] == "WORKSPACE_ENV_DUPLICATE"


@pytest.mark.unit
def test_workspace_sensitive_settings_accepts_unique_user_owned_env_keys() -> None:
    request = WorkspaceSensitiveSettingsReplaceRequest.model_validate(
        {
            "envVars": [
                {"key": "CUSTOM_VALUE", "value": ""},
                {"key": "FEATURE_FLAG", "value": "enabled"},
            ]
        }
    )

    assert [item.key for item in request.env_vars or []] == [
        "CUSTOM_VALUE",
        "FEATURE_FLAG",
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        {"setupScript": "printf 'before\x00after'"},
        {"setupScript": "x" * (SETUP_SCRIPT_MAX_BYTES + 1)},
    ],
)
def test_workspace_sensitive_settings_rejects_unsafe_setup_script(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        WorkspaceSensitiveSettingsReplaceRequest.model_validate(payload)


@pytest.mark.unit
def test_workspace_sensitive_settings_accepts_setup_script_at_byte_limit() -> None:
    request = WorkspaceSensitiveSettingsReplaceRequest.model_validate(
        {"setupScript": "x" * SETUP_SCRIPT_MAX_BYTES}
    )

    assert request.setup_script is not None
    assert len(request.setup_script.encode("utf-8")) == SETUP_SCRIPT_MAX_BYTES


@pytest.mark.unit
@pytest.mark.parametrize("model", [WorkspaceCreateRequest, WorkspaceUpdateRequest])
def test_general_workspace_requests_reject_sensitive_settings(model: type) -> None:
    payload = {"envVars": [{"key": "CUSTOM_VALUE", "value": "secret"}]}
    if model is WorkspaceCreateRequest:
        payload.update({"name": "workspace", "runtime": "workspace-runtime:latest"})

    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(payload)

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.unit
@pytest.mark.parametrize("field", ["gitUrl", "branch"])
def test_workspace_create_rejects_git_bootstrap_fields(field: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _create_request(**{field: "https://example.invalid/repository.git"})

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.unit
@pytest.mark.parametrize("field", ["gitUrl", "branch"])
def test_workspace_update_rejects_git_repository_fields(field: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceUpdateRequest.model_validate(
            {field: "https://example.invalid/repository.git"}
        )

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.unit
def test_firewall_rule_normalizes_domains() -> None:
    rule = FirewallRuleConfig(
        egressMode="allowlist",
        allowedDomains=[" GitHub.COM. ", "台灣.台灣"],
    )

    assert rule.allowed_domains == ["github.com", "xn--kpry57d.xn--kpry57d"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "domain",
    [
        "",
        "*.example.com",
        "https://example.com",
        "example.com/path",
        "example.com:443",
        "127.0.0.1",
        "10.0.0.0/8",
        "bad..example.com",
        "-bad.example.com",
    ],
)
def test_firewall_rule_rejects_invalid_domains(domain: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        FirewallRuleConfig(
            egressMode="allowlist",
            allowedDomains=[domain],
        )

    assert exc_info.value.errors()[0]["type"] == "FIREWALL_DOMAIN_INVALID"


@pytest.mark.unit
def test_firewall_rule_rejects_normalized_duplicates() -> None:
    with pytest.raises(ValidationError) as exc_info:
        FirewallRuleConfig(
            egressMode="allowlist",
            allowedDomains=["GitHub.com", "github.com."],
        )

    assert exc_info.value.errors()[0]["type"] == "FIREWALL_DOMAIN_DUPLICATE"


@pytest.mark.unit
def test_firewall_rule_rejects_removed_effective_domains_field() -> None:
    with pytest.raises(ValidationError):
        FirewallRuleConfig.model_validate(
            {
                "egressMode": "unrestricted",
                "allowedDomains": [],
                "effectiveAllowedDomains": ["platform.example.com"],
            }
        )


@pytest.mark.unit
def test_firewall_rule_requires_non_empty_allowlist() -> None:
    with pytest.raises(ValidationError) as exc_info:
        FirewallRuleConfig(egressMode="allowlist", allowedDomains=[])

    assert exc_info.value.errors()[0]["type"] == "FIREWALL_ALLOWLIST_EMPTY"


@pytest.mark.unit
@pytest.mark.parametrize("egress_mode", ["blocked", "unrestricted"])
def test_firewall_rule_rejects_domains_outside_allowlist(egress_mode: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        FirewallRuleConfig(
            egressMode=egress_mode,
            allowedDomains=["example.com"],
        )

    assert exc_info.value.errors()[0]["type"] == "FIREWALL_DOMAINS_NOT_ALLOWED"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("removed_field", "removed_value"),
    [
        ("networkAccessEnabled", True),
        ("domainAccessMode", "all"),
    ],
)
def test_firewall_rule_rejects_removed_egress_fields(
    removed_field: str,
    removed_value: object,
) -> None:
    with pytest.raises(ValidationError):
        FirewallRuleConfig.model_validate(
            {
                "egressMode": "unrestricted",
                "allowedDomains": [],
                removed_field: removed_value,
            }
        )
