#!/usr/bin/env python3
"""Expose one typed, fail-closed HomeLab deployment lifecycle facade."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TextIO
from urllib.parse import urlsplit

try:
    from scripts.deploy.rke2 import homelab_execution as HOMELAB_EXECUTION
    from scripts.deploy.rke2 import installation_state as INSTALLATION_STATE
    from scripts.deploy.rke2 import private_input as PRIVATE_INPUT
except ModuleNotFoundError as exc:  # Direct script execution from deployment host.
    if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
        raise
    import homelab_execution as HOMELAB_EXECUTION  # type: ignore[no-redef]
    import installation_state as INSTALLATION_STATE  # type: ignore[no-redef]
    import private_input as PRIVATE_INPUT  # type: ignore[no-redef]

__all__ = [
    "AcceptanceLoginDriver",
    "ExecutionDisposition",
    "ExecutionPort",
    "ExecutionPortError",
    "ExecutionReceipt",
    "ExecutionRequest",
    "ExecutionStep",
    "HomelabProfile",
    "SourceInspector",
    "SourceSnapshot",
    "StagedInput",
    "main",
]

PROFILE_SCHEMA = "aileron-homelab-profile/v1"
STAGED_PROFILE_SCHEMA = "aileron-homelab-staged-profile/v1"
PLAN_SCHEMA = "aileron-homelab-run-plan/v1"
JOURNAL_SCHEMA = "aileron-homelab-run-journal/v1"
INSTALLATION_INTENT = "newInstallation"
GLOBAL_EXECUTION_LOCK_NAME = ".apply.lock"
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_PATTERN = re.compile(r"^run-[0-9a-f]{32}$")
PROFILE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,61}[a-z0-9])?$")
CONTEXT_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,252})$")
ERROR_CODE_PATTERN = re.compile(r"^[a-z][A-Za-z0-9]{0,63}$")
PORT_PATTERN_TEXT = (
    r"(?:[1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|"
    r"65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"
)
LOWERCASE_HOST_LABEL_PATTERN_TEXT = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
PUBLIC_HOST_LABEL_PATTERN_TEXT = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
REGISTRY_HOST_PATTERN = re.compile(
    rf"^{LOWERCASE_HOST_LABEL_PATTERN_TEXT}"
    rf"(?:\.{LOWERCASE_HOST_LABEL_PATTERN_TEXT})*"
    rf"(?::({PORT_PATTERN_TEXT}))?$"
)
REGISTRY_PROJECT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
PLATFORM_URL_PATTERN = re.compile(
    rf"^https://(?:\[[0-9A-Fa-f:]+\]|{PUBLIC_HOST_LABEL_PATTERN_TEXT}"
    rf"(?:\.{PUBLIC_HOST_LABEL_PATTERN_TEXT})*)(?::({PORT_PATTERN_TEXT}))?$"
)
TURN_HOST_PATTERN_TEXT = (
    r"(?:\[[0-9A-Fa-f:]+\]|" r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)"
)
TURN_URL_PATTERN = re.compile(
    rf"^(?:turn|turns):{TURN_HOST_PATTERN_TEXT}"
    rf"(?::({PORT_PATTERN_TEXT}))?(?:\?transport=(?:udp|tcp))?$"
)
PROFILE_MAXIMUM_BYTES = 64 * 1024
PRIVATE_INPUT_KEYS = (
    "kubeconfig",
    "backendExecutionProfile",
    "harborDockerconfig",
    "registryCa",
    "appsTlsCertificate",
    "appsTlsPrivateKey",
    "appsTlsCa",
    "oidcCa",
    "identityTlsCertificate",
    "identityTlsPrivateKey",
    "externalOidcClientSecret",
    "oidcLoginUsername",
    "oidcLoginPassword",
    "coreDataServiceValues",
    "identityDataServiceValues",
    "platformDatabaseUrl",
    "platformDatabaseCa",
    "redisGeneralUrl",
    "redisJobQueueUrl",
    "redisJobResultUrl",
    "redisGeneralCa",
    "redisJobQueueCa",
    "redisJobResultCa",
    "identityDatabaseUsername",
    "identityDatabasePassword",
    "identityDatabaseCa",
)
INPUT_SNAPSHOT_PATHS = {
    "kubeconfigRaw": "inputs/kubeconfig.raw",
    "kubeconfig": "inputs/kubeconfig",
    "backendExecutionProfile": "inputs/backend-execution-profile.json",
    "harborDockerconfig": "inputs/docker/config.json",
    "registryCa": "inputs/registry-ca.crt",
    "appsTlsCertificate": "inputs/apps-tls.crt",
    "appsTlsPrivateKey": "inputs/apps-tls.key",
    "appsTlsCa": "inputs/apps-ca.crt",
    "oidcCa": "inputs/oidc-ca.crt",
    "identityTlsCertificate": "inputs/identity-tls.crt",
    "identityTlsPrivateKey": "inputs/identity-tls.key",
    "externalOidcClientSecret": "inputs/external-oidc-client-secret",
    "oidcLoginUsername": "inputs/oidc-login-username",
    "oidcLoginPassword": "inputs/oidc-login-password",
    "coreDataServiceValues": "inputs/core-data-service-values.yaml",
    "identityDataServiceValues": "inputs/identity-data-service-values.yaml",
    "platformDatabaseUrl": "inputs/platform-database-url",
    "platformDatabaseCa": "inputs/platform-database-ca.crt",
    "redisGeneralUrl": "inputs/redis-general-url",
    "redisJobQueueUrl": "inputs/redis-job-queue-url",
    "redisJobResultUrl": "inputs/redis-job-result-url",
    "redisGeneralCa": "inputs/redis-general-ca.crt",
    "redisJobQueueCa": "inputs/redis-job-queue-ca.crt",
    "redisJobResultCa": "inputs/redis-job-result-ca.crt",
    "identityDatabaseUsername": "inputs/identity-database-username",
    "identityDatabasePassword": "inputs/identity-database-password",
    "identityDatabaseCa": "inputs/identity-database-ca.crt",
}
INPUT_SNAPSHOT_DIRECTORIES = ("inputs/docker", "inputs")
BASE_INPUT_NAMES = (
    "kubeconfigRaw",
    "kubeconfig",
    "backendExecutionProfile",
    "harborDockerconfig",
    "registryCa",
    "appsTlsCertificate",
    "appsTlsPrivateKey",
    "appsTlsCa",
    "oidcCa",
)
EXECUTION_INPUT_NAMES = frozenset(INPUT_SNAPSHOT_PATHS) - {"kubeconfigRaw"}
CORE_POSTGRES_INPUT_NAMES = {"platformDatabaseUrl", "platformDatabaseCa"}
CORE_REDIS_INPUT_NAMES = {
    "redisGeneralUrl",
    "redisJobQueueUrl",
    "redisJobResultUrl",
    "redisGeneralCa",
    "redisJobQueueCa",
    "redisJobResultCa",
}
IDENTITY_DATABASE_INPUT_NAMES = {
    "identityDatabaseUsername",
    "identityDatabasePassword",
    "identityDatabaseCa",
}
DATA_SERVICE_INPUT_NAMES = (
    "coreDataServiceValues",
    "identityDataServiceValues",
    "platformDatabaseUrl",
    "platformDatabaseCa",
    "redisGeneralUrl",
    "redisJobQueueUrl",
    "redisJobResultUrl",
    "redisGeneralCa",
    "redisJobQueueCa",
    "redisJobResultCa",
    "identityDatabaseUsername",
    "identityDatabasePassword",
    "identityDatabaseCa",
)


class ExecutionStep(str, Enum):
    """Code-owned HomeLab workflow steps exposed to one execution adapter."""

    NEW_INSTALLATION = "newInstallation"
    RELEASE_PREPARATION = "releasePreparation"
    RESET = "reset"
    INSTALL = "install"
    ACCEPTANCE = "acceptance"


STEP_SEQUENCE = (
    ExecutionStep.NEW_INSTALLATION,
    ExecutionStep.RELEASE_PREPARATION,
    ExecutionStep.RESET,
    ExecutionStep.INSTALL,
    ExecutionStep.ACCEPTANCE,
)


class ExecutionDisposition(str, Enum):
    """Typed adapter result understood by the lifecycle journal."""

    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaitingApproval"


@dataclass(frozen=True)
class AcceptanceLoginDriver:
    """Immutable browser-login contract selected by the identity mode."""

    kind: str
    username_selector: str | None
    password_selector: str | None
    submit_selector: str | None
    error_selector: str | None

    def __post_init__(self) -> None:
        selectors = (
            self.username_selector,
            self.password_selector,
            self.submit_selector,
            self.error_selector,
        )
        if self.kind == "keycloak" and all(selector is None for selector in selectors):
            return
        if self.kind == "form" and all(
            isinstance(selector, str)
            and 1 <= len(selector) <= 256
            and selector == selector.strip()
            and not any(
                ord(character) < 32 or ord(character) == 127 for character in selector
            )
            for selector in selectors
        ):
            return
        raise _LifecycleError("profileAcceptanceInvalid", 65)

    @classmethod
    def from_document(
        cls,
        document: Any,
        *,
        identity_mode: str,
    ) -> AcceptanceLoginDriver:
        if identity_mode == "bundledKeycloak":
            if not isinstance(document, dict) or document != {"kind": "keycloak"}:
                raise _LifecycleError("profileAcceptanceInvalid", 65)
            return cls(
                kind="keycloak",
                username_selector=None,
                password_selector=None,
                submit_selector=None,
                error_selector=None,
            )
        expected = {
            "kind",
            "usernameSelector",
            "passwordSelector",
            "submitSelector",
            "errorSelector",
        }
        if (
            identity_mode != "externalOidc"
            or not isinstance(document, dict)
            or set(document) != expected
            or document.get("kind") != "form"
        ):
            raise _LifecycleError("profileAcceptanceInvalid", 65)
        selectors = tuple(
            document.get(key)
            for key in (
                "usernameSelector",
                "passwordSelector",
                "submitSelector",
                "errorSelector",
            )
        )
        username, password, submit, error = selectors
        return cls(
            kind="form",
            username_selector=username,
            password_selector=password,
            submit_selector=submit,
            error_selector=error,
        )

    def to_document(self) -> dict[str, str]:
        if self.kind == "keycloak":
            return {"kind": "keycloak"}
        assert self.username_selector is not None
        assert self.password_selector is not None
        assert self.submit_selector is not None
        assert self.error_selector is not None
        return {
            "kind": "form",
            "usernameSelector": self.username_selector,
            "passwordSelector": self.password_selector,
            "submitSelector": self.submit_selector,
            "errorSelector": self.error_selector,
        }


def _exact_text(value: Any, code: str, *, maximum_length: int = 2048) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum_length
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise _LifecycleError(code, 65)
    return value


def _platform_origin(value: Any) -> str:
    origin = _exact_text(value, "profileEndpointsInvalid")
    if PLATFORM_URL_PATTERN.fullmatch(origin) is None:
        raise _LifecycleError("profileEndpointsInvalid", 65)
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise _LifecycleError("profileEndpointsInvalid", 65) from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or (port is not None and not 1 <= port <= 65535)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.netloc.endswith(":")
        or "*" in parsed.hostname
    ):
        raise _LifecycleError("profileEndpointsInvalid", 65)
    return origin


def _admin_console_url(value: Any) -> str:
    console_url = _exact_text(value, "profileIdentityInvalid")
    if any(character.isspace() or character == "\\" for character in console_url):
        raise _LifecycleError("profileIdentityInvalid", 65)
    try:
        parsed = urlsplit(console_url)
        port = parsed.port
    except ValueError as exc:
        raise _LifecycleError("profileIdentityInvalid", 65) from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or (port is not None and not 1 <= port <= 65535)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.netloc.endswith(":")
        or "*" in parsed.hostname
    ):
        raise _LifecycleError("profileIdentityInvalid", 65)
    return console_url


def _turn_url(value: Any) -> str:
    turn_url = _exact_text(value, "profileEndpointsInvalid")
    match = TURN_URL_PATTERN.fullmatch(turn_url)
    if match is None:
        raise _LifecycleError("profileEndpointsInvalid", 65)
    port = match.group(1)
    if port is not None and not 1 <= int(port) <= 65535:
        raise _LifecycleError("profileEndpointsInvalid", 65)
    return turn_url


@dataclass(frozen=True)
class HomelabProfile:
    """Complete non-secret deployment configuration staged into a run."""

    profile_id: str
    context: str
    registry_host: str
    registry_project: str
    platform_url: str
    turn_url: str
    identity_mode: str
    issuer_url: str
    admin_console_url: str | None
    client_id: str
    acceptance_login_mode: str
    acceptance_login_driver: AcceptanceLoginDriver
    installation_intent: str = INSTALLATION_INTENT

    @classmethod
    def from_document(cls, document: Any) -> HomelabProfile:
        if not isinstance(document, dict) or set(document) != {
            "schemaVersion",
            "profileId",
            "context",
            "registry",
            "endpoints",
            "identity",
            "acceptance",
            "installationIntent",
        }:
            raise _LifecycleError("stagedProfileShapeInvalid", 65)
        registry = document.get("registry")
        endpoints = document.get("endpoints")
        identity = document.get("identity")
        acceptance = document.get("acceptance")
        if not isinstance(registry, dict) or set(registry) != {"host", "project"}:
            raise _LifecycleError("profileRegistryInvalid", 65)
        if not isinstance(endpoints, dict) or set(endpoints) != {
            "platformUrl",
            "turnUrl",
        }:
            raise _LifecycleError("profileEndpointsInvalid", 65)
        if not isinstance(identity, dict):
            raise _LifecycleError("profileIdentityInvalid", 65)
        if not isinstance(acceptance, dict) or set(acceptance) != {
            "loginMode",
            "loginDriver",
        }:
            raise _LifecycleError("profileAcceptanceInvalid", 65)
        if document.get("schemaVersion") != STAGED_PROFILE_SCHEMA:
            raise _LifecycleError("stagedProfileSchemaInvalid", 65)
        if document.get("installationIntent") != INSTALLATION_INTENT:
            raise _LifecycleError("installationIntentInvalid", 65)

        profile_id = document.get("profileId")
        context = document.get("context")
        registry_host = _exact_text(
            registry.get("host"), "profileRegistryInvalid", maximum_length=253
        )
        registry_project = _exact_text(
            registry.get("project"), "profileRegistryInvalid", maximum_length=253
        )
        if (
            REGISTRY_HOST_PATTERN.fullmatch(registry_host) is None
            or REGISTRY_PROJECT_PATTERN.fullmatch(registry_project) is None
        ):
            raise _LifecycleError("profileRegistryInvalid", 65)
        platform_url = _platform_origin(endpoints.get("platformUrl"))
        turn_url = _turn_url(endpoints.get("turnUrl"))
        mode = identity.get("mode")
        issuer_url = identity.get("issuerUrl")
        admin_console_url = identity.get("adminConsoleUrl")
        client_id = identity.get("clientId")
        login_mode = acceptance.get("loginMode")
        if (
            not isinstance(profile_id, str)
            or PROFILE_ID_PATTERN.fullmatch(profile_id) is None
        ):
            raise _LifecycleError("profileIdInvalid", 65)
        if not isinstance(context, str) or CONTEXT_PATTERN.fullmatch(context) is None:
            raise _LifecycleError("contextInvalid", 65)
        try:
            INSTALLATION_STATE.validate_identity_selection(
                identity_mode=mode,
                issuer_url=issuer_url,
                client_id=client_id,
            )
        except INSTALLATION_STATE.InstallationStateContractError as exc:
            raise _LifecycleError("profileIdentityInvalid", 65) from exc
        if mode == "bundledKeycloak":
            if set(identity) != {
                "mode",
                "issuerUrl",
                "adminConsoleUrl",
                "clientId",
            }:
                raise _LifecycleError("profileIdentityInvalid", 65)
            admin_console_url = _admin_console_url(admin_console_url)
        elif set(identity) != {"mode", "issuerUrl", "clientId"}:
            raise _LifecycleError("profileIdentityInvalid", 65)
        else:
            admin_console_url = None
        if login_mode not in {"breakGlass", "files"}:
            raise _LifecycleError("profileAcceptanceInvalid", 65)
        if login_mode == "breakGlass" and mode != "bundledKeycloak":
            raise _LifecycleError("profileAcceptanceInvalid", 65)
        login_driver = AcceptanceLoginDriver.from_document(
            acceptance.get("loginDriver"),
            identity_mode=mode,
        )
        return cls(
            profile_id=profile_id,
            context=context,
            registry_host=registry_host,
            registry_project=registry_project,
            platform_url=platform_url,
            turn_url=turn_url,
            identity_mode=mode,
            issuer_url=issuer_url,
            admin_console_url=admin_console_url,
            client_id=client_id,
            acceptance_login_mode=login_mode,
            acceptance_login_driver=login_driver,
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "schemaVersion": STAGED_PROFILE_SCHEMA,
            "profileId": self.profile_id,
            "context": self.context,
            "registry": {
                "host": self.registry_host,
                "project": self.registry_project,
            },
            "endpoints": {
                "platformUrl": self.platform_url,
                "turnUrl": self.turn_url,
            },
            "identity": {
                "mode": self.identity_mode,
                "issuerUrl": self.issuer_url,
                **(
                    {"adminConsoleUrl": self.admin_console_url}
                    if self.admin_console_url is not None
                    else {}
                ),
                "clientId": self.client_id,
            },
            "acceptance": {
                "loginMode": self.acceptance_login_mode,
                "loginDriver": self.acceptance_login_driver.to_document(),
            },
            "installationIntent": self.installation_intent,
        }


@dataclass(frozen=True)
class _SourceProfile:
    profile: HomelabProfile
    private_inputs: dict[str, Path | None]

    @classmethod
    def from_document(cls, document: Any) -> _SourceProfile:
        if not isinstance(document, dict) or set(document) != {
            "schemaVersion",
            "profileId",
            "context",
            "registry",
            "endpoints",
            "identity",
            "acceptance",
            "privateInputs",
            "installationIntent",
        }:
            raise _LifecycleError("profileShapeInvalid", 65)
        if document.get("schemaVersion") != PROFILE_SCHEMA:
            raise _LifecycleError("profileSchemaInvalid", 65)
        raw_inputs = document.get("privateInputs")
        if not isinstance(raw_inputs, dict) or set(raw_inputs) != set(
            PRIVATE_INPUT_KEYS
        ):
            raise _LifecycleError("profilePrivateInputsInvalid", 65)
        staged_document = {
            key: value for key, value in document.items() if key != "privateInputs"
        }
        staged_document["schemaVersion"] = STAGED_PROFILE_SCHEMA
        profile = HomelabProfile.from_document(staged_document)
        private_inputs: dict[str, Path | None] = {}
        for name in PRIVATE_INPUT_KEYS:
            value = raw_inputs[name]
            if value is None:
                private_inputs[name] = None
                continue
            path = Path(
                _exact_text(
                    value,
                    "profilePrivateInputsInvalid",
                    maximum_length=4096,
                )
            )
            if not path.is_absolute():
                raise _LifecycleError("profilePrivateInputsInvalid", 65)
            private_inputs[name] = path
        cls._validate_mode_inputs(profile, private_inputs)
        return cls(profile=profile, private_inputs=private_inputs)

    @staticmethod
    def _validate_mode_inputs(
        profile: HomelabProfile, inputs: dict[str, Path | None]
    ) -> None:
        required = {
            "kubeconfig",
            "backendExecutionProfile",
            "harborDockerconfig",
            "registryCa",
            "appsTlsCertificate",
            "appsTlsPrivateKey",
            "appsTlsCa",
            "oidcCa",
        }
        if profile.identity_mode == "bundledKeycloak":
            required.update({"identityTlsCertificate", "identityTlsPrivateKey"})
            forbidden = {"externalOidcClientSecret"}
        else:
            required.add("externalOidcClientSecret")
            forbidden = {"identityTlsCertificate", "identityTlsPrivateKey"}
        if profile.acceptance_login_mode == "files":
            required.update({"oidcLoginUsername", "oidcLoginPassword"})
        else:
            forbidden.update({"oidcLoginUsername", "oidcLoginPassword"})
        core_optional = CORE_POSTGRES_INPUT_NAMES | CORE_REDIS_INPUT_NAMES
        if inputs["coreDataServiceValues"] is None:
            forbidden.update(core_optional)
        if profile.identity_mode != "bundledKeycloak":
            forbidden.update(
                {"identityDataServiceValues"} | IDENTITY_DATABASE_INPUT_NAMES
            )
        elif inputs["identityDataServiceValues"] is None:
            forbidden.update(IDENTITY_DATABASE_INPUT_NAMES)
        for group in (
            CORE_POSTGRES_INPUT_NAMES,
            CORE_REDIS_INPUT_NAMES,
            IDENTITY_DATABASE_INPUT_NAMES,
        ):
            present = {name for name in group if inputs[name] is not None}
            if present and present != group:
                raise _LifecycleError("profilePrivateInputModeInvalid", 65)
        if any(inputs[name] is None for name in required) or any(
            inputs[name] is not None for name in forbidden
        ):
            raise _LifecycleError("profilePrivateInputModeInvalid", 65)


@dataclass(frozen=True)
class StagedInput:
    """One canonical run-scoped private input exposed to an execution adapter."""

    name: str
    path: Path
    digest: str


@dataclass(frozen=True)
class ExecutionRequest:
    """One resumable, code-owned workflow step."""

    run_id: str
    plan_digest: str
    approval_digest: str
    commit: str
    step: ExecutionStep
    attempt: int
    profile: HomelabProfile
    inputs: tuple[StagedInput, ...]


@dataclass(frozen=True)
class ExecutionReceipt:
    """Non-secret durable result returned by an execution adapter."""

    step: ExecutionStep
    disposition: ExecutionDisposition
    digest: str


class ExecutionPortError(RuntimeError):
    """Report a safe execution failure code without leaking adapter output."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or ERROR_CODE_PATTERN.fullmatch(code) is None:
            code = "executionFailed"
        self.code = code
        super().__init__(code)


class ExecutionPort(Protocol):
    """The only mutation seam used by the HomeLab lifecycle facade."""

    def execute(self, request: ExecutionRequest) -> ExecutionReceipt:
        """Execute one idempotent workflow step and return its receipt."""


@dataclass(frozen=True)
class SourceSnapshot:
    """Read-only identity of the source checkout staged into a run."""

    head_commit: str
    clean: bool


class SourceInspector(Protocol):
    """Read the exact current checkout identity without mutating it."""

    def inspect(self) -> SourceSnapshot:
        """Return the current HEAD and whether tracked/untracked state is clean."""


def _expected_input_names(
    profile: HomelabProfile,
    present_names: set[str] | None = None,
) -> tuple[str, ...]:
    names = list(BASE_INPUT_NAMES)
    if profile.identity_mode == "bundledKeycloak":
        names.extend(("identityTlsCertificate", "identityTlsPrivateKey"))
    else:
        names.append("externalOidcClientSecret")
    if profile.acceptance_login_mode == "files":
        names.extend(("oidcLoginUsername", "oidcLoginPassword"))
    if present_names is not None:
        allowed = set(names) | set(DATA_SERVICE_INPUT_NAMES)
        if not set(names).issubset(present_names) or not present_names.issubset(
            allowed
        ):
            raise _LifecycleError("planPrivateInputsInvalid", 65)
        for group in (
            CORE_POSTGRES_INPUT_NAMES,
            CORE_REDIS_INPUT_NAMES,
            IDENTITY_DATABASE_INPUT_NAMES,
        ):
            present = group & present_names
            if present and present != group:
                raise _LifecycleError("planPrivateInputsInvalid", 65)
        if (
            (
                (CORE_POSTGRES_INPUT_NAMES | CORE_REDIS_INPUT_NAMES) & present_names
                and "coreDataServiceValues" not in present_names
            )
            or (
                IDENTITY_DATABASE_INPUT_NAMES & present_names
                and "identityDataServiceValues" not in present_names
            )
            or (
                profile.identity_mode != "bundledKeycloak"
                and ({"identityDataServiceValues"} | IDENTITY_DATABASE_INPUT_NAMES)
                & present_names
            )
        ):
            raise _LifecycleError("planPrivateInputsInvalid", 65)
        names.extend(name for name in DATA_SERVICE_INPUT_NAMES if name in present_names)
    return tuple(names)


@dataclass(frozen=True)
class _InputRecord:
    name: str
    snapshot: str
    digest: str
    size_bytes: int

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "snapshot": self.snapshot,
            "sha256": self.digest,
            "sizeBytes": self.size_bytes,
        }

    @classmethod
    def from_document(cls, document: Any, *, expected_name: str) -> _InputRecord:
        if not isinstance(document, dict) or set(document) != {
            "name",
            "snapshot",
            "sha256",
            "sizeBytes",
        }:
            raise _LifecycleError("planPrivateInputShapeInvalid", 65)
        digest = document.get("sha256")
        size_bytes = document.get("sizeBytes")
        if (
            document.get("name") != expected_name
            or document.get("snapshot") != INPUT_SNAPSHOT_PATHS[expected_name]
            or not isinstance(digest, str)
            or DIGEST_PATTERN.fullmatch(digest) is None
            or isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
        ):
            raise _LifecycleError("planPrivateInputInvalid", 65)
        return cls(
            name=expected_name,
            snapshot=INPUT_SNAPSHOT_PATHS[expected_name],
            digest=digest,
            size_bytes=size_bytes,
        )


@dataclass(frozen=True)
class _RunPlan:
    run_id: str
    commit: str
    profile: HomelabProfile
    source_profile_digest: str
    private_inputs: tuple[_InputRecord, ...]
    steps: tuple[ExecutionStep, ...] = STEP_SEQUENCE

    def to_document(self) -> dict[str, Any]:
        return {
            "schemaVersion": PLAN_SCHEMA,
            "runId": self.run_id,
            "commit": self.commit,
            "profile": self.profile.to_document(),
            "sourceProfileSha256": self.source_profile_digest,
            "privateInputs": [item.to_document() for item in self.private_inputs],
            "steps": [step.value for step in self.steps],
        }

    @classmethod
    def from_document(cls, document: Any) -> _RunPlan:
        if not isinstance(document, dict) or set(document) != {
            "schemaVersion",
            "runId",
            "commit",
            "profile",
            "sourceProfileSha256",
            "privateInputs",
            "steps",
        }:
            raise _LifecycleError("planShapeInvalid", 65)
        run_id = document.get("runId")
        commit = document.get("commit")
        profile_digest = document.get("sourceProfileSha256")
        if document.get("schemaVersion") != PLAN_SCHEMA:
            raise _LifecycleError("planSchemaInvalid", 65)
        if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise _LifecycleError("planRunIdInvalid", 65)
        if not isinstance(commit, str) or FULL_SHA_PATTERN.fullmatch(commit) is None:
            raise _LifecycleError("planCommitInvalid", 65)
        if (
            not isinstance(profile_digest, str)
            or DIGEST_PATTERN.fullmatch(profile_digest) is None
        ):
            raise _LifecycleError("planSourceProfileDigestInvalid", 65)
        if document.get("steps") != [step.value for step in STEP_SEQUENCE]:
            raise _LifecycleError("planStepsInvalid", 65)
        profile = HomelabProfile.from_document(document.get("profile"))
        raw_inputs = document.get("privateInputs")
        raw_names = (
            {
                item.get("name")
                for item in raw_inputs
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            if isinstance(raw_inputs, list)
            else set()
        )
        expected_inputs = _expected_input_names(profile, raw_names)
        if not isinstance(raw_inputs, list) or len(raw_inputs) != len(expected_inputs):
            raise _LifecycleError("planPrivateInputsInvalid", 65)
        private_inputs = tuple(
            _InputRecord.from_document(raw, expected_name=expected)
            for raw, expected in zip(raw_inputs, expected_inputs)
        )
        return cls(
            run_id=run_id,
            commit=commit,
            profile=profile,
            source_profile_digest=profile_digest,
            private_inputs=private_inputs,
        )


@dataclass(frozen=True)
class _JournalStep:
    step: ExecutionStep
    status: str = "pending"
    attempts: int = 0
    receipt_digest: str | None = None
    last_error_code: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.step.value,
            "status": self.status,
            "attempts": self.attempts,
            "receiptDigest": self.receipt_digest,
            "lastErrorCode": self.last_error_code,
        }

    @classmethod
    def from_document(
        cls, document: Any, *, expected_step: ExecutionStep
    ) -> _JournalStep:
        if not isinstance(document, dict) or set(document) != {
            "id",
            "status",
            "attempts",
            "receiptDigest",
            "lastErrorCode",
        }:
            raise _LifecycleError("journalStepShapeInvalid", 65)
        status = document.get("status")
        attempts = document.get("attempts")
        receipt = document.get("receiptDigest")
        error = document.get("lastErrorCode")
        if document.get("id") != expected_step.value:
            raise _LifecycleError("journalStepOrderInvalid", 65)
        if status not in {"pending", "started", "awaitingApproval", "completed"}:
            raise _LifecycleError("journalStepStatusInvalid", 65)
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
            raise _LifecycleError("journalStepAttemptsInvalid", 65)
        if receipt is not None and (
            not isinstance(receipt, str) or DIGEST_PATTERN.fullmatch(receipt) is None
        ):
            raise _LifecycleError("journalStepReceiptInvalid", 65)
        if error is not None and (
            not isinstance(error, str) or ERROR_CODE_PATTERN.fullmatch(error) is None
        ):
            raise _LifecycleError("journalStepErrorInvalid", 65)
        if status == "pending" and (
            attempts != 0 or receipt is not None or error is not None
        ):
            raise _LifecycleError("journalPendingStepInvalid", 65)
        if status == "started" and (attempts == 0 or receipt is not None):
            raise _LifecycleError("journalStartedStepInvalid", 65)
        if status in {"awaitingApproval", "completed"} and (
            attempts == 0 or receipt is None or error is not None
        ):
            raise _LifecycleError("journalFinishedStepInvalid", 65)
        return cls(
            step=expected_step,
            status=status,
            attempts=attempts,
            receipt_digest=receipt,
            last_error_code=error,
        )


@dataclass(frozen=True)
class _RunJournal:
    run_id: str
    plan_digest: str
    phase: str
    required_approval_digest: str | None
    last_approved_digest: str | None
    revision: int
    steps: tuple[_JournalStep, ...]

    @classmethod
    def staged(cls, *, run_id: str, plan_digest: str) -> _RunJournal:
        return cls(
            run_id=run_id,
            plan_digest=plan_digest,
            phase="staged",
            required_approval_digest=plan_digest,
            last_approved_digest=None,
            revision=0,
            steps=tuple(_JournalStep(step=step) for step in STEP_SEQUENCE),
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "schemaVersion": JOURNAL_SCHEMA,
            "runId": self.run_id,
            "planDigest": self.plan_digest,
            "phase": self.phase,
            "requiredApprovalDigest": self.required_approval_digest,
            "lastApprovedDigest": self.last_approved_digest,
            "revision": self.revision,
            "steps": [step.to_document() for step in self.steps],
        }

    @classmethod
    def from_document(cls, document: Any) -> _RunJournal:
        if not isinstance(document, dict) or set(document) != {
            "schemaVersion",
            "runId",
            "planDigest",
            "phase",
            "requiredApprovalDigest",
            "lastApprovedDigest",
            "revision",
            "steps",
        }:
            raise _LifecycleError("journalShapeInvalid", 65)
        run_id = document.get("runId")
        plan_digest = document.get("planDigest")
        phase = document.get("phase")
        required = document.get("requiredApprovalDigest")
        last_approved = document.get("lastApprovedDigest")
        revision = document.get("revision")
        raw_steps = document.get("steps")
        if document.get("schemaVersion") != JOURNAL_SCHEMA:
            raise _LifecycleError("journalSchemaInvalid", 65)
        if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise _LifecycleError("journalRunIdInvalid", 65)
        if (
            not isinstance(plan_digest, str)
            or DIGEST_PATTERN.fullmatch(plan_digest) is None
        ):
            raise _LifecycleError("journalPlanDigestInvalid", 65)
        if phase not in {
            "staged",
            "applying",
            "awaitingApproval",
            "failed",
            "succeeded",
        }:
            raise _LifecycleError("journalPhaseInvalid", 65)
        if required is not None and (
            not isinstance(required, str) or DIGEST_PATTERN.fullmatch(required) is None
        ):
            raise _LifecycleError("journalApprovalDigestInvalid", 65)
        if last_approved is not None and (
            not isinstance(last_approved, str)
            or DIGEST_PATTERN.fullmatch(last_approved) is None
        ):
            raise _LifecycleError("journalLastApprovedDigestInvalid", 65)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise _LifecycleError("journalRevisionInvalid", 65)
        if not isinstance(raw_steps, list) or len(raw_steps) != len(STEP_SEQUENCE):
            raise _LifecycleError("journalStepsInvalid", 65)
        steps = tuple(
            _JournalStep.from_document(raw, expected_step=expected)
            for raw, expected in zip(raw_steps, STEP_SEQUENCE)
        )
        journal = cls(
            run_id=run_id,
            plan_digest=plan_digest,
            phase=phase,
            required_approval_digest=required,
            last_approved_digest=last_approved,
            revision=revision,
            steps=steps,
        )
        journal._validate_progression()
        return journal

    def _validate_progression(self) -> None:
        statuses = [step.status for step in self.steps]
        first_incomplete = next(
            (index for index, status in enumerate(statuses) if status != "completed"),
            len(statuses),
        )
        if any(status == "completed" for status in statuses[first_incomplete + 1 :]):
            raise _LifecycleError("journalProgressionInvalid", 65)
        current = (
            None if first_incomplete == len(statuses) else statuses[first_incomplete]
        )
        if any(status != "pending" for status in statuses[first_incomplete + 1 :]):
            raise _LifecycleError("journalProgressionInvalid", 65)
        valid_current = {
            "staged": {"pending"},
            "applying": {"pending", "started"},
            "awaitingApproval": {"awaitingApproval"},
            "failed": {"started"},
            "succeeded": {None},
        }[self.phase]
        if current not in valid_current:
            raise _LifecycleError("journalProgressionInvalid", 65)
        if self.phase == "staged" and (
            first_incomplete != 0
            or self.last_approved_digest is not None
            or self.required_approval_digest != self.plan_digest
        ):
            raise _LifecycleError("journalStagedStateInvalid", 65)
        if self.phase == "succeeded" and (
            self.required_approval_digest is not None
            or self.last_approved_digest is None
        ):
            raise _LifecycleError("journalSucceededStateInvalid", 65)
        if self.phase not in {"staged", "succeeded"} and (
            self.required_approval_digest is None or self.last_approved_digest is None
        ):
            raise _LifecycleError("journalActiveApprovalInvalid", 65)
        if self.phase in {"applying", "failed"} and (
            self.required_approval_digest != self.last_approved_digest
        ):
            raise _LifecycleError("journalActiveApprovalInvalid", 65)
        if self.phase == "awaitingApproval" and (
            self.required_approval_digest != self.steps[first_incomplete].receipt_digest
            or self.required_approval_digest == self.last_approved_digest
        ):
            raise _LifecycleError("journalCheckpointInvalid", 65)
        if (
            self.phase == "failed"
            and self.steps[first_incomplete].last_error_code is None
        ):
            raise _LifecycleError("journalFailureInvalid", 65)
        if self.phase != "failed" and any(
            step.last_error_code is not None for step in self.steps
        ):
            raise _LifecycleError("journalUnexpectedErrorInvalid", 65)


@dataclass(frozen=True)
class _RunPaths:
    directory: Path

    @property
    def profile(self) -> Path:
        return self.directory / "profile.json"

    @property
    def plan(self) -> Path:
        return self.directory / "plan.json"

    @property
    def journal(self) -> Path:
        return self.directory / "journal.json"

    @property
    def inputs(self) -> Path:
        return self.directory / "inputs"

    def input(self, name: str) -> Path:
        return self.directory / INPUT_SNAPSHOT_PATHS[name]


class _LifecycleError(ValueError):
    def __init__(self, code: str, exit_code: int) -> None:
        self.code = code
        self.exit_code = exit_code
        super().__init__(code)


class _GitSourceInspector:
    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root

    def inspect(self) -> SourceSnapshot:
        head = self._run(["rev-parse", "--verify", "HEAD"]).strip()
        status = self._run(["status", "--porcelain=v1", "--untracked-files=all"])
        return SourceSnapshot(head_commit=head, clean=status == "")

    def _run(self, arguments: list[str]) -> str:
        completed = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(self._repository_root),
                *arguments,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if completed.returncode != 0:
            raise _LifecycleError("sourceInspectionFailed", 74)
        return completed.stdout


def _run_kubeconfig_command(command: list[str], *, environment: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        env={**os.environ, **environment},
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if completed.returncode != 0:
        raise _LifecycleError("kubeconfigFlattenFailed", 74)
    return completed.stdout


def _strict_json(content: bytes, description: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _LifecycleError(f"{description}DuplicateKey", 65)
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        raise _LifecycleError(f"{description}Invalid", 65)

    try:
        return json.loads(
            content.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except _LifecycleError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _LifecycleError(f"{description}Invalid", 65) from exc


def _canonical_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise _LifecycleError("runIdInvalid", 64)


def _private_root(private_root: Path | None) -> Path:
    try:
        return PRIVATE_INPUT.private_root_path(private_root)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("privateRootInvalid", 65) from exc


def _ensure_directory(path: Path, *, private_root: Path) -> Path:
    if not path.exists():
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise _LifecycleError("runStoreUnavailable", 73) from exc
    try:
        return PRIVATE_INPUT.validate_private_directory(
            path,
            "HomeLab run directory",
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("runStoreInvalid", 65) from exc


def _run_store(private_root: Path) -> Path:
    homelab = _ensure_directory(private_root / "homelab", private_root=private_root)
    return _ensure_directory(homelab / "runs", private_root=private_root)


def _global_execution_lock_path(private_root: Path) -> Path:
    return private_root / "homelab" / GLOBAL_EXECUTION_LOCK_NAME


def _ensure_global_execution_lock(private_root: Path) -> Path:
    path = _global_execution_lock_path(private_root)
    created = False
    try:
        path.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        pass
    except OSError as exc:
        raise _LifecycleError("executionLockUnavailable", 73) from exc
    try:
        PRIVATE_INPUT.validate_private_directory(
            path,
            "HomeLab global execution lock",
            private_root=private_root,
        )
        if created:
            descriptor = os.open(
                path.parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("executionLockInvalid", 65) from exc
    except OSError as exc:
        raise _LifecycleError("executionLockUnavailable", 73) from exc
    return path


def _write_snapshot(
    *, path: Path, content: bytes, description: str, private_root: Path
) -> None:
    try:
        PRIVATE_INPUT.write_private_snapshot(
            destination=path,
            content=content,
            description=description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("runStateWriteFailed", 73) from exc


def _discard_staging_directory(paths: _RunPaths) -> None:
    input_paths = tuple(
        paths.directory / relative
        for relative in dict.fromkeys(INPUT_SNAPSHOT_PATHS.values())
    )
    for path in (
        *input_paths,
        paths.journal,
        paths.plan,
        paths.profile,
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return
    for relative in INPUT_SNAPSHOT_DIRECTORIES:
        try:
            (paths.directory / relative).rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            return
    try:
        paths.directory.rmdir()
    except OSError:
        pass


def _publish_staged_run(
    *, staging: _RunPaths, destination: Path, run_store: Path
) -> None:
    try:
        os.rename(staging.directory, destination)
        descriptor = os.open(
            run_store,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except FileExistsError as exc:
        raise _LifecycleError("runIdCollision", 73) from exc
    except OSError as exc:
        raise _LifecycleError("runPublishFailed", 73) from exc


def _existing_run_paths(*, private_root: Path, run_id: str) -> _RunPaths:
    current = private_root
    for component in ("homelab", "runs", run_id):
        current /= component
        try:
            PRIVATE_INPUT.validate_private_directory(
                current,
                "HomeLab run directory",
                private_root=private_root,
            )
        except PRIVATE_INPUT.PrivateInputError as exc:
            raise _LifecycleError("runNotFoundOrInvalid", 66) from exc
    return _RunPaths(current)


@contextmanager
def _journal_lock(paths: _RunPaths, *, exclusive: bool):
    descriptor: int | None = None
    try:
        descriptor = os.open(
            paths.directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        fcntl.flock(
            descriptor,
            fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
        )
    except OSError as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise _LifecycleError("runLockFailed", 73) from exc
    assert descriptor is not None
    try:
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


@contextmanager
def _execution_lock(path: Path, *, private_root: Path):
    try:
        PRIVATE_INPUT.validate_private_directory(
            path,
            "HomeLab global execution lock",
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("executionLockInvalid", 65) from exc

    def identity_matches(descriptor: int) -> bool:
        try:
            opened = os.fstat(descriptor)
            current = os.lstat(path)
        except OSError:
            return False
        return (
            stat.S_ISDIR(opened.st_mode)
            and stat.S_ISDIR(current.st_mode)
            and stat.S_IMODE(opened.st_mode) == 0o700
            and stat.S_IMODE(current.st_mode) == 0o700
            and opened.st_uid == os.geteuid()
            and current.st_uid == os.geteuid()
            and opened.st_dev == current.st_dev
            and opened.st_ino == current.st_ino
        )

    descriptor: int | None = None
    locked = False
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        if not identity_matches(descriptor):
            raise _LifecycleError("executionLockInvalid", 65)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        locked = True
        if not identity_matches(descriptor):
            raise _LifecycleError("executionLockInvalid", 65)
    except _LifecycleError:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise
    except OSError as exc:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise _LifecycleError("executionLockFailed", 73) from exc
    assert descriptor is not None
    try:
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _read_run_file(path: Path, *, description: str, private_root: Path) -> bytes:
    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("runStateInvalid", 65) from exc


def _load_run(
    *, paths: _RunPaths, private_root: Path, expected_run_id: str
) -> tuple[_RunPlan, _RunJournal, tuple[StagedInput, ...]]:
    plan_content = _read_run_file(
        paths.plan,
        description="HomeLab run plan",
        private_root=private_root,
    )
    plan = _RunPlan.from_document(_strict_json(plan_content, "plan"))
    if plan_content != _canonical_bytes(plan.to_document()):
        raise _LifecycleError("planEncodingInvalid", 65)
    if plan.run_id != expected_run_id:
        raise _LifecycleError("planRunIdMismatch", 65)
    plan_digest = _digest(plan_content)

    profile_content = _read_run_file(
        paths.profile,
        description="staged HomeLab profile",
        private_root=private_root,
    )
    if _digest(profile_content) != plan.source_profile_digest:
        raise _LifecycleError("profileDigestMismatch", 65)

    try:
        for relative in reversed(INPUT_SNAPSHOT_DIRECTORIES):
            PRIVATE_INPUT.validate_private_directory(
                paths.directory / relative,
                "HomeLab staged input directory",
                private_root=private_root,
            )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("stagedInputsInvalid", 65) from exc
    execution_inputs: list[StagedInput] = []
    for record in plan.private_inputs:
        snapshot = paths.input(record.name)
        content = _read_run_file(
            snapshot,
            description=f"staged HomeLab input {record.name}",
            private_root=private_root,
        )
        if len(content) != record.size_bytes or _digest(content) != record.digest:
            raise _LifecycleError("stagedInputDigestMismatch", 65)
        if record.name in EXECUTION_INPUT_NAMES:
            execution_inputs.append(
                StagedInput(
                    name=record.name,
                    path=snapshot,
                    digest=record.digest,
                )
            )

    journal_content = _read_run_file(
        paths.journal,
        description="HomeLab run journal",
        private_root=private_root,
    )
    journal = _RunJournal.from_document(_strict_json(journal_content, "journal"))
    if journal_content != _canonical_bytes(journal.to_document()):
        raise _LifecycleError("journalEncodingInvalid", 65)
    if journal.run_id != expected_run_id or journal.plan_digest != plan_digest:
        raise _LifecycleError("journalIdentityMismatch", 65)
    return plan, journal, tuple(execution_inputs)


def _replace_journal(
    *, paths: _RunPaths, journal: _RunJournal, private_root: Path
) -> None:
    content = _canonical_bytes(journal.to_document())
    temporary = paths.directory / f".journal-{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    replaced = False
    try:
        PRIVATE_INPUT.validate_private_file(
            paths.journal,
            "HomeLab run journal",
            private_root=private_root,
        )
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("journal write returned no progress")
            view = view[written:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, paths.journal)
        replaced = True
        directory_descriptor = os.open(
            paths.directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except (OSError, PRIVATE_INPUT.PrivateInputError) as exc:
        raise _LifecycleError("journalWriteFailed", 73) from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if not replaced:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _replace_step(
    journal: _RunJournal,
    *,
    index: int,
    step: _JournalStep,
    phase: str,
    required_approval_digest: str | None,
    last_approved_digest: str | None,
) -> _RunJournal:
    steps = list(journal.steps)
    steps[index] = step
    return replace(
        journal,
        phase=phase,
        required_approval_digest=required_approval_digest,
        last_approved_digest=last_approved_digest,
        revision=journal.revision + 1,
        steps=tuple(steps),
    )


def _validate_receipt(
    receipt: Any, *, expected_step: ExecutionStep, current_approval: str
) -> ExecutionReceipt:
    if (
        not isinstance(receipt, ExecutionReceipt)
        or receipt.step is not expected_step
        or not isinstance(receipt.disposition, ExecutionDisposition)
        or not isinstance(receipt.digest, str)
        or DIGEST_PATTERN.fullmatch(receipt.digest) is None
        or (
            receipt.disposition is ExecutionDisposition.AWAITING_APPROVAL
            and receipt.digest == current_approval
        )
    ):
        raise ExecutionPortError("executionReceiptInvalid")
    return receipt


def _record_execution_failure(
    *,
    paths: _RunPaths,
    journal: _RunJournal,
    index: int,
    error_code: str,
    private_root: Path,
) -> None:
    failed_step = replace(journal.steps[index], last_error_code=error_code)
    failed = _replace_step(
        journal,
        index=index,
        step=failed_step,
        phase="failed",
        required_approval_digest=journal.required_approval_digest,
        last_approved_digest=journal.last_approved_digest,
    )
    _replace_journal(paths=paths, journal=failed, private_root=private_root)


@dataclass(frozen=True)
class _ExecutionCheckpoint:
    plan: _RunPlan
    journal: _RunJournal
    index: int
    request: ExecutionRequest


def _succeeded_result(run_id: str) -> dict[str, Any]:
    return {
        "phase": "succeeded",
        "requiredApprovalDigest": None,
        "runId": run_id,
    }


def _begin_execution_step(
    *,
    paths: _RunPaths,
    private_root: Path,
    run_id: str,
    approve_digest: str,
) -> _ExecutionCheckpoint | dict[str, Any]:
    with _journal_lock(paths, exclusive=True):
        plan, journal, staged_inputs = _load_run(
            paths=paths,
            private_root=private_root,
            expected_run_id=run_id,
        )
        expected_approval = (
            journal.last_approved_digest
            if journal.phase == "succeeded"
            else journal.required_approval_digest
        )
        if approve_digest != expected_approval:
            raise _LifecycleError("approvalDigestMismatch", 64)
        if journal.phase == "succeeded":
            return _succeeded_result(run_id)

        index = next(
            index
            for index, step in enumerate(journal.steps)
            if step.status != "completed"
        )
        current = journal.steps[index]
        started = replace(
            current,
            status="started",
            attempts=current.attempts + 1,
            receipt_digest=None,
            last_error_code=None,
        )
        started_journal = _replace_step(
            journal,
            index=index,
            step=started,
            phase="applying",
            required_approval_digest=approve_digest,
            last_approved_digest=approve_digest,
        )
        _replace_journal(
            paths=paths,
            journal=started_journal,
            private_root=private_root,
        )
        return _ExecutionCheckpoint(
            plan=plan,
            journal=started_journal,
            index=index,
            request=ExecutionRequest(
                run_id=run_id,
                plan_digest=started_journal.plan_digest,
                approval_digest=approve_digest,
                commit=plan.commit,
                step=current.step,
                attempt=started.attempts,
                profile=plan.profile,
                inputs=staged_inputs,
            ),
        )


def _reload_execution_checkpoint(
    *,
    paths: _RunPaths,
    private_root: Path,
    run_id: str,
    checkpoint: _ExecutionCheckpoint,
) -> _RunJournal:
    plan, journal, _ = _load_run(
        paths=paths,
        private_root=private_root,
        expected_run_id=run_id,
    )
    actual_step = journal.steps[checkpoint.index]
    expected_step = checkpoint.journal.steps[checkpoint.index]
    if (
        plan != checkpoint.plan
        or journal.revision != checkpoint.journal.revision
        or actual_step.step is not checkpoint.request.step
        or actual_step.status != "started"
        or actual_step.attempts != checkpoint.request.attempt
        or actual_step != expected_step
        or journal != checkpoint.journal
    ):
        raise _LifecycleError("executionCheckpointChanged", 75)
    return journal


def _record_checkpoint_failure(
    *,
    paths: _RunPaths,
    private_root: Path,
    run_id: str,
    checkpoint: _ExecutionCheckpoint,
    error_code: str,
) -> None:
    with _journal_lock(paths, exclusive=True):
        journal = _reload_execution_checkpoint(
            paths=paths,
            private_root=private_root,
            run_id=run_id,
            checkpoint=checkpoint,
        )
        _record_execution_failure(
            paths=paths,
            journal=journal,
            index=checkpoint.index,
            error_code=error_code,
            private_root=private_root,
        )


def _record_checkpoint_receipt(
    *,
    paths: _RunPaths,
    private_root: Path,
    run_id: str,
    checkpoint: _ExecutionCheckpoint,
    receipt: ExecutionReceipt,
) -> dict[str, Any] | None:
    with _journal_lock(paths, exclusive=True):
        journal = _reload_execution_checkpoint(
            paths=paths,
            private_root=private_root,
            run_id=run_id,
            checkpoint=checkpoint,
        )
        started = journal.steps[checkpoint.index]
        if receipt.disposition is ExecutionDisposition.AWAITING_APPROVAL:
            awaiting = replace(
                started,
                status="awaitingApproval",
                receipt_digest=receipt.digest,
            )
            awaiting_journal = _replace_step(
                journal,
                index=checkpoint.index,
                step=awaiting,
                phase="awaitingApproval",
                required_approval_digest=receipt.digest,
                last_approved_digest=checkpoint.request.approval_digest,
            )
            _replace_journal(
                paths=paths,
                journal=awaiting_journal,
                private_root=private_root,
            )
            return {
                "phase": "awaitingApproval",
                "requiredApprovalDigest": receipt.digest,
                "runId": run_id,
            }

        completed = replace(
            started,
            status="completed",
            receipt_digest=receipt.digest,
        )
        final_step = checkpoint.index == len(journal.steps) - 1
        completed_journal = _replace_step(
            journal,
            index=checkpoint.index,
            step=completed,
            phase="succeeded" if final_step else "applying",
            required_approval_digest=(
                None if final_step else checkpoint.request.approval_digest
            ),
            last_approved_digest=checkpoint.request.approval_digest,
        )
        _replace_journal(
            paths=paths,
            journal=completed_journal,
            private_root=private_root,
        )
        return _succeeded_result(run_id) if final_step else None


def _apply(
    *,
    run_id: str,
    approve_digest: str,
    private_root: Path | None,
    execution_port: ExecutionPort,
) -> dict[str, Any]:
    _validate_run_id(run_id)
    if DIGEST_PATTERN.fullmatch(approve_digest) is None:
        raise _LifecycleError("approvalDigestInvalid", 64)
    root = _private_root(private_root)
    paths = _existing_run_paths(private_root=root, run_id=run_id)
    with _execution_lock(
        _global_execution_lock_path(root),
        private_root=root,
    ):
        while True:
            checkpoint_or_result = _begin_execution_step(
                paths=paths,
                private_root=root,
                run_id=run_id,
                approve_digest=approve_digest,
            )
            if isinstance(checkpoint_or_result, dict):
                return checkpoint_or_result
            checkpoint = checkpoint_or_result
            try:
                receipt = _validate_receipt(
                    execution_port.execute(checkpoint.request),
                    expected_step=checkpoint.request.step,
                    current_approval=approve_digest,
                )
            except ExecutionPortError as exc:
                _record_checkpoint_failure(
                    paths=paths,
                    private_root=root,
                    run_id=run_id,
                    checkpoint=checkpoint,
                    error_code=exc.code,
                )
                raise _LifecycleError(exc.code, 75) from exc
            except Exception as exc:
                _record_checkpoint_failure(
                    paths=paths,
                    private_root=root,
                    run_id=run_id,
                    checkpoint=checkpoint,
                    error_code="executionFailed",
                )
                raise _LifecycleError("executionFailed", 75) from exc
            result = _record_checkpoint_receipt(
                paths=paths,
                private_root=root,
                run_id=run_id,
                checkpoint=checkpoint,
                receipt=receipt,
            )
            if result is not None:
                return result


def _status(*, run_id: str, private_root: Path | None) -> dict[str, Any]:
    _validate_run_id(run_id)
    root = _private_root(private_root)
    paths = _existing_run_paths(private_root=root, run_id=run_id)
    with _journal_lock(paths, exclusive=False):
        _, journal, _ = _load_run(
            paths=paths,
            private_root=root,
            expected_run_id=run_id,
        )
    return journal.to_document()


def _snapshot_private_inputs(
    *,
    source_profile: _SourceProfile,
    staging: _RunPaths,
    private_root: Path,
    kubeconfig_runner: Callable[..., str],
) -> tuple[_InputRecord, ...]:
    kubeconfig = source_profile.private_inputs["kubeconfig"]
    assert kubeconfig is not None
    try:
        PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
            source=kubeconfig,
            raw_destination=staging.input("kubeconfigRaw"),
            flattened_destination=staging.input("kubeconfig"),
            context=source_profile.profile.context,
            runner=kubeconfig_runner,
            private_root=private_root,
        )
        present_names = {
            name
            for name, path in source_profile.private_inputs.items()
            if path is not None
        } | {"kubeconfigRaw"}
        expected_names = _expected_input_names(source_profile.profile, present_names)
        for name in expected_names:
            if name in {"kubeconfigRaw", "kubeconfig"}:
                continue
            source = source_profile.private_inputs[name]
            assert source is not None
            PRIVATE_INPUT.snapshot_private_file(
                source=source,
                destination=staging.input(name),
                description=f"HomeLab private input {name}",
                private_root=private_root,
            )
    except _LifecycleError:
        raise
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("privateInputSnapshotFailed", 65) from exc

    records: list[_InputRecord] = []
    for name in expected_names:
        content = _read_run_file(
            staging.input(name),
            description=f"staged HomeLab input {name}",
            private_root=private_root,
        )
        records.append(
            _InputRecord(
                name=name,
                snapshot=INPUT_SNAPSHOT_PATHS[name],
                digest=_digest(content),
                size_bytes=len(content),
            )
        )
    return tuple(records)


def _stage(
    *,
    profile_path: Path,
    commit: str,
    private_root: Path | None,
    run_id_factory: Callable[[], str],
    source_inspector: SourceInspector,
    kubeconfig_runner: Callable[..., str],
) -> dict[str, Any]:
    if FULL_SHA_PATTERN.fullmatch(commit) is None:
        raise _LifecycleError("commitInvalid", 64)
    root = _private_root(private_root)
    try:
        profile_content = PRIVATE_INPUT.read_private_bytes(
            profile_path,
            "HomeLab profile",
            private_root=root,
            maximum_size=PROFILE_MAXIMUM_BYTES,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise _LifecycleError("profileInputInvalid", 65) from exc
    source_profile = _SourceProfile.from_document(
        _strict_json(profile_content, "profile")
    )
    try:
        source = source_inspector.inspect()
    except _LifecycleError:
        raise
    except Exception as exc:
        raise _LifecycleError("sourceInspectionFailed", 74) from exc
    if (
        not isinstance(source, SourceSnapshot)
        or not isinstance(source.clean, bool)
        or not isinstance(source.head_commit, str)
        or FULL_SHA_PATTERN.fullmatch(source.head_commit) is None
    ):
        raise _LifecycleError("sourceInspectionInvalid", 65)
    if source.head_commit != commit:
        raise _LifecycleError("sourceCommitMismatch", 65)
    if not source.clean:
        raise _LifecycleError("sourceCheckoutDirty", 65)
    try:
        run_id = run_id_factory()
    except Exception as exc:
        raise _LifecycleError("runIdAllocationFailed", 73) from exc
    _validate_run_id(run_id)
    store = _run_store(root)
    _ensure_global_execution_lock(root)
    staging_directory = store / f".stage-{secrets.token_hex(16)}"
    try:
        staging_directory.mkdir(mode=0o700)
    except OSError as exc:
        raise _LifecycleError("runStoreUnavailable", 73) from exc
    staging = _RunPaths(staging_directory)
    try:
        _write_snapshot(
            path=staging.profile,
            content=profile_content,
            description="staged HomeLab profile",
            private_root=root,
        )
        input_records = _snapshot_private_inputs(
            source_profile=source_profile,
            staging=staging,
            private_root=root,
            kubeconfig_runner=kubeconfig_runner,
        )
        plan = _RunPlan(
            run_id=run_id,
            commit=commit,
            profile=source_profile.profile,
            source_profile_digest=_digest(profile_content),
            private_inputs=input_records,
        )
        plan_content = _canonical_bytes(plan.to_document())
        plan_digest = _digest(plan_content)
        journal_content = _canonical_bytes(
            _RunJournal.staged(
                run_id=run_id,
                plan_digest=plan_digest,
            ).to_document()
        )
        _write_snapshot(
            path=staging.plan,
            content=plan_content,
            description="HomeLab run plan",
            private_root=root,
        )
        _write_snapshot(
            path=staging.journal,
            content=journal_content,
            description="HomeLab run journal",
            private_root=root,
        )
        _publish_staged_run(
            staging=staging,
            destination=store / run_id,
            run_store=store,
        )
    except BaseException:
        _discard_staging_directory(staging)
        raise

    return {
        "approvalDigest": plan_digest,
        "phase": "staged",
        "planDigest": plan_digest,
        "runId": run_id,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage, apply, or inspect one HomeLab deployment run.",
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    stage = commands.add_parser("stage", allow_abbrev=False)
    stage.add_argument("--profile", required=True, type=Path)
    stage.add_argument("--commit", required=True)

    apply = commands.add_parser("apply", allow_abbrev=False)
    apply.add_argument("--run-id", required=True)
    apply.add_argument("--approve-digest", required=True)

    status = commands.add_parser("status", allow_abbrev=False)
    status.add_argument("--run-id", required=True)
    return parser


def _write_json(stream: TextIO, document: dict[str, Any]) -> None:
    stream.write(json.dumps(document, separators=(",", ":"), sort_keys=True))
    stream.write("\n")


def main(
    argv: list[str] | None = None,
    *,
    execution_port: ExecutionPort | None = None,
    private_root: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    run_id_factory: Callable[[], str] | None = None,
    source_inspector: SourceInspector | None = None,
    kubeconfig_runner: Callable[..., str] | None = None,
) -> int:
    """Run the HomeLab lifecycle command-line facade."""

    args = _build_parser().parse_args(argv)
    output = stdout if stdout is not None else sys.stdout
    error_output = stderr if stderr is not None else sys.stderr
    id_factory = (
        run_id_factory
        if run_id_factory is not None
        else lambda: f"run-{secrets.token_hex(16)}"
    )
    inspector = (
        source_inspector
        if source_inspector is not None
        else _GitSourceInspector(Path(__file__).resolve().parents[3])
    )
    config_runner = (
        kubeconfig_runner if kubeconfig_runner is not None else _run_kubeconfig_command
    )
    try:
        if args.command == "stage":
            result = _stage(
                profile_path=args.profile,
                commit=args.commit,
                private_root=private_root,
                run_id_factory=id_factory,
                source_inspector=inspector,
                kubeconfig_runner=config_runner,
            )
        elif args.command == "apply":
            if execution_port is not None:
                port = execution_port
            else:
                try:
                    port = HOMELAB_EXECUTION.create_production_execution_port(
                        facade=sys.modules[__name__],
                        repository_root=Path(__file__).resolve().parents[3],
                    )
                except Exception:  # noqa: BLE001 - sanitize adapter preflight.
                    raise _LifecycleError(
                        "executionAdapterUnavailable",
                        75,
                    ) from None
            result = _apply(
                run_id=args.run_id,
                approve_digest=args.approve_digest,
                private_root=private_root,
                execution_port=port,
            )
        else:
            result = _status(
                run_id=args.run_id,
                private_root=private_root,
            )
    except _LifecycleError as exc:
        _write_json(error_output, {"error": {"code": exc.code}})
        return exc.exit_code
    _write_json(output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
