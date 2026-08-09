"""Load the shared Workspace availability contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


@dataclass(frozen=True)
class WorkspaceAvailabilityReasonContract:
    """Normalized semantics for one stable availability reason code."""

    availability: str
    scope: str
    http_status: int
    retryable: bool
    default_allowed_actions: tuple[str, ...]

    @classmethod
    def from_manifest(
        cls,
        value: dict[str, Any],
    ) -> WorkspaceAvailabilityReasonContract:
        return cls(
            availability=str(value["availability"]),
            scope=str(value["scope"]),
            http_status=int(value["httpStatus"]),
            retryable=bool(value["retryable"]),
            default_allowed_actions=tuple(value["defaultAllowedActions"]),
        )


def _contract_path() -> Path:
    configured_path = get_settings().WORKSPACE_AVAILABILITY_CONTRACT_PATH
    if configured_path:
        return Path(configured_path)

    candidates = (
        Path("/repo-root/contracts/workspace-availability.json"),
        Path("/contracts/workspace-availability.json"),
        Path(__file__).resolve().parents[3]
        / "contracts"
        / "workspace-availability.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Workspace availability contract is unavailable")


@lru_cache(maxsize=1)
def load_workspace_availability_contract() -> dict[str, Any]:
    return json.loads(_contract_path().read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def workspace_availability_reason_contracts() -> dict[
    str,
    WorkspaceAvailabilityReasonContract,
]:
    manifest = load_workspace_availability_contract()
    return {
        code: WorkspaceAvailabilityReasonContract.from_manifest(value)
        for code, value in manifest["reasonCodes"].items()
    }


def workspace_availability_reason(
    code: str,
) -> WorkspaceAvailabilityReasonContract:
    try:
        return workspace_availability_reason_contracts()[code]
    except KeyError as exc:
        raise RuntimeError(
            f"Workspace availability reason is not declared: {code}"
        ) from exc


__all__ = [
    "WorkspaceAvailabilityReasonContract",
    "load_workspace_availability_contract",
    "workspace_availability_reason",
    "workspace_availability_reason_contracts",
]
