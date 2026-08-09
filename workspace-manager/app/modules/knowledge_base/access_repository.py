"""Resolve Knowledge Base access without depending on feature workflows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSnapshot,
    ResourceAccessSource,
    highest_role,
    normalize_resource_role,
)


class KnowledgeBaseAccessResolver:
    """Resolve one principal's complete Knowledge Base access snapshot."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve(
        self,
        *,
        knowledge_base_id: str,
        user_id: str,
    ) -> ResourceAccessSnapshot | None:
        knowledge_base = self.db.get(db_models.KnowledgeBase, knowledge_base_id)
        if knowledge_base is None:
            return None
        if knowledge_base.owner_id == user_id:
            return ResourceAccessSnapshot(
                access_role=ResourceAccessRole.OWNER,
                access_source=ResourceAccessSource.OWNED,
                access_sources=(ResourceAccessSource.OWNED,),
            )

        direct_share = self.db.scalar(
            select(db_models.KnowledgeBaseShare).where(
                db_models.KnowledgeBaseShare.kb_id == knowledge_base_id,
                db_models.KnowledgeBaseShare.target_type == "user",
                db_models.KnowledgeBaseShare.target_id == user_id,
            )
        )
        group_shares = self.db.scalars(
            select(db_models.KnowledgeBaseShare)
            .join(
                db_models.UserGroupMember,
                db_models.UserGroupMember.group_id
                == db_models.KnowledgeBaseShare.target_id,
            )
            .where(
                db_models.KnowledgeBaseShare.kb_id == knowledge_base_id,
                db_models.KnowledgeBaseShare.target_type == "user_group",
                db_models.UserGroupMember.user_id == user_id,
            )
        ).all()
        contributions: list[tuple[ResourceAccessRole, ResourceAccessSource]] = []
        if direct_share is not None:
            direct_role = normalize_resource_role(direct_share.role)
            if direct_role is not None:
                contributions.append((direct_role, ResourceAccessSource.DIRECT_SHARE))
        contributions.extend(
            (role, ResourceAccessSource.GROUP_SHARE)
            for role in (normalize_resource_role(share.role) for share in group_shares)
            if role is not None
        )
        if knowledge_base.visibility == "public":
            contributions.append(
                (ResourceAccessRole.READER, ResourceAccessSource.PUBLIC)
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


__all__ = ["KnowledgeBaseAccessResolver"]
