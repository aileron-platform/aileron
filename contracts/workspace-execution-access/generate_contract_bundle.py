#!/usr/bin/env python3
"""Generate and verify the Workspace Execution Access contract bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUNDLE_OUTPUT = ROOT / "generated" / "contract-bundle.json"
SOURCES = (
    "claims.schema.json",
    "route-inventory.json",
    "conformance-vectors.json",
)
EXPECTED_ACTIONS = {
    "runtime_read",
    "runtime_write",
    "workspace_settings",
    "terminal",
    "agent",
    "automation",
    "browser_automation",
}
EXPECTED_AUDIENCES = {"workspace-runtime", "workspace-terminal"}


def _load(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _validate_sources() -> None:
    schema = _load("claims.schema.json")
    inventory = _load("route-inventory.json")
    vectors = _load("conformance-vectors.json")

    if schema["properties"]["kind"]["const"] != vectors["tokenKind"]:
        raise SystemExit("Execution Grant token kind drifted")
    if (
        schema["x-aileron-token-ttl-seconds"] != 60
        or vectors["ttlSeconds"] != 60
    ):
        raise SystemExit("Execution Grant TTL must be exactly 60 seconds")
    audiences = set(schema["properties"]["aud"]["enum"])
    if audiences != EXPECTED_AUDIENCES or set(inventory["audiences"]) != audiences:
        raise SystemExit("Execution Grant audience inventory drifted")
    actions = set(schema["properties"]["actions"]["items"]["enum"])
    inventory_actions = {
        action
        for audience in inventory["audiences"].values()
        for action in audience["allowedActions"]
    }
    if actions != EXPECTED_ACTIONS or inventory_actions != actions:
        raise SystemExit("Execution Grant action inventory drifted")
    required_cases = {
        "valid-runtime",
        "wrong-audience-runtime",
        "wrong-action-runtime",
        "empty-actions-runtime",
        "all-action-runtime",
        "expired-runtime",
        "instance-mismatch-runtime",
        "revision-mismatch-runtime",
        "valid-terminal",
        "wrong-audience-terminal",
        "wrong-action-terminal",
        "empty-actions-terminal",
        "all-action-terminal",
        "expired-terminal",
        "instance-mismatch-terminal",
        "revision-mismatch-terminal",
    }
    case_names = {case["name"] for case in vectors["verificationCases"]}
    if not required_cases.issubset(case_names):
        raise SystemExit("Execution Grant conformance matrix is incomplete")


def generate_bundle() -> bytes:
    _validate_sources()
    bundle = {
        "generated": True,
        "message": "DO NOT EDIT; run generate_contract_bundle.py",
        "contracts": {name: _load(name) for name in SOURCES},
    }
    return (json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    expected = generate_bundle()
    if arguments.check:
        if not BUNDLE_OUTPUT.exists() or BUNDLE_OUTPUT.read_bytes() != expected:
            raise SystemExit(f"Execution Grant generated output drifted: {BUNDLE_OUTPUT}")
        return 0
    BUNDLE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE_OUTPUT.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
