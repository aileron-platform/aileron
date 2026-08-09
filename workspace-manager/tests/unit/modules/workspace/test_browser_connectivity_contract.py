import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.workspace.browser_connectivity_contract import (
    TURNPathEvidence,
    TURNPathEvidenceSnapshot,
    TURNReachabilityProfile,
    TURNReachabilityProfileError,
    evidence_is_fresh,
)

PROFILE_PATH = Path(
    "/repo-root/contracts/browser-connectivity/turn-reachability-profile.json"
)
DIGEST_VECTORS_PATH = Path(
    "/repo-root/contracts/browser-connectivity/profile-digest-vectors.json"
)


def test_shared_profile_revision_matches_the_cross_runtime_contract() -> None:
    profile = TURNReachabilityProfile.from_file(PROFILE_PATH)

    assert profile.revision == (
        "sha256:dec4c3e486c36aa2fb937400a10e28c924f5737b0a7af4e7a94ce94de29c6aaa"
    )


def test_profile_rejects_unknown_contract_version() -> None:
    raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    raw["contractVersion"] = "browser-connectivity/v2"

    with pytest.raises(TURNReachabilityProfileError, match="contractVersion"):
        TURNReachabilityProfile.from_mapping(raw)


def test_profile_revision_normalizes_set_fields() -> None:
    first = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    first["evidence"]["requiredFrontendVantages"] = ["z-vantage", "host", "z-vantage"]
    second = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    second["evidence"]["requiredFrontendVantages"] = ["host", "z-vantage"]

    assert TURNReachabilityProfile.from_mapping(first).revision == (
        TURNReachabilityProfile.from_mapping(second).revision
    )


@pytest.mark.parametrize(
    "vector",
    json.loads(DIGEST_VECTORS_PATH.read_text(encoding="utf-8"))["vectors"],
    ids=lambda vector: vector["name"],
)
def test_profile_matches_shared_digest_vectors(vector: dict) -> None:
    profile = TURNReachabilityProfile.from_mapping(vector["profile"])

    assert profile.revision == vector["expectedRevision"]


@pytest.mark.parametrize(
    "invalid_change",
    [
        lambda profile: {**profile, "unexpected": True},
        lambda profile: {
            **profile,
            "backend": {**profile["backend"], "unexpected": True},
        },
        lambda profile: {
            **profile,
            "backend": {
                **profile["backend"],
                "controlDestination": {"kind": "unenforced", "unexpected": True},
            },
        },
    ],
)
def test_profile_parser_rejects_shape_drift(invalid_change) -> None:
    raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    with pytest.raises(TURNReachabilityProfileError):
        TURNReachabilityProfile.from_mapping(invalid_change(raw))


def test_evidence_freshness_uses_authority_time_and_ignores_producer_clock() -> None:
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    evidence = TURNPathEvidence.from_mapping(
        {
            "contractVersion": "browser-connectivity/v1",
            "producer": {"installationId": "install-1", "vantageId": "host"},
            "outcome": "success",
            "profileRevision": "sha256:" + "a" * 64,
            "credentialRevision": "credential",
            "measuredAt": "2030-08-05T00:00:00Z",
            "acceptedAt": "2026-08-05T00:00:00Z",
            "expiresAt": "2026-08-05T00:01:00Z",
            "relayAddress": "127.0.0.1:49160",
        }
    )

    assert evidence_is_fresh(
        evidence,
        profile_revision="sha256:" + "a" * 64,
        credential_revision="credential",
        now=now,
    )
    with pytest.raises(ValueError, match="include a timezone"):
        TURNPathEvidence.from_mapping(
            {
                "contractVersion": "browser-connectivity/v1",
                "producer": {"installationId": "install-1", "vantageId": "host"},
                "outcome": "success",
                "profileRevision": "sha256:" + "a" * 64,
                "credentialRevision": "credential",
                "acceptedAt": "2026-08-05T00:00:00",
                "expiresAt": "2026-08-05T00:01:00Z",
                "relayAddress": "127.0.0.1:49160",
            }
        )


def test_evidence_snapshot_rejects_cross_producer_last_success() -> None:
    evidence = {
        "contractVersion": "browser-connectivity/v1",
        "producer": {"installationId": "install-1", "vantageId": "host"},
        "outcome": "failure",
        "profileRevision": "sha256:" + "a" * 64,
        "credentialRevision": "credential",
        "acceptedAt": "2026-08-05T00:00:00Z",
        "expiresAt": "2026-08-05T00:01:00Z",
        "errorCode": "TURN_RELAY_UNAVAILABLE",
    }
    last_success = {
        **{key: value for key, value in evidence.items() if key != "errorCode"},
        "producer": {"installationId": "install-1", "vantageId": "other"},
        "outcome": "success",
        "relayAddress": "127.0.0.1:49160",
    }

    with pytest.raises(ValueError, match="identity and revisions"):
        TURNPathEvidenceSnapshot.from_mapping(
            {
                "contractVersion": "browser-connectivity/v1",
                "latestAttempt": evidence,
                "lastSuccess": last_success,
            }
        )
