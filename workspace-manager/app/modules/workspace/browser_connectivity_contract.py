"""Provider-neutral TURN reachability profile and evidence contract."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs

from app.modules.workspace.browser_connectivity_contract_generated import (
    BROWSER_CONNECTIVITY_CONTRACT_VERSION,
    CONNECTIVITY_STATES,
    EVIDENCE_OUTCOMES,
)

PROFILE_REVISION_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


class TURNReachabilityProfileError(ValueError):
    """The canonical TURN profile is missing or violates its contract."""


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TURNReachabilityProfileError(f"{name} must be an object")
    return value


def _reject_unknown_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    name: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise TURNReachabilityProfileError(
            f"{name} contains unsupported fields: {', '.join(unknown)}"
        )


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TURNReachabilityProfileError(f"{name} must be a non-empty string")
    return value.strip()


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TURNReachabilityProfileError(f"{name} must be a non-empty array")
    result = tuple(
        _string(item, f"{name}[{index}]") for index, item in enumerate(value)
    )
    return result


def _optional_string_list(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise TURNReachabilityProfileError(f"{name} must be an array")
    return tuple(_string(item, f"{name}[{index}]") for index, item in enumerate(value))


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TURNReachabilityProfileError(f"{name} must be a positive integer")
    return value


def _turn_urls(value: object, name: str) -> tuple[str, ...]:
    urls = _string_list(value, name)
    for url in urls:
        if not _is_valid_turn_endpoint(url):
            raise TURNReachabilityProfileError(
                f"{name} must contain only TURN endpoints"
            )
    return urls


def _is_valid_turn_endpoint(value: str) -> bool:
    lower_value = value.lower()
    secure = lower_value.startswith("turns:")
    if lower_value.startswith("turn:"):
        address = value[5:]
        default_port = 3478
    elif secure:
        address = value[6:]
        default_port = 5349
    else:
        return False
    if "?" in address:
        address, query_string = address.split("?", 1)
        try:
            query = parse_qs(query_string, keep_blank_values=True)
        except ValueError:
            return False
        transports = query.get("transport")
        if transports is not None:
            if len(transports) != 1 or transports[0].lower() not in {"udp", "tcp"}:
                return False
            if secure and transports[0].lower() == "udp":
                return False
    address = address.removeprefix("//")
    if not address:
        return False

    host = address
    port = default_port
    if address.startswith("["):
        closing = address.find("]")
        if closing < 0:
            return False
        host = address[1:closing]
        suffix = address[closing + 1 :]
        if suffix:
            if not suffix.startswith(":"):
                return False
            try:
                port = int(suffix[1:])
            except ValueError:
                return False
    elif address.count(":") == 1:
        host, raw_port = address.rsplit(":", 1)
        try:
            port = int(raw_port)
        except ValueError:
            return False
    elif ":" in address:
        try:
            ipaddress.ip_address(address)
        except ValueError:
            return False

    if not host.strip() or any(char in host for char in "/?# \t\r\n"):
        return False
    return 1 <= port <= 65535


def _destination(
    value: object,
    name: str,
    *,
    policy_backend: str,
    relay: bool,
) -> Mapping[str, Any]:
    destination = _mapping(value, name)
    _reject_unknown_keys(
        destination, {"kind", "values", "namespace", "podLabels"}, name
    )
    kind = _string(destination.get("kind"), f"{name}.kind")
    if kind not in {
        "ciliumEntities",
        "cidrs",
        "fqdns",
        "namespacePods",
        "unenforced",
    }:
        raise TURNReachabilityProfileError(f"{name}.kind is unsupported")
    if kind == "ciliumEntities":
        if policy_backend != "cilium":
            raise TURNReachabilityProfileError(
                f"{name}.kind requires the cilium policy backend"
            )
        _string_list(destination.get("values"), f"{name}.values")
    if kind == "cidrs":
        values = _string_list(destination.get("values"), f"{name}.values")
        for value in values:
            try:
                ipaddress.ip_network(value, strict=False)
            except ValueError as exc:
                raise TURNReachabilityProfileError(
                    f"{name}.values contains an invalid CIDR"
                ) from exc
    if kind == "fqdns":
        if relay or policy_backend != "cilium":
            raise TURNReachabilityProfileError(
                f"{name}.kind is not supported for this destination"
            )
        _string_list(destination.get("values"), f"{name}.values")
    if kind == "namespacePods":
        _string(destination.get("namespace"), f"{name}.namespace")
        labels = _mapping(destination.get("podLabels"), f"{name}.podLabels")
        if not labels or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(item, str)
            or not item.strip()
            for key, item in labels.items()
        ):
            raise TURNReachabilityProfileError(
                f"{name}.podLabels must contain non-empty string entries"
            )
    if kind == "unenforced" and policy_backend != "unenforced":
        raise TURNReachabilityProfileError(
            f"{name}.kind requires the unenforced policy backend"
        )
    return destination


def _canonical_destination(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": _string(value["kind"], "destination.kind")}
    if value.get("values"):
        result["values"] = sorted(
            {_string(item, "destination.values") for item in value["values"]}
        )
    if value.get("namespace"):
        result["namespace"] = _string(value["namespace"], "destination.namespace")
    if value.get("podLabels"):
        result["podLabels"] = {
            key.strip(): _string(value["podLabels"][key], "destination.podLabels")
            for key in sorted(value["podLabels"])
        }
    return result


@dataclass(frozen=True)
class TURNReachabilityProfile:
    """Strictly validated representation of the canonical profile."""

    contract_version: str
    policy_backend: str
    backend_urls: tuple[str, ...]
    backend_control_destination: Mapping[str, Any]
    backend_relay_destination: Mapping[str, Any]
    relay_port_min: int
    relay_port_max: int
    frontend_urls: tuple[str, ...]
    credential_issuer_kind: str
    credential_issuer_secret_ref: str
    credential_ttl_seconds: int
    evidence_interval_seconds: int
    evidence_ttl_seconds: int
    required_frontend_vantages: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: object) -> "TURNReachabilityProfile":
        profile = _mapping(raw, "TURN reachability profile")
        _reject_unknown_keys(
            profile,
            {
                "contractVersion",
                "policyBackend",
                "backend",
                "frontend",
                "credentialIssuer",
                "evidence",
            },
            "TURN reachability profile",
        )
        contract_version = _string(profile.get("contractVersion"), "contractVersion")
        if contract_version != BROWSER_CONNECTIVITY_CONTRACT_VERSION:
            raise TURNReachabilityProfileError("contractVersion is unsupported")
        policy_backend = _string(profile.get("policyBackend"), "policyBackend")
        if policy_backend not in {"cilium", "kubernetes", "unenforced"}:
            raise TURNReachabilityProfileError("policyBackend is unsupported")

        backend = _mapping(profile.get("backend"), "backend")
        frontend = _mapping(profile.get("frontend"), "frontend")
        credential = _mapping(profile.get("credentialIssuer"), "credentialIssuer")
        evidence = _mapping(profile.get("evidence"), "evidence")
        _reject_unknown_keys(
            backend,
            {"urls", "controlDestination", "relayDestination", "relayPortRange"},
            "backend",
        )
        _reject_unknown_keys(frontend, {"urls"}, "frontend")
        _reject_unknown_keys(
            credential,
            {"kind", "secretRef", "ttlSeconds"},
            "credentialIssuer",
        )
        _reject_unknown_keys(
            evidence,
            {"intervalSeconds", "ttlSeconds", "requiredFrontendVantages"},
            "evidence",
        )
        control_destination = _destination(
            backend.get("controlDestination"),
            "backend.controlDestination",
            policy_backend=policy_backend,
            relay=False,
        )
        relay_destination = _destination(
            backend.get("relayDestination"),
            "backend.relayDestination",
            policy_backend=policy_backend,
            relay=True,
        )
        relay_range = _mapping(backend.get("relayPortRange"), "backend.relayPortRange")
        _reject_unknown_keys(relay_range, {"min", "max"}, "backend.relayPortRange")
        relay_port_min = _positive_integer(relay_range.get("min"), "relayPortRange.min")
        relay_port_max = _positive_integer(relay_range.get("max"), "relayPortRange.max")
        if (
            relay_port_min > relay_port_max
            or relay_port_max > 65535
            or relay_port_min < 1024
        ):
            raise TURNReachabilityProfileError("relayPortRange is invalid")

        issuer_kind = _string(credential.get("kind"), "credentialIssuer.kind")
        if issuer_kind != "turnRest":
            raise TURNReachabilityProfileError("credentialIssuer.kind is unsupported")
        credential_ttl_seconds = _positive_integer(
            credential.get("ttlSeconds"), "credentialIssuer.ttlSeconds"
        )
        if credential_ttl_seconds < 60:
            raise TURNReachabilityProfileError(
                "credentialIssuer.ttlSeconds must be at least 60"
            )

        evidence_interval_seconds = _positive_integer(
            evidence.get("intervalSeconds"), "evidence.intervalSeconds"
        )
        evidence_ttl_seconds = _positive_integer(
            evidence.get("ttlSeconds"), "evidence.ttlSeconds"
        )
        if evidence_ttl_seconds < evidence_interval_seconds * 2:
            raise TURNReachabilityProfileError(
                "evidence.ttlSeconds must be at least twice intervalSeconds"
            )
        required_vantages = _optional_string_list(
            evidence.get("requiredFrontendVantages"),
            "evidence.requiredFrontendVantages",
        )
        if policy_backend != "unenforced" and not required_vantages:
            raise TURNReachabilityProfileError(
                "evidence.requiredFrontendVantages is required"
            )

        return cls(
            contract_version=contract_version,
            policy_backend=policy_backend,
            backend_urls=_turn_urls(backend.get("urls"), "backend.urls"),
            backend_control_destination=_canonical_destination(control_destination),
            backend_relay_destination=_canonical_destination(relay_destination),
            relay_port_min=relay_port_min,
            relay_port_max=relay_port_max,
            frontend_urls=_turn_urls(frontend.get("urls"), "frontend.urls"),
            credential_issuer_kind=issuer_kind,
            credential_issuer_secret_ref=_string(
                credential.get("secretRef"), "credentialIssuer.secretRef"
            ),
            credential_ttl_seconds=credential_ttl_seconds,
            evidence_interval_seconds=evidence_interval_seconds,
            evidence_ttl_seconds=evidence_ttl_seconds,
            required_frontend_vantages=tuple(sorted(set(required_vantages))),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "TURNReachabilityProfile":
        profile_path = Path(path)
        try:
            raw = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TURNReachabilityProfileError(
                f"read TURN reachability profile failed: {profile_path}"
            ) from exc
        return cls.from_mapping(raw)

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "policyBackend": self.policy_backend,
            "backend": {
                "urls": list(self.backend_urls),
                "controlDestination": _canonical_destination(
                    self.backend_control_destination
                ),
                "relayDestination": _canonical_destination(
                    self.backend_relay_destination
                ),
                "relayPortRange": {
                    "min": self.relay_port_min,
                    "max": self.relay_port_max,
                },
            },
            "frontend": {"urls": list(self.frontend_urls)},
            "credentialIssuer": {
                "kind": self.credential_issuer_kind,
                "secretRef": self.credential_issuer_secret_ref,
                "ttlSeconds": self.credential_ttl_seconds,
            },
            "evidence": {
                "intervalSeconds": self.evidence_interval_seconds,
                "ttlSeconds": self.evidence_ttl_seconds,
                "requiredFrontendVantages": sorted(
                    set(self.required_frontend_vantages)
                ),
            },
        }

    @property
    def revision(self) -> str:
        canonical = json.dumps(
            self.canonical_mapping(),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(canonical).hexdigest()


def parse_timestamp(value: object, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class TURNPathEvidence:
    contract_version: str
    installation_id: str
    vantage_id: str
    profile_revision: str
    credential_revision: str
    outcome: str
    measured_at: datetime | None
    accepted_at: datetime
    expires_at: datetime
    relay_address: str | None = None
    error_code: str | None = None

    @classmethod
    def from_mapping(cls, raw: object) -> "TURNPathEvidence":
        evidence = _mapping(raw, "TURN path evidence")
        _reject_unknown_keys(
            evidence,
            {
                "contractVersion",
                "producer",
                "profileRevision",
                "credentialRevision",
                "outcome",
                "measuredAt",
                "acceptedAt",
                "expiresAt",
                "relayAddress",
                "errorCode",
            },
            "TURN path evidence",
        )
        contract_version = _string(
            evidence.get("contractVersion"), "evidence.contractVersion"
        )
        if contract_version != BROWSER_CONNECTIVITY_CONTRACT_VERSION:
            raise ValueError("evidence.contractVersion is unsupported")
        producer = _mapping(evidence.get("producer"), "evidence.producer")
        _reject_unknown_keys(
            producer, {"installationId", "vantageId"}, "evidence.producer"
        )
        outcome = _string(evidence.get("outcome"), "evidence.outcome")
        if outcome not in EVIDENCE_OUTCOMES:
            raise ValueError("evidence.outcome is unsupported")
        relay_address = (
            _string(evidence["relayAddress"], "evidence.relayAddress")
            if "relayAddress" in evidence
            else None
        )
        error_code = (
            _string(evidence["errorCode"], "evidence.errorCode")
            if "errorCode" in evidence
            else None
        )
        if outcome == "success" and (relay_address is None or error_code is not None):
            raise ValueError("successful evidence payload is invalid")
        if outcome == "failure" and (error_code is None or relay_address is not None):
            raise ValueError("failed evidence payload is invalid")
        accepted_at = parse_timestamp(evidence.get("acceptedAt"), "evidence.acceptedAt")
        expires_at = parse_timestamp(evidence.get("expiresAt"), "evidence.expiresAt")
        if accepted_at is None or expires_at is None or expires_at <= accepted_at:
            raise ValueError("evidence authority timestamps are invalid")
        return cls(
            contract_version=contract_version,
            installation_id=_string(
                producer.get("installationId"), "evidence.producer.installationId"
            ),
            vantage_id=_string(
                producer.get("vantageId"), "evidence.producer.vantageId"
            ),
            profile_revision=_profile_revision(
                evidence.get("profileRevision"), "evidence.profileRevision"
            ),
            credential_revision=_string(
                evidence.get("credentialRevision"), "evidence.credentialRevision"
            ),
            outcome=outcome,
            measured_at=(
                parse_timestamp(evidence["measuredAt"], "evidence.measuredAt")
                if "measuredAt" in evidence
                else None
            ),
            accepted_at=accepted_at,
            expires_at=expires_at,
            relay_address=relay_address,
            error_code=error_code,
        )


@dataclass(frozen=True)
class TURNPathEvidenceSnapshot:
    contract_version: str
    latest_attempt: TURNPathEvidence
    last_success: TURNPathEvidence | None

    @classmethod
    def from_mapping(cls, raw: object) -> "TURNPathEvidenceSnapshot":
        snapshot = _mapping(raw, "TURN path evidence snapshot")
        _reject_unknown_keys(
            snapshot,
            {"contractVersion", "latestAttempt", "lastSuccess"},
            "TURN path evidence snapshot",
        )
        contract_version = _string(snapshot.get("contractVersion"), "contractVersion")
        if contract_version != BROWSER_CONNECTIVITY_CONTRACT_VERSION:
            raise ValueError("contractVersion is unsupported")
        latest_attempt = TURNPathEvidence.from_mapping(snapshot.get("latestAttempt"))
        last_success_raw = snapshot.get("lastSuccess")
        last_success = (
            TURNPathEvidence.from_mapping(last_success_raw)
            if last_success_raw is not None
            else None
        )
        if last_success is not None and last_success.outcome != "success":
            raise ValueError("lastSuccess must have a success outcome")
        if latest_attempt.contract_version != contract_version or (
            last_success is not None
            and last_success.contract_version != contract_version
        ):
            raise ValueError("evidence contractVersion does not match snapshot")
        if last_success is not None and (
            last_success.installation_id != latest_attempt.installation_id
            or last_success.vantage_id != latest_attempt.vantage_id
            or last_success.profile_revision != latest_attempt.profile_revision
            or last_success.credential_revision != latest_attempt.credential_revision
        ):
            raise ValueError(
                "lastSuccess identity and revisions must match latestAttempt"
            )
        return cls(contract_version, latest_attempt, last_success)


def _profile_revision(value: object, name: str) -> str:
    revision = _string(value, name)
    if PROFILE_REVISION_PATTERN.fullmatch(revision) is None:
        raise ValueError(f"{name} must be a sha256 semantic revision")
    return revision


def evidence_is_fresh(
    evidence: TURNPathEvidence,
    *,
    profile_revision: str,
    credential_revision: str,
    now: datetime,
) -> bool:
    return (
        evidence.outcome == "success"
        and evidence.profile_revision == profile_revision
        and evidence.credential_revision == credential_revision
        and evidence.expires_at > now
        and evidence.accepted_at <= now
    )


__all__ = [
    "BROWSER_CONNECTIVITY_CONTRACT_VERSION",
    "CONNECTIVITY_STATES",
    "EVIDENCE_OUTCOMES",
    "TURNPathEvidence",
    "TURNPathEvidenceSnapshot",
    "TURNReachabilityProfile",
    "TURNReachabilityProfileError",
    "evidence_is_fresh",
    "parse_timestamp",
]
