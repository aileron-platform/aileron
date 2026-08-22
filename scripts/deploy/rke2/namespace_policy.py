#!/usr/bin/env python3
"""Publish the independent versioned HomeLab Namespace policy."""

from __future__ import annotations

import argparse
import json
from typing import Any

if __package__:
    from . import namespace_contract as NAMESPACE_CONTRACT
else:
    import namespace_contract as NAMESPACE_CONTRACT


CONTRACT_VERSION = "aileron-installation-namespace-policy/v1"
LIFECYCLES = {
    "aileron-acceptance-system": "retained",
    "aileron-backend-attestor-system": "retained",
    "aileron-identity-system": "resettable",
    "aileron-turn-system": "resettable",
    "workspace-system": "resettable",
}


class NamespacePolicyError(ValueError):
    """Raised when the canonical Namespace policy is invalid."""


def namespace_policy_document() -> dict[str, Any]:
    """Return the code-owned Namespace lifecycle and security policy."""

    if set(LIFECYCLES) != set(NAMESPACE_CONTRACT.NAMESPACE_PROFILES):
        raise NamespacePolicyError("Namespace policy inventory is incomplete")
    return {
        "contractVersion": CONTRACT_VERSION,
        "namespaces": [
            {
                "name": name,
                "lifecycle": lifecycle,
                "labels": NAMESPACE_CONTRACT.profile_labels(name),
            }
            for name, lifecycle in LIFECYCLES.items()
        ],
    }


def canonical_policy_bytes() -> bytes:
    """Return the exact canonical bytes signed by reset evidence."""

    return (
        json.dumps(namespace_policy_document(), separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()


def load_namespace_policy(raw: bytes) -> dict[str, Any]:
    """Validate one exact current Namespace policy document."""

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        document = json.loads(raw, object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise NamespacePolicyError("Namespace policy is invalid") from exc
    if raw != canonical_policy_bytes() or document != namespace_policy_document():
        raise NamespacePolicyError("Namespace policy does not match current code")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", action="store_true", dest="print_policy")
    arguments = parser.parse_args(argv)
    if arguments.print_policy:
        print(canonical_policy_bytes().decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
