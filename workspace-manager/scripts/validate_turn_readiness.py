"""Validate the Docker Compose TURN readiness installation contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.workspace.browser_connectivity_contract import (
    TURNReachabilityProfile,
    TURNReachabilityProfileError,
)


def _read_non_empty(path: Path, name: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"{name} is unreadable: {path}") from exc
    if not value:
        raise RuntimeError(f"{name} is empty: {path}")
    return value


def validate(args: argparse.Namespace) -> None:
    try:
        profile = TURNReachabilityProfile.from_file(args.profile)
    except TURNReachabilityProfileError as exc:
        raise RuntimeError("TURN reachability profile is invalid") from exc

    if profile.credential_issuer_kind != "turnRest":
        raise RuntimeError("Docker Compose requires a turnRest credential issuer")
    if profile.credential_issuer_secret_ref != "turn-rest-shared-secret":
        raise RuntimeError(
            "Docker Compose requires credentialIssuer.secretRef=turn-rest-shared-secret"
        )
    if args.required_vantage not in profile.required_frontend_vantages:
        raise RuntimeError("the Docker host vantage is not required by the profile")
    if args.relay_port_min != profile.relay_port_min:
        raise RuntimeError("TURN relay minimum port does not match the profile")
    if args.relay_port_max != profile.relay_port_max:
        raise RuntimeError("TURN relay maximum port does not match the profile")
    if not args.credential_revision.strip():
        raise RuntimeError("TURN credential revision is required")
    if not args.operator_image.strip() or not args.coturn_image.strip():
        raise RuntimeError("workspace-operator and coturn images are required")

    secret_dir = Path(args.secret_dir)
    rest_secret = _read_non_empty(
        secret_dir / "turn-rest-shared-secret",
        "TURN REST shared secret",
    )
    coturn_secret = _read_non_empty(
        secret_dir / "coturn-auth-secret",
        "Coturn auth secret",
    )
    if rest_secret != coturn_secret:
        raise RuntimeError("TURN REST and Coturn auth secrets must match")
    _read_non_empty(secret_dir / "gateway-internal-token", "Gateway internal token")
    host_agent_token = _read_non_empty(
        secret_dir / "host-agent-token",
        "host external-agent token",
    )
    try:
        agent_tokens = json.loads(
            _read_non_empty(
                secret_dir / "connectivity-agent-tokens.json",
                "external-agent token map",
            )
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError("external-agent token map is invalid JSON") from exc
    if not isinstance(agent_tokens, dict):
        raise RuntimeError("external-agent token map must be a JSON object")
    if agent_tokens.get(args.required_vantage) != host_agent_token:
        raise RuntimeError("host external-agent token does not match the token map")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--secret-dir", required=True)
    parser.add_argument("--credential-revision", required=True)
    parser.add_argument("--operator-image", required=True)
    parser.add_argument("--coturn-image", required=True)
    parser.add_argument("--relay-port-min", type=int, required=True)
    parser.add_argument("--relay-port-max", type=int, required=True)
    parser.add_argument("--required-vantage", default="host")
    args = parser.parse_args()
    validate(args)


if __name__ == "__main__":
    main()
