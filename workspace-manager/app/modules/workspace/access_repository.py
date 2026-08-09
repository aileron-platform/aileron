"""Reusable workspace visibility and mutation authorization queries."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSnapshot,
    ResourceAccessSource,
    highest_role,
    normalize_resource_role,
    role_satisfies,
)


def _workspace_access_contributions(
    db: Session,
    *,
    workspace: db_models.Workspace,
    user_id: str,
) -> tuple[tuple[ResourceAccessRole, ResourceAccessSource], ...]:
    """Return every effective Workspace role contribution for one principal."""

    if workspace.owner_id == user_id:
        return ((ResourceAccessRole.OWNER, ResourceAccessSource.OWNED),)

    direct_role = db.scalar(
        select(db_models.WorkspaceShare.role).where(
            db_models.WorkspaceShare.workspace_id == workspace.id,
            db_models.WorkspaceShare.target_type == "user",
            db_models.WorkspaceShare.target_id == user_id,
        )
    )
    group_roles = db.scalars(
        select(db_models.WorkspaceShare.role)
        .join(
            db_models.UserGroupMember,
            db_models.UserGroupMember.group_id == db_models.WorkspaceShare.target_id,
        )
        .where(
            db_models.WorkspaceShare.workspace_id == workspace.id,
            db_models.WorkspaceShare.target_type == "user_group",
            db_models.UserGroupMember.user_id == user_id,
        )
    ).all()
    contributions: list[tuple[ResourceAccessRole, ResourceAccessSource]] = []
    normalized_direct_role = normalize_resource_role(direct_role)
    if normalized_direct_role is not None:
        contributions.append(
            (normalized_direct_role, ResourceAccessSource.DIRECT_SHARE)
        )
    contributions.extend(
        (role, ResourceAccessSource.GROUP_SHARE)
        for role in (normalize_resource_role(value) for value in group_roles)
        if role is not None
    )
    return tuple(contributions)


def visible_workspace_ids(user_id: str):
    """Return a scalar select of workspaces visible to one actor."""

    direct_shared_ids = select(db_models.WorkspaceShare.workspace_id).where(
        db_models.WorkspaceShare.target_type == "user",
        db_models.WorkspaceShare.target_id == user_id,
    )
    group_shared_ids = (
        select(db_models.WorkspaceShare.workspace_id)
        .join(
            db_models.UserGroupMember,
            db_models.UserGroupMember.group_id == db_models.WorkspaceShare.target_id,
        )
        .where(
            db_models.WorkspaceShare.target_type == "user_group",
            db_models.UserGroupMember.user_id == user_id,
        )
    )
    return select(db_models.Workspace.id).where(
        or_(
            db_models.Workspace.owner_id == user_id,
            db_models.Workspace.id.in_(direct_shared_ids),
            db_models.Workspace.id.in_(group_shared_ids),
        )
    )


class WorkspaceAccessResolver:
    """Resolve one principal's complete Workspace access snapshot."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve(
        self,
        *,
        workspace: db_models.Workspace,
        user_id: str,
    ) -> ResourceAccessSnapshot | None:
        contributions = list(
            _workspace_access_contributions(
                self.db,
                workspace=workspace,
                user_id=user_id,
            )
        )
        role = highest_role(role for role, _source in contributions)
        if role is None:
            return None
        primary_source = next(
            source
            for contributed_role, source in contributions
            if contributed_role is role
        )
        sources = tuple(
            dict.fromkeys(
                [
                    primary_source,
                    *(source for _role, source in contributions),
                ]
            )
        )
        return ResourceAccessSnapshot(
            access_role=role,
            access_source=primary_source,
            access_sources=sources,
        )


class WorkspaceAccessRepository:
    """Read workspace access without coupling callers to a feature repository."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def actor_can_view(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> bool:
        """Return whether the actor has Reader-or-higher workspace access."""

        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            return False
        access = WorkspaceAccessResolver(self.db).resolve(
            workspace=workspace,
            user_id=user_id,
        )
        return access is not None

    def actor_can_mutate(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> bool:
        """Return whether the actor has Manager-or-higher workspace access."""

        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            return False
        access = WorkspaceAccessResolver(self.db).resolve(
            workspace=workspace,
            user_id=user_id,
        )
        return access is not None and role_satisfies(
            access.access_role,
            ResourceAccessRole.MANAGER,
        )
