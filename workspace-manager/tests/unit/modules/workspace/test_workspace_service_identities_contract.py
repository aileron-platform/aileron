from __future__ import annotations

import json
from pathlib import Path

from app.modules.workspace.service_identities import workspace_service_identity


def test_workspace_service_identity_matches_canonical_vectors() -> None:
    contract_path = Path(
        "/repo-root/contracts/workspace-service-identities/registry.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert contract["contractVersion"] == "1"
    for vector in contract["vectors"]:
        for identity, expected in vector["expected"].items():
            actual = workspace_service_identity(
                identity,
                vector["workspaceId"],
                vector["namespace"],
            )
            assert actual.service_name == expected["serviceName"]
            assert actual.fqdn == expected["fqdn"]
            assert actual.port == expected["port"]
            assert actual.url == expected["url"]
