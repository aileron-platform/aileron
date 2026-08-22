"""Versioned installation Namespace policy contract tests."""

from __future__ import annotations

from scripts.deploy.rke2 import namespace_policy as MODULE


def test_namespace_policy_is_an_independent_canonical_versioned_document() -> None:
    document = MODULE.namespace_policy_document()

    assert document["contractVersion"] == "aileron-installation-namespace-policy/v1"
    assert [(item["name"], item["lifecycle"]) for item in document["namespaces"]] == [
        ("aileron-acceptance-system", "retained"),
        ("aileron-backend-attestor-system", "retained"),
        ("aileron-identity-system", "resettable"),
        ("aileron-turn-system", "resettable"),
        ("workspace-system", "resettable"),
    ]
    assert MODULE.load_namespace_policy(MODULE.canonical_policy_bytes()) == document
