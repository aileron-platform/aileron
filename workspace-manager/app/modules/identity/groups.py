"""DB-backed user group service."""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, NoReturn
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.identity.group_models import (
    UserGroup,
    UserGroupListResponse,
    UserGroupMember,
    UserGroupMemberAddResponse,
    UserGroupMemberCandidate,
    UserGroupMemberCandidateListResponse,
    UserGroupMemberFailure,
    UserGroupMemberListResponse,
    UserGroupMemberRemoveResponse,
)
from app.modules.audit.events import AuditEventService
from app.modules.identity.platform_role import PLATFORM_ROLES
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy
from app.modules.workspace.group_access_convergence import (
    GroupWorkspaceAuthorizationConvergence,
)

GROUP_INVALID_REQUEST = "KB_GROUP_ADMIN_INVALID_REQUEST"
GROUP_INVALID_PAGE_REQUEST = "KB_GROUP_ADMIN_INVALID_PAGE_REQUEST"
GROUP_DUPLICATE_NAME = "KB_GROUP_ADMIN_DUPLICATE_NAME"
GROUP_NOT_FOUND = "KB_GROUP_ADMIN_NOT_FOUND"
GROUP_MEMBER_NOT_FOUND = "KB_GROUP_ADMIN_MEMBER_NOT_FOUND"
GROUP_MEMBER_NOT_AUTHORIZABLE = "KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE"

logger = logging.getLogger(__name__)

ACCOUNT_STATES = frozenset(
    {
        "active",
        "local_disabled",
        "identity_disabled",
        "sync_failed",
        "shadow_missing",
    }
)
ROLE_STATUSES = frozenset({"valid", "missing", "multiple"})


class UserGroupService:
    """Manage product user groups and memberships."""

    def __init__(
        self,
        db: Session,
        *,
        authorization_policy: UserAuthorizationPolicy | None = None,
    ) -> None:
        self.db = db
        self.audit_events = AuditEventService(db)
        self.authorization_policy = authorization_policy or UserAuthorizationPolicy()
        self.workspace_authorization = GroupWorkspaceAuthorizationConvergence(db)

    def list_groups(
        self,
        *,
        q: str | None = None,
        member_count_range: str | None = None,
        has_description: bool | None = None,
        updated_within_days: int | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "name",
        sort_direction: str = "asc",
    ) -> UserGroupListResponse:
        self._validate_page(page=page, page_size=page_size)
        self._validate_q(q)
        if member_count_range not in {None, "empty", "1_10", "gt_10"}:
            self._invalid_page_request()
        if updated_within_days is not None and not 1 <= updated_within_days <= 365:
            self._invalid_page_request()

        member_counts = (
            select(
                db_models.UserGroupMember.group_id.label("group_id"),
                func.count(db_models.UserGroupMember.id).label("member_count"),
            )
            .group_by(db_models.UserGroupMember.group_id)
            .subquery()
        )
        share_counts = (
            select(
                db_models.KnowledgeBaseShare.target_id.label("group_id"),
                func.count(db_models.KnowledgeBaseShare.id).label("share_count"),
            )
            .where(db_models.KnowledgeBaseShare.target_type == "user_group")
            .group_by(db_models.KnowledgeBaseShare.target_id)
            .subquery()
        )
        member_count = func.coalesce(member_counts.c.member_count, 0)
        share_count = func.coalesce(share_counts.c.share_count, 0)
        query = (
            select(
                db_models.UserGroup.id.label("group_id"),
                db_models.UserGroup.name.label("group_name"),
                db_models.UserGroup.description.label("group_description"),
                db_models.UserGroup.created_at.label("group_created_at"),
                db_models.UserGroup.updated_at.label("group_updated_at"),
                member_count.label("member_count"),
                share_count.label("share_count"),
            )
            .outerjoin(
                member_counts, member_counts.c.group_id == db_models.UserGroup.id
            )
            .outerjoin(share_counts, share_counts.c.group_id == db_models.UserGroup.id)
        )

        normalized_q = (q or "").strip()
        if normalized_q:
            pattern = self._search_pattern(normalized_q)
            query = query.where(
                or_(
                    db_models.UserGroup.name.ilike(pattern, escape="\\"),
                    db_models.UserGroup.description.ilike(pattern, escape="\\"),
                )
            )
        if member_count_range == "empty":
            query = query.where(member_count == 0)
        elif member_count_range == "1_10":
            query = query.where(member_count.between(1, 10))
        elif member_count_range == "gt_10":
            query = query.where(member_count >= 11)
        if has_description is True:
            query = query.where(func.trim(db_models.UserGroup.description) != "")
        elif has_description is False:
            query = query.where(
                or_(
                    db_models.UserGroup.description.is_(None),
                    func.trim(db_models.UserGroup.description) == "",
                )
            )
        if updated_within_days is not None:
            threshold = datetime.now(timezone.utc) - timedelta(days=updated_within_days)
            query = query.where(db_models.UserGroup.updated_at >= threshold)

        sort_columns = {
            "name": func.lower(db_models.UserGroup.name),
            "memberCount": member_count,
            "createdAt": db_models.UserGroup.created_at,
            "updatedAt": db_models.UserGroup.updated_at,
        }
        rows, total = self._execute_page(
            query,
            sort_columns=sort_columns,
            sort_by=sort_by,
            sort_direction=sort_direction,
            tie_breaker=db_models.UserGroup.id,
            page=page,
            page_size=page_size,
        )
        return UserGroupListResponse(
            items=[
                UserGroup(
                    id=str(row["group_id"]),
                    name=str(row["group_name"]),
                    description=row["group_description"],
                    memberCount=int(row["member_count"]),
                    knowledgeBaseShareCount=int(row["share_count"]),
                    createdAt=row["group_created_at"],
                    updatedAt=row["group_updated_at"],
                )
                for row in rows
            ],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def get_group(self, *, group_id: str) -> UserGroup:
        group = self._get_group(group_id)
        member_count = self.db.scalar(
            select(func.count(db_models.UserGroupMember.id)).where(
                db_models.UserGroupMember.group_id == group_id
            )
        )
        share_count = self.db.scalar(
            select(func.count(db_models.KnowledgeBaseShare.id)).where(
                db_models.KnowledgeBaseShare.target_type == "user_group",
                db_models.KnowledgeBaseShare.target_id == group_id,
            )
        )
        return self._to_group(
            group,
            member_count=int(member_count or 0),
            knowledge_base_share_count=int(share_count or 0),
        )

    def create_group(
        self,
        *,
        name: str,
        description: str | None,
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> UserGroup:
        correlation_id, root_correlation_id = self._correlation_ids(
            correlation_id, root_correlation_id
        )
        group = db_models.UserGroup(
            id=str(uuid4()),
            name=name,
            description=description,
        )
        try:
            self.db.add(group)
            self.db.flush()
            self._record_audit(
                event_type="user_group.created",
                actor_user_id=actor_user_id,
                target_id=group.id,
                action="create_group",
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"changed_fields": ["description", "name"]},
            )
            self.db.refresh(group)
            result = self._to_group(
                group,
                member_count=0,
                knowledge_base_share_count=0,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            if self._is_duplicate_group_name(exc):
                self._persist_failure_audit(
                    event_type="user_group.created",
                    actor_user_id=actor_user_id,
                    target_type="user_group",
                    target_id=group.id,
                    action="create_group",
                    error_code=GROUP_DUPLICATE_NAME,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=GROUP_DUPLICATE_NAME,
                ) from exc
            self._persist_failure_audit(
                event_type="user_group.created",
                actor_user_id=actor_user_id,
                target_type="user_group",
                target_id=group.id,
                action="create_group",
                error_code=GROUP_INVALID_REQUEST,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            raise
        except Exception as exc:
            self.db.rollback()
            self._persist_failure_audit(
                event_type="user_group.created",
                actor_user_id=actor_user_id,
                target_type="user_group",
                target_id=group.id,
                action="create_group",
                error_code=self._failure_code(exc, fallback=GROUP_INVALID_REQUEST),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            raise

    def update_group(
        self,
        *,
        group_id: str,
        name: str | None,
        description: str | None,
        name_provided: bool,
        description_provided: bool,
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> UserGroup:
        correlation_id, root_correlation_id = self._correlation_ids(
            correlation_id, root_correlation_id
        )
        try:
            if not name_provided and not description_provided:
                self._invalid_request()
            group = self._get_group(group_id, for_update=True)
            changed_fields: list[str] = []
            if name_provided:
                if name is None:
                    self._invalid_request()
                group.name = name
                changed_fields.append("name")
            if description_provided:
                group.description = description
                changed_fields.append("description")
            group.updated_at = datetime.now(timezone.utc)
            self.db.flush()
            self._record_audit(
                event_type="user_group.updated",
                actor_user_id=actor_user_id,
                target_id=group.id,
                action="update_group",
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"changed_fields": sorted(changed_fields)},
            )
            result = self.get_group(group_id=group.id)
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            if self._is_duplicate_group_name(exc):
                self._persist_failure_audit(
                    event_type="user_group.updated",
                    actor_user_id=actor_user_id,
                    target_type="user_group",
                    target_id=group_id,
                    action="update_group",
                    error_code=GROUP_DUPLICATE_NAME,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=GROUP_DUPLICATE_NAME,
                ) from exc
            self._persist_failure_audit(
                event_type="user_group.updated",
                actor_user_id=actor_user_id,
                target_type="user_group",
                target_id=group_id,
                action="update_group",
                error_code=GROUP_INVALID_REQUEST,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            raise
        except Exception as exc:
            self.db.rollback()
            self._persist_failure_audit(
                event_type="user_group.updated",
                actor_user_id=actor_user_id,
                target_type="user_group",
                target_id=group_id,
                action="update_group",
                error_code=self._failure_code(exc, fallback=GROUP_INVALID_REQUEST),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            raise

    def delete_group(
        self,
        *,
        group_id: str,
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> None:
        correlation_id, root_correlation_id = self._correlation_ids(
            correlation_id, root_correlation_id
        )
        delivery = None
        try:
            group = self._get_group(group_id, for_update=True)
            members = list(
                self.db.scalars(
                    select(db_models.UserGroupMember)
                    .where(db_models.UserGroupMember.group_id == group_id)
                    .order_by(db_models.UserGroupMember.user_id)
                    .with_for_update()
                ).all()
            )
            knowledge_base_shares = list(
                self.db.scalars(
                    select(db_models.KnowledgeBaseShare)
                    .where(
                        db_models.KnowledgeBaseShare.target_type == "user_group",
                        db_models.KnowledgeBaseShare.target_id == group_id,
                    )
                    .order_by(db_models.KnowledgeBaseShare.kb_id)
                    .with_for_update()
                ).all()
            )

            def delete_group_resources(workspace_change) -> None:
                for share in workspace_change.group_shares:
                    self.db.delete(share)
                for share in knowledge_base_shares:
                    self.db.delete(share)
                for member in members:
                    self.db.delete(member)
                self.db.delete(group)

            delivery = self.workspace_authorization.apply_reduction_in_transaction(
                group_id=group_id,
                principal_user_ids=[member.user_id for member in members],
                mutation=delete_group_resources,
                actor_user_id=actor_user_id,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                reason="user_group_deleted",
            )
            self._record_audit(
                event_type="user_group.deleted",
                actor_user_id=actor_user_id,
                target_id=group_id,
                action="delete_group",
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self._persist_failure_audit(
                event_type="user_group.deleted",
                actor_user_id=actor_user_id,
                target_type="user_group",
                target_id=group_id,
                action="delete_group",
                error_code=self._failure_code(exc, fallback=GROUP_INVALID_REQUEST),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            raise
        if delivery is not None:
            delivery.deliver()

    def list_members(
        self,
        *,
        group_id: str,
        q: str | None = None,
        role: str | None = None,
        account_state: str | None = None,
        source: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "username",
        sort_direction: str = "asc",
    ) -> UserGroupMemberListResponse:
        self._get_group(group_id)
        self._validate_page(page=page, page_size=page_size)
        self._validate_q(q)
        if role is not None and role not in PLATFORM_ROLES:
            self._invalid_page_request()
        if source not in {None, "manual"}:
            self._invalid_page_request()
        account_states = self._parse_csv_filter(account_state, ACCOUNT_STATES)

        query = (
            select(
                db_models.User.id.label("user_id"),
                db_models.User.username.label("username"),
                db_models.User.email.label("email"),
                db_models.User.first_name.label("first_name"),
                db_models.User.last_name.label("last_name"),
                db_models.User.is_active.label("is_active"),
                db_models.User.identity_enabled.label("identity_enabled"),
                db_models.User.sync_status.label("sync_status"),
                db_models.User.platform_role.label("platform_role"),
                db_models.User.role_status.label("role_status"),
                db_models.UserGroupMember.created_at.label("joined_at"),
                db_models.User.updated_at.label("user_updated_at"),
            )
            .join(
                db_models.User, db_models.User.id == db_models.UserGroupMember.user_id
            )
            .where(db_models.UserGroupMember.group_id == group_id)
        )
        query = self._apply_user_filters(
            query,
            q=q,
            role=role,
            account_states=account_states,
            role_statuses=None,
        )
        sort_columns = {
            "username": func.lower(db_models.User.username),
            "email": func.lower(db_models.User.email),
            "joinedAt": db_models.UserGroupMember.created_at,
            "updatedAt": db_models.User.updated_at,
        }
        rows, total = self._execute_page(
            query,
            sort_columns=sort_columns,
            sort_by=sort_by,
            sort_direction=sort_direction,
            tie_breaker=db_models.User.id,
            page=page,
            page_size=page_size,
        )
        return UserGroupMemberListResponse(
            items=[self._member_from_row(row) for row in rows],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def list_member_candidates(
        self,
        *,
        group_id: str,
        q: str | None = None,
        membership: str = "not_member",
        role: str | None = None,
        account_state: str | None = None,
        role_status: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "username",
        sort_direction: str = "asc",
    ) -> UserGroupMemberCandidateListResponse:
        self._get_group(group_id)
        self._validate_page(page=page, page_size=page_size)
        self._validate_q(q)
        if membership not in {"not_member", "member", "all"}:
            self._invalid_page_request()
        if role is not None and role not in PLATFORM_ROLES:
            self._invalid_page_request()
        account_states = self._parse_csv_filter(account_state, ACCOUNT_STATES)
        role_statuses = self._parse_csv_filter(role_status, ROLE_STATUSES)

        membership_join = and_(
            db_models.UserGroupMember.group_id == group_id,
            db_models.UserGroupMember.user_id == db_models.User.id,
        )
        query = select(
            db_models.User.id.label("user_id"),
            db_models.User.username.label("username"),
            db_models.User.email.label("email"),
            db_models.User.first_name.label("first_name"),
            db_models.User.last_name.label("last_name"),
            db_models.User.is_active.label("is_active"),
            db_models.User.identity_enabled.label("identity_enabled"),
            db_models.User.sync_status.label("sync_status"),
            db_models.User.platform_role.label("platform_role"),
            db_models.User.role_status.label("role_status"),
            db_models.User.created_at.label("user_created_at"),
            db_models.User.updated_at.label("user_updated_at"),
            db_models.UserGroupMember.id.label("membership_id"),
        ).outerjoin(
            db_models.UserGroupMember,
            membership_join,
        )
        if membership == "member":
            query = query.where(db_models.UserGroupMember.id.is_not(None))
        elif membership == "not_member":
            query = query.where(db_models.UserGroupMember.id.is_(None))
        query = self._apply_user_filters(
            query,
            q=q,
            role=role,
            account_states=account_states,
            role_statuses=role_statuses,
        )
        sort_columns = {
            "username": func.lower(db_models.User.username),
            "email": func.lower(db_models.User.email),
            "createdAt": db_models.User.created_at,
            "updatedAt": db_models.User.updated_at,
        }
        rows, total = self._execute_page(
            query,
            sort_columns=sort_columns,
            sort_by=sort_by,
            sort_direction=sort_direction,
            tie_breaker=db_models.User.id,
            page=page,
            page_size=page_size,
        )
        return UserGroupMemberCandidateListResponse(
            items=[self._candidate_from_row(row) for row in rows],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def add_members(
        self,
        *,
        group_id: str,
        user_ids: list[str],
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> UserGroupMemberAddResponse:
        correlation_id, root_correlation_id = self._correlation_ids(
            correlation_id, root_correlation_id
        )
        try:
            self._validate_user_ids(user_ids)
            group = self._get_group(group_id, for_update=True)
            existing_user_ids = set(
                self.db.scalars(
                    select(db_models.UserGroupMember.user_id)
                    .where(
                        db_models.UserGroupMember.group_id == group_id,
                        db_models.UserGroupMember.user_id.in_(user_ids),
                    )
                    .order_by(db_models.UserGroupMember.user_id)
                    .with_for_update()
                ).all()
            )
            users = {
                user.id: user
                for user in self.db.scalars(
                    select(db_models.User)
                    .where(db_models.User.id.in_(user_ids))
                    .order_by(db_models.User.id)
                    .with_for_update()
                ).all()
            }
            added: list[str] = []
            skipped: list[str] = []
            failed: list[UserGroupMemberFailure] = []

            for user_id in user_ids:
                if user_id in existing_user_ids:
                    skipped.append(user_id)
                    continue
                user = users.get(user_id)
                if user is None:
                    failed.append(
                        UserGroupMemberFailure(
                            userId=user_id,
                            errorCode=GROUP_MEMBER_NOT_FOUND,
                        )
                    )
                    continue
                if not self.authorization_policy.is_authorized(user):
                    failed.append(
                        UserGroupMemberFailure(
                            userId=user_id,
                            errorCode=GROUP_MEMBER_NOT_AUTHORIZABLE,
                        )
                    )
                    continue
                added.append(user_id)

            for user_id in added:
                self.db.add(
                    db_models.UserGroupMember(
                        id=str(uuid4()),
                        group_id=group_id,
                        user_id=user_id,
                        created_by_id=actor_user_id,
                    )
                )
            if added:
                group.updated_at = datetime.now(timezone.utc)
            self.db.flush()
            for user_id in added:
                self._record_member_audit(
                    event_type="user_group.member_added",
                    actor_user_id=actor_user_id,
                    target_user_id=user_id,
                    action="add_member",
                    group_id=group_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                )
            for failure in failed:
                self._record_member_audit(
                    event_type="user_group.member_added",
                    actor_user_id=actor_user_id,
                    target_user_id=failure.user_id,
                    action="add_member",
                    group_id=group_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    result="failure",
                    error_code=failure.error_code,
                )
            self.db.commit()
            return UserGroupMemberAddResponse(
                addedUserIds=added,
                skippedUserIds=skipped,
                failedUsers=failed,
            )
        except Exception as exc:
            self.db.rollback()
            error_code = self._failure_code(exc, fallback=GROUP_INVALID_REQUEST)
            for user_id in dict.fromkeys(user_ids):
                self._persist_failure_audit(
                    event_type="user_group.member_added",
                    actor_user_id=actor_user_id,
                    target_type="user",
                    target_id=user_id,
                    action="add_member",
                    error_code=error_code,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata={"group_id": group_id},
                )
            raise

    def remove_members(
        self,
        *,
        group_id: str,
        user_ids: list[str],
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> UserGroupMemberRemoveResponse:
        correlation_id, root_correlation_id = self._correlation_ids(
            correlation_id, root_correlation_id
        )
        delivery = None
        try:
            self._validate_user_ids(user_ids)
            group = self._get_group(group_id, for_update=True)
            members = {
                member.user_id: member
                for member in self.db.scalars(
                    select(db_models.UserGroupMember)
                    .where(
                        db_models.UserGroupMember.group_id == group_id,
                        db_models.UserGroupMember.user_id.in_(user_ids),
                    )
                    .order_by(db_models.UserGroupMember.user_id)
                    .with_for_update()
                ).all()
            }
            existing_users = set(
                self.db.scalars(
                    select(db_models.User.id).where(db_models.User.id.in_(user_ids))
                ).all()
            )
            removed: list[str] = []
            skipped: list[str] = []
            failed: list[UserGroupMemberFailure] = []
            for user_id in user_ids:
                member = members.get(user_id)
                if member is not None:
                    removed.append(user_id)
                elif user_id in existing_users:
                    skipped.append(user_id)
                else:
                    failed.append(
                        UserGroupMemberFailure(
                            userId=user_id,
                            errorCode=GROUP_MEMBER_NOT_FOUND,
                        )
                    )

            if removed:

                def delete_members(_workspace_change) -> None:
                    for removed_user_id in removed:
                        self.db.delete(members[removed_user_id])
                    group.updated_at = datetime.now(timezone.utc)

                delivery = self.workspace_authorization.apply_reduction_in_transaction(
                    group_id=group_id,
                    principal_user_ids=removed,
                    mutation=delete_members,
                    actor_user_id=actor_user_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    reason="user_group_member_removed",
                )
            for user_id in removed:
                self._record_member_audit(
                    event_type="user_group.member_removed",
                    actor_user_id=actor_user_id,
                    target_user_id=user_id,
                    action="remove_member",
                    group_id=group_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                )
            for failure in failed:
                self._record_member_audit(
                    event_type="user_group.member_removed",
                    actor_user_id=actor_user_id,
                    target_user_id=failure.user_id,
                    action="remove_member",
                    group_id=group_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    result="failure",
                    error_code=failure.error_code,
                )
            self.db.commit()
            result = UserGroupMemberRemoveResponse(
                removedUserIds=removed,
                skippedUserIds=skipped,
                failedUsers=failed,
            )
        except Exception as exc:
            self.db.rollback()
            error_code = self._failure_code(exc, fallback=GROUP_INVALID_REQUEST)
            for user_id in dict.fromkeys(user_ids):
                self._persist_failure_audit(
                    event_type="user_group.member_removed",
                    actor_user_id=actor_user_id,
                    target_type="user",
                    target_id=user_id,
                    action="remove_member",
                    error_code=error_code,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata={"group_id": group_id},
                )
            raise
        if delivery is not None:
            delivery.deliver()
        return result

    def remove_member(
        self,
        *,
        group_id: str,
        user_id: str,
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> None:
        correlation_id, root_correlation_id = self._correlation_ids(
            correlation_id, root_correlation_id
        )
        delivery = None
        try:
            group = self._get_group(group_id, for_update=True)
            member = self.db.scalar(
                select(db_models.UserGroupMember)
                .where(
                    db_models.UserGroupMember.group_id == group_id,
                    db_models.UserGroupMember.user_id == user_id,
                )
                .with_for_update()
            )
            if member is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=GROUP_MEMBER_NOT_FOUND,
                )

            def delete_member(_workspace_change) -> None:
                self.db.delete(member)
                group.updated_at = datetime.now(timezone.utc)

            delivery = self.workspace_authorization.apply_reduction_in_transaction(
                group_id=group_id,
                principal_user_ids=[user_id],
                mutation=delete_member,
                actor_user_id=actor_user_id,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                reason="user_group_member_removed",
            )
            self._record_member_audit(
                event_type="user_group.member_removed",
                actor_user_id=actor_user_id,
                target_user_id=user_id,
                action="remove_member",
                group_id=group_id,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self._persist_failure_audit(
                event_type="user_group.member_removed",
                actor_user_id=actor_user_id,
                target_type="user",
                target_id=user_id,
                action="remove_member",
                error_code=self._failure_code(exc, fallback=GROUP_MEMBER_NOT_FOUND),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"group_id": group_id},
            )
            raise
        if delivery is not None:
            delivery.deliver()

    def _get_group(
        self,
        group_id: str,
        *,
        for_update: bool = False,
    ) -> db_models.UserGroup:
        query = select(db_models.UserGroup).where(db_models.UserGroup.id == group_id)
        if for_update:
            query = query.with_for_update()
        group = self.db.scalar(query)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=GROUP_NOT_FOUND,
            )
        return group

    @staticmethod
    def _to_group(
        group: db_models.UserGroup,
        *,
        member_count: int,
        knowledge_base_share_count: int,
    ) -> UserGroup:
        return UserGroup(
            id=group.id,
            name=group.name,
            description=group.description,
            memberCount=member_count,
            knowledgeBaseShareCount=knowledge_base_share_count,
            createdAt=group.created_at,
            updatedAt=group.updated_at,
        )

    @staticmethod
    def _member_from_row(row: Mapping[str, Any]) -> UserGroupMember:
        return UserGroupMember(
            userId=str(row["user_id"]),
            username=str(row["username"]),
            email=row["email"],
            firstName=row["first_name"],
            lastName=row["last_name"],
            enabled=UserGroupService._enabled_values(row),
            accountState=UserGroupService._account_state_from_row(row),
            role=row["platform_role"],
            roleStatus=row["role_status"],
            source="manual",
            joinedAt=row["joined_at"],
            updatedAt=row["user_updated_at"],
        )

    @staticmethod
    def _candidate_from_row(row: Mapping[str, Any]) -> UserGroupMemberCandidate:
        return UserGroupMemberCandidate(
            userId=str(row["user_id"]),
            username=str(row["username"]),
            email=row["email"],
            firstName=row["first_name"],
            lastName=row["last_name"],
            enabled=UserGroupService._enabled_values(row),
            accountState=UserGroupService._account_state_from_row(row),
            role=row["platform_role"],
            roleStatus=row["role_status"],
            membershipStatus=(
                "member" if row["membership_id"] is not None else "not_member"
            ),
            createdAt=row["user_created_at"],
            updatedAt=row["user_updated_at"],
        )

    @staticmethod
    def _enabled_values(row: Mapping[str, Any]) -> bool:
        return bool(
            row["is_active"]
            and row["identity_enabled"]
            and row["sync_status"] in {"synced", "local_shadow_imported"}
        )

    @staticmethod
    def _account_state_from_row(
        row: Mapping[str, Any],
    ) -> Literal[
        "active",
        "local_disabled",
        "identity_disabled",
        "sync_failed",
        "shadow_missing",
    ]:
        if row["sync_status"] == "identity_sync_failed":
            return "sync_failed"
        if row["sync_status"] == "local_shadow_missing":
            return "shadow_missing"
        if not row["is_active"]:
            return "local_disabled"
        if not row["identity_enabled"]:
            return "identity_disabled"
        return "active"

    @staticmethod
    def _account_state_condition(account_state: str) -> Any:
        normal_sync = db_models.User.sync_status.not_in(
            {"local_shadow_missing", "identity_sync_failed"}
        )
        conditions = {
            "shadow_missing": db_models.User.sync_status == "local_shadow_missing",
            "sync_failed": db_models.User.sync_status == "identity_sync_failed",
            "local_disabled": and_(normal_sync, db_models.User.is_active.is_(False)),
            "identity_disabled": and_(
                normal_sync,
                db_models.User.is_active.is_(True),
                db_models.User.identity_enabled.is_(False),
            ),
            "active": and_(
                normal_sync,
                db_models.User.is_active.is_(True),
                db_models.User.identity_enabled.is_(True),
            ),
        }
        return conditions[account_state]

    def _apply_user_filters(
        self,
        query: Any,
        *,
        q: str | None,
        role: str | None,
        account_states: set[str] | None,
        role_statuses: set[str] | None,
    ) -> Any:
        normalized_q = (q or "").strip()
        if normalized_q:
            pattern = self._search_pattern(normalized_q)
            query = query.where(
                or_(
                    db_models.User.username.ilike(pattern, escape="\\"),
                    db_models.User.email.ilike(pattern, escape="\\"),
                    db_models.User.first_name.ilike(pattern, escape="\\"),
                    db_models.User.last_name.ilike(pattern, escape="\\"),
                )
            )
        if role is not None:
            query = query.where(db_models.User.platform_role == role)
        if account_states:
            query = query.where(
                or_(
                    *[
                        self._account_state_condition(account_state)
                        for account_state in sorted(account_states)
                    ]
                )
            )
        if role_statuses:
            query = query.where(db_models.User.role_status.in_(role_statuses))
        return query

    def _execute_page(
        self,
        query: Any,
        *,
        sort_columns: Mapping[str, Any],
        sort_by: str,
        sort_direction: str,
        tie_breaker: Any,
        page: int,
        page_size: int,
    ) -> tuple[list[Mapping[str, Any]], int]:
        if sort_by not in sort_columns or sort_direction not in {"asc", "desc"}:
            UserGroupService._invalid_page_request()
        column = sort_columns[sort_by]
        ordered = (
            column.desc().nulls_last()
            if sort_direction == "desc"
            else column.asc().nulls_last()
        )
        filtered = query.add_columns(
            func.row_number()
            .over(order_by=(ordered, tie_breaker.asc()))
            .label("_page_row")
        ).cte("filtered_page_rows")
        page_start = (page - 1) * page_size
        page_rows = (
            select(*filtered.c)
            .where(
                filtered.c["_page_row"] > page_start,
                filtered.c["_page_row"] <= page_start + page_size,
            )
            .cte("selected_page_rows")
        )
        totals = (
            select(func.count().label("_page_total"))
            .select_from(filtered)
            .cte("page_totals")
        )
        statement = (
            select(*page_rows.c, totals.c["_page_total"])
            .select_from(totals.outerjoin(page_rows, true()))
            .order_by(page_rows.c["_page_row"].asc().nulls_last())
        )
        mappings = list(self.db.execute(statement).mappings().all())
        total = int(mappings[0]["_page_total"])
        page_items: list[Mapping[str, Any]] = []
        for row in mappings:
            if row["_page_row"] is not None:
                page_items.append(dict(row))
        return page_items, total

    @staticmethod
    def _parse_csv_filter(
        value: str | None,
        allowed: Collection[str],
    ) -> set[str] | None:
        if value is None:
            return None
        parts = value.split(",")
        normalized = set(parts)
        if (
            not normalized
            or "" in normalized
            or len(normalized) != len(parts)
            or not normalized.issubset(allowed)
        ):
            UserGroupService._invalid_page_request()
        return normalized

    @staticmethod
    def _validate_page(*, page: int, page_size: int) -> None:
        if page < 1 or not 1 <= page_size <= 100:
            UserGroupService._invalid_page_request()

    @staticmethod
    def _validate_q(q: str | None) -> None:
        if q is not None and len(q.strip()) > 200:
            UserGroupService._invalid_page_request()

    @staticmethod
    def _validate_user_ids(user_ids: list[str]) -> None:
        if (
            not 1 <= len(user_ids) <= 100
            or len(set(user_ids)) != len(user_ids)
            or any(not user_id or user_id.strip() != user_id for user_id in user_ids)
        ):
            UserGroupService._invalid_request()

    @staticmethod
    def _search_pattern(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    @staticmethod
    def _correlation_ids(
        correlation_id: str | None,
        root_correlation_id: str | None,
    ) -> tuple[str, str]:
        resolved = correlation_id or str(uuid4())
        return resolved, root_correlation_id or resolved

    def _record_audit(
        self,
        *,
        event_type: str,
        actor_user_id: str,
        target_id: str,
        action: str,
        correlation_id: str,
        root_correlation_id: str,
        metadata: dict[str, object] | None = None,
        result: Literal["success", "failure"] = "success",
        error_code: str | None = None,
    ) -> None:
        self.audit_events.record(
            event_type=event_type,
            actor_type="user",
            actor_id=actor_user_id,
            actor_user_id=actor_user_id,
            target_type="user_group",
            target_id=target_id,
            action=action,
            result=result,
            error_code=error_code,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            metadata=metadata,
        )

    def _record_member_audit(
        self,
        *,
        event_type: str,
        actor_user_id: str,
        target_user_id: str,
        action: str,
        group_id: str,
        correlation_id: str,
        root_correlation_id: str,
        result: Literal["success", "failure"] = "success",
        error_code: str | None = None,
    ) -> None:
        self.audit_events.record(
            event_type=event_type,
            actor_type="user",
            actor_id=actor_user_id,
            actor_user_id=actor_user_id,
            target_type="user",
            target_id=target_user_id,
            action=action,
            result=result,
            error_code=error_code,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            metadata={"group_id": group_id},
        )

    def _persist_failure_audit(
        self,
        *,
        event_type: str,
        actor_user_id: str,
        target_type: Literal["user", "user_group"],
        target_id: str,
        action: str,
        error_code: str,
        correlation_id: str,
        root_correlation_id: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        try:
            with Session(bind=self.db.get_bind()) as audit_db:
                AuditEventService(audit_db).record(
                    event_type=event_type,
                    actor_type="user",
                    actor_id=actor_user_id,
                    actor_user_id=actor_user_id,
                    target_type=target_type,
                    target_id=target_id,
                    action=action,
                    result="failure",
                    error_code=error_code,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata=metadata,
                )
                audit_db.commit()
        except Exception:
            logger.exception(
                "Failed to persist user group failure audit",
                extra={"event_type": event_type, "target_id": target_id},
            )

    @staticmethod
    def _failure_code(exc: Exception, *, fallback: str) -> str:
        if (
            isinstance(exc, HTTPException)
            and isinstance(exc.detail, str)
            and exc.detail.startswith("KB_GROUP_ADMIN_")
        ):
            return exc.detail
        return fallback

    @staticmethod
    def _is_duplicate_group_name(exc: IntegrityError) -> bool:
        detail = str(exc.orig).lower()
        return "user_groups" in detail and ("unique" in detail or "name_key" in detail)

    @staticmethod
    def _invalid_request() -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GROUP_INVALID_REQUEST,
        )

    @staticmethod
    def _invalid_page_request() -> NoReturn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GROUP_INVALID_PAGE_REQUEST,
        )
