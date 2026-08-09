"""Local platform authorization administration."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.identity.advisory_lock import acquire_identity_lock
from app.modules.identity.admin_models import (
    PLATFORM_ROLE_ORDER,
    AdminRoleListResponse,
    AdminRoleOption,
    AdminUser,
    AdminUserListResponse,
    AdminUserRoleRequest,
    admin_user_from_model,
)
from app.modules.identity.platform_role import normalize_platform_role


class UserAdminService:
    """Manage local platform roles and read-only identity snapshots."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_events = AuditEventService(db)

    def list_users(
        self,
        *,
        q: str | None = None,
        role: str | None = None,
        role_statuses: Collection[str] = (),
        account_states: Collection[str] = (),
        enabled: bool | None = None,
        group_id: str | None = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "username",
        sort_direction: str = "asc",
    ) -> AdminUserListResponse:
        """Return a database-filtered page of local authorization snapshots."""

        statement = select(db_models.User)
        filters: list[Any] = []
        if q:
            pattern = f"%{self._escape_like(q.lower())}%"
            filters.append(
                or_(
                    func.lower(db_models.User.username).like(pattern, escape="\\"),
                    func.lower(func.coalesce(db_models.User.email, "")).like(
                        pattern, escape="\\"
                    ),
                    func.lower(func.coalesce(db_models.User.first_name, "")).like(
                        pattern, escape="\\"
                    ),
                    func.lower(func.coalesce(db_models.User.last_name, "")).like(
                        pattern, escape="\\"
                    ),
                )
            )
        if role is not None:
            filters.append(db_models.User.platform_role == role)
        if role_statuses:
            filters.append(db_models.User.role_status.in_(tuple(role_statuses)))
        if account_states:
            filters.append(self._account_state_expression().in_(tuple(account_states)))
        if enabled is not None:
            enabled_expression = and_(
                db_models.User.is_active.is_(True),
                db_models.User.identity_enabled.is_(True),
                db_models.User.sync_status.in_(("synced", "local_shadow_imported")),
            )
            filters.append(enabled_expression if enabled else ~enabled_expression)
        if group_id is not None:
            filters.append(
                exists(
                    select(1).where(
                        db_models.UserGroupMember.user_id == db_models.User.id,
                        db_models.UserGroupMember.group_id == group_id,
                    )
                )
            )
        if filters:
            statement = statement.where(*filters)

        total = int(
            self.db.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        sort_column = {
            "username": func.lower(db_models.User.username),
            "createdAt": db_models.User.created_at,
            "updatedAt": db_models.User.updated_at,
        }.get(sort_by)
        if sort_column is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="USER_ADMIN_INVALID_PAGE_REQUEST",
            )
        primary_order = (
            sort_column.asc().nulls_last()
            if sort_direction == "asc"
            else sort_column.desc().nulls_last()
        )
        users = list(
            self.db.scalars(
                statement.order_by(primary_order, db_models.User.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return AdminUserListResponse(
            items=[admin_user_from_model(user) for user in users],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def get_user(self, user_id: str) -> AdminUser:
        user = self.db.get(db_models.User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
        return admin_user_from_model(user)

    @staticmethod
    def list_roles() -> AdminRoleListResponse:
        return AdminRoleListResponse(
            items=[
                AdminRoleOption(
                    id=role,
                    labelKey=f"roles.platform.{role}.label",
                    descriptionKey=f"roles.platform.{role}.description",
                )
                for role in PLATFORM_ROLE_ORDER
            ]
        )

    def replace_role(
        self,
        user_id: str,
        payload: AdminUserRoleRequest,
        *,
        actor_user_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> AdminUser:
        """Change the local platform role; external identity roles are untouched."""

        # Role changes share one transaction lock so concurrent demotions cannot
        # both observe the same last-admin count.
        acquire_identity_lock(self.db, "platform-admin-roles")
        user = self.db.get(db_models.User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
        role = normalize_platform_role(str(payload.role))
        if role is None:
            raise HTTPException(status_code=422, detail="INVALID_PLATFORM_ROLE")
        current_role = normalize_platform_role(user.platform_role)
        if current_role == role:
            return admin_user_from_model(user)
        if current_role == "admin" and role != "admin":
            if actor_user_id == user_id:
                raise HTTPException(status_code=409, detail="SELF_DEMOTE_FORBIDDEN")
            admin_count = int(
                self.db.scalar(
                    select(func.count(db_models.User.id)).where(
                        db_models.User.platform_role == "admin",
                        db_models.User.is_active.is_(True),
                        db_models.User.identity_enabled.is_(True),
                    )
                )
                or 0
            )
            if admin_count <= 1:
                raise HTTPException(status_code=409, detail="LAST_ADMIN_FORBIDDEN")

        before = user.platform_role
        user.platform_role = role.value
        user.role_status = "valid"
        user.role_issues = []
        user.updated_at = datetime.now(timezone.utc)
        event_correlation_id = correlation_id or str(uuid4())
        self.audit_events.record(
            event_type="user.role_replaced",
            actor_type="user",
            actor_id=actor_user_id,
            actor_user_id=actor_user_id,
            target_type="user",
            target_id=user_id,
            action="replace_user_role",
            result="success",
            error_code=None,
            correlation_id=event_correlation_id,
            root_correlation_id=root_correlation_id or event_correlation_id,
            metadata={
                "changed_fields": ["platform_role", "role_status", "role_issues"],
                "before": before or "none",
                "after": role.value,
            },
        )
        self.db.commit()
        self.db.refresh(user)
        return admin_user_from_model(user)

    def _account_state_expression(self):
        return case(
            (db_models.User.sync_status == "local_shadow_missing", "shadow_missing"),
            (db_models.User.sync_status == "identity_sync_failed", "sync_failed"),
            (db_models.User.is_active.is_(False), "local_disabled"),
            (db_models.User.identity_enabled.is_(False), "identity_disabled"),
            else_="active",
        )

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


__all__ = ["UserAdminService"]
