"""Manager-owned repository target resolvers."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from aileron_git_core.contracts import LockScopeKeys, RepositoryTarget


def _managed_child(root: Path, identity: str) -> Path:
    """Resolve one managed child without accepting path-shaped identities."""
    if not identity or Path(identity).name != identity or identity in {".", ".."}:
        raise ValueError("repository_target_invalid")
    resolved_root = root.resolve()
    resolved_target = (resolved_root / identity).resolve()
    if resolved_target.parent != resolved_root:
        raise ValueError("repository_target_invalid")
    return resolved_target


class KnowledgeBaseRepositoryTargetResolver:
    """Resolve a Knowledge Base to its single managed Git repository."""

    def __init__(self, storage_root: Path) -> None:
        self._storage_root = storage_root

    def resolve(
        self,
        knowledge_base_id: str,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> RepositoryTarget:
        identity = f"knowledge-base:{knowledge_base_id}"
        return RepositoryTarget(
            root=_managed_child(self._storage_root, knowledge_base_id),
            lock_scope_keys=LockScopeKeys(
                common_repository=identity,
                working_tree_target=identity,
            ),
            environment=environment or {},
        )


class MarketplaceRepositoryTargetResolver:
    """Resolve the single system-managed Marketplace registry repository."""

    def __init__(self, storage_root: Path) -> None:
        self._storage_root = storage_root

    def resolve(
        self,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> RepositoryTarget:
        identity = "marketplace:registry"
        return RepositoryTarget(
            root=_managed_child(self._storage_root, "registry"),
            lock_scope_keys=LockScopeKeys(
                common_repository=identity,
                working_tree_target=identity,
            ),
            environment=environment or {},
        )

    def resolve_staging_clone(
        self,
        staging_root: Path,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> RepositoryTarget:
        """Resolve an internally-created clone staging directory."""
        managed_parent = self._storage_root.resolve().parent
        resolved = staging_root.resolve()
        if resolved.name != "registry" or managed_parent not in resolved.parents:
            raise ValueError("repository_target_invalid")
        identity = "marketplace:registry"
        return RepositoryTarget(
            root=resolved,
            lock_scope_keys=LockScopeKeys(
                common_repository=identity,
                working_tree_target=identity,
            ),
            environment=environment or {},
        )
