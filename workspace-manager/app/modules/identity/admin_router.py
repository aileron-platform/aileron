"""Canonical admin users API."""

from __future__ import annotations

from collections.abc import Collection
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import get_db
from app.modules.identity.admin_models import (
    ACCOUNT_STATE_VALUES,
    PLATFORM_ROLE_ORDER,
    ROLE_STATUS_VALUES,
    AdminRoleListResponse,
    AdminUser,
    AdminUserListResponse,
    AdminUserRoleRequest,
)
from app.modules.identity.admin_authorization import require_admin_user
from app.modules.identity.admin import UserAdminService

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

_LIST_QUERY_KEYS = frozenset(
    {
        "q",
        "role",
        "roleStatus",
        "accountState",
        "enabled",
        "groupId",
        "page",
        "pageSize",
        "sortBy",
        "sortDirection",
    }
)
_SORT_FIELDS = frozenset({"username", "createdAt", "updatedAt"})


def get_user_admin_service(db: Session = Depends(get_db)) -> UserAdminService:
    return UserAdminService(db)


@router.get("", response_model=AdminUserListResponse)
def list_admin_users(
    request: Request,
    q: str | None = Query(None),
    role: str | None = Query(None),
    role_status: str | None = Query(None, alias="roleStatus"),
    account_state: str | None = Query(None, alias="accountState"),
    enabled: str | None = Query(None),
    group_id: str | None = Query(None, alias="groupId"),
    page: str = Query("1"),
    page_size: str = Query("25", alias="pageSize"),
    sort_by: str = Query("username", alias="sortBy"),
    sort_direction: str = Query("asc", alias="sortDirection"),
    _admin: db_models.User = Depends(require_admin_user),
    service: UserAdminService = Depends(get_user_admin_service),
) -> AdminUserListResponse:
    _validate_list_query_keys(request)
    normalized_q = q.strip() if q is not None else None
    if normalized_q == "":
        normalized_q = None
    if normalized_q is not None and len(normalized_q) > 200:
        _invalid_page_request()
    normalized_role = _parse_optional_enum(role, PLATFORM_ROLE_ORDER)
    role_statuses = _parse_csv_enum(role_status, ROLE_STATUS_VALUES)
    account_states = _parse_csv_enum(account_state, ACCOUNT_STATE_VALUES)
    normalized_group_id = group_id.strip() if group_id is not None else None
    if normalized_group_id == "":
        _invalid_page_request()
    normalized_sort = _parse_required_enum(sort_by, _SORT_FIELDS)
    normalized_direction = _parse_required_enum(
        sort_direction, frozenset({"asc", "desc"})
    )
    return service.list_users(
        q=normalized_q,
        role=normalized_role,
        role_statuses=role_statuses,
        account_states=account_states,
        enabled=_parse_optional_bool(enabled),
        group_id=normalized_group_id,
        page=_parse_positive_int(page, maximum=None),
        page_size=_parse_positive_int(page_size, maximum=100),
        sort_by=normalized_sort,
        sort_direction=normalized_direction,
    )


@router.get("/roles", response_model=AdminRoleListResponse)
def list_admin_user_roles(
    _admin: db_models.User = Depends(require_admin_user),
) -> AdminRoleListResponse:
    return UserAdminService.list_roles()


@router.get("/{user_id}", response_model=AdminUser)
def get_admin_user(
    user_id: str,
    _admin: db_models.User = Depends(require_admin_user),
    service: UserAdminService = Depends(get_user_admin_service),
) -> AdminUser:
    return service.get_user(user_id)


@router.put("/{user_id}/role", response_model=AdminUser)
def replace_admin_user_role(
    user_id: str,
    request: Request,
    payload: AdminUserRoleRequest,
    admin: db_models.User = Depends(require_admin_user),
    service: UserAdminService = Depends(get_user_admin_service),
) -> AdminUser:
    return service.replace_role(
        user_id,
        payload,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )


def _validate_list_query_keys(request: Request) -> None:
    keys = list(request.query_params.keys())
    if set(keys) - _LIST_QUERY_KEYS:
        _invalid_page_request()
    if any(len(request.query_params.getlist(key)) != 1 for key in keys):
        _invalid_page_request()


def _parse_positive_int(raw_value: str, *, maximum: int | None) -> int:
    if not raw_value.isascii() or not raw_value.isdigit():
        _invalid_page_request()
    value = int(raw_value)
    if value < 1 or (maximum is not None and value > maximum):
        _invalid_page_request()
    return value


def _parse_optional_bool(raw_value: str | None) -> bool | None:
    if raw_value is None:
        return None
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    _invalid_page_request()


def _parse_optional_enum(
    raw_value: str | None,
    allowed: Collection[str],
) -> str | None:
    if raw_value is None:
        return None
    return _parse_required_enum(raw_value, allowed)


def _parse_required_enum(raw_value: str, allowed: Collection[str]) -> str:
    if not raw_value or raw_value not in allowed:
        _invalid_page_request()
    return raw_value


def _parse_csv_enum(
    raw_value: str | None,
    allowed: Collection[str],
) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    values = raw_value.split(",")
    if not values or any(not value or value not in allowed for value in values):
        _invalid_page_request()
    return tuple(dict.fromkeys(values))


def _invalid_page_request() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="USER_ADMIN_INVALID_PAGE_REQUEST",
    )
