from __future__ import annotations

from dataclasses import dataclass

from app.modules.workspace.service_identities_generated import (
    CANONICAL_WORKSPACE_SERVICE_DEFINITIONS,
)


@dataclass(frozen=True)
class WorkspaceServiceIdentity:
    service_name: str
    fqdn: str
    port: int
    url: str


def workspace_service_identity(
    identity: str,
    workspace_id: str,
    namespace: str,
) -> WorkspaceServiceIdentity:
    try:
        service_component, port = CANONICAL_WORKSPACE_SERVICE_DEFINITIONS[identity]
    except KeyError as error:
        raise ValueError(f"unknown workspace service identity {identity!r}") from error
    if not workspace_id or not namespace:
        raise ValueError("workspace ID and namespace are required")
    service_name = f"{service_component}-{workspace_id}"
    fqdn = f"{service_name}.{namespace}.svc.cluster.local"
    return WorkspaceServiceIdentity(
        service_name=service_name,
        fqdn=fqdn,
        port=port,
        url=f"http://{fqdn}:{port}",
    )
