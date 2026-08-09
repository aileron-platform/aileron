"""Admin user groups API."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import get_db
from app.modules.identity.group_models import (
    UserGroup,
    UserGroupCreateRequest,
    UserGroupListResponse,
    UserGroupMemberAddResponse,
    UserGroupMemberCandidateListResponse,
    UserGroupMemberListResponse,
    UserGroupMemberMutationRequest,
    UserGroupMemberRemoveResponse,
    UserGroupPatchRequest,
)
from app.modules.identity.admin_authorization import require_admin_user
from app.modules.identity.groups import UserGroupService

router = APIRouter(prefix="/admin/user-groups", tags=["admin-user-groups"])

GROUP_INVALID_PAGE_REQUEST = "KB_GROUP_ADMIN_INVALID_PAGE_REQUEST"


def get_user_group_service(db: Session = Depends(get_db)) -> UserGroupService:
    return UserGroupService(db)


def _invalid_page_request() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=GROUP_INVALID_PAGE_REQUEST,
    )


def _parse_bounded_int(
    value: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if not value.isascii() or not value.isdecimal():
        _invalid_page_request()
    parsed = int(value)
    if parsed < minimum or (maximum is not None and parsed > maximum):
        _invalid_page_request()
    return parsed


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    _invalid_page_request()


def _validate_query_contract(request: Request, *, allowed: set[str]) -> None:
    observed: set[str] = set()
    for key, _value in request.query_params.multi_items():
        if key not in allowed or key in observed:
            _invalid_page_request()
        observed.add(key)


@router.get("", response_model=UserGroupListResponse)
def list_user_groups(
    request: Request,
    q: str | None = None,
    member_count_range: str | None = Query(None, alias="memberCountRange"),
    has_description: str | None = Query(None, alias="hasDescription"),
    updated_within_days: str | None = Query(None, alias="updatedWithinDays"),
    page: str = "1",
    page_size: str = Query("25", alias="pageSize"),
    sort_by: str = Query("name", alias="sortBy"),
    sort_direction: str = Query("asc", alias="sortDirection"),
    _admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupListResponse:
    _validate_query_contract(
        request,
        allowed={
            "q",
            "memberCountRange",
            "hasDescription",
            "updatedWithinDays",
            "page",
            "pageSize",
            "sortBy",
            "sortDirection",
        },
    )
    return service.list_groups(
        q=q,
        member_count_range=member_count_range,
        has_description=_parse_optional_bool(has_description),
        updated_within_days=(
            _parse_bounded_int(updated_within_days, minimum=1, maximum=365)
            if updated_within_days is not None
            else None
        ),
        page=_parse_bounded_int(page, minimum=1),
        page_size=_parse_bounded_int(page_size, minimum=1, maximum=100),
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


@router.post("", response_model=UserGroup, status_code=status.HTTP_201_CREATED)
def create_user_group(
    request: Request,
    payload: UserGroupCreateRequest,
    admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroup:
    return service.create_group(
        name=payload.name,
        description=payload.description,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )


@router.get("/{group_id}", response_model=UserGroup)
def get_user_group(
    group_id: str,
    _admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroup:
    return service.get_group(group_id=group_id)


@router.patch("/{group_id}", response_model=UserGroup)
def update_user_group(
    group_id: str,
    request: Request,
    payload: UserGroupPatchRequest,
    admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroup:
    return service.update_group(
        group_id=group_id,
        name=payload.name,
        description=payload.description,
        name_provided="name" in payload.model_fields_set,
        description_provided="description" in payload.model_fields_set,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_group(
    group_id: str,
    request: Request,
    admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> None:
    service.delete_group(
        group_id=group_id,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )


@router.get("/{group_id}/members", response_model=UserGroupMemberListResponse)
def list_user_group_members(
    group_id: str,
    request: Request,
    q: str | None = None,
    role: str | None = None,
    account_state: str | None = Query(None, alias="accountState"),
    source: str | None = None,
    page: str = "1",
    page_size: str = Query("25", alias="pageSize"),
    sort_by: str = Query("username", alias="sortBy"),
    sort_direction: str = Query("asc", alias="sortDirection"),
    _admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupMemberListResponse:
    _validate_query_contract(
        request,
        allowed={
            "q",
            "role",
            "accountState",
            "source",
            "page",
            "pageSize",
            "sortBy",
            "sortDirection",
        },
    )
    return service.list_members(
        group_id=group_id,
        q=q,
        role=role,
        account_state=account_state,
        source=source,
        page=_parse_bounded_int(page, minimum=1),
        page_size=_parse_bounded_int(page_size, minimum=1, maximum=100),
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


@router.get(
    "/{group_id}/member-candidates",
    response_model=UserGroupMemberCandidateListResponse,
)
def list_user_group_member_candidates(
    group_id: str,
    request: Request,
    q: str | None = None,
    membership: str = "not_member",
    role: str | None = None,
    account_state: str | None = Query(None, alias="accountState"),
    role_status: str | None = Query(None, alias="roleStatus"),
    page: str = "1",
    page_size: str = Query("25", alias="pageSize"),
    sort_by: str = Query("username", alias="sortBy"),
    sort_direction: str = Query("asc", alias="sortDirection"),
    _admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupMemberCandidateListResponse:
    _validate_query_contract(
        request,
        allowed={
            "q",
            "membership",
            "role",
            "accountState",
            "roleStatus",
            "page",
            "pageSize",
            "sortBy",
            "sortDirection",
        },
    )
    return service.list_member_candidates(
        group_id=group_id,
        q=q,
        membership=membership,
        role=role,
        account_state=account_state,
        role_status=role_status,
        page=_parse_bounded_int(page, minimum=1),
        page_size=_parse_bounded_int(page_size, minimum=1, maximum=100),
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


@router.post("/{group_id}/members", response_model=UserGroupMemberAddResponse)
def add_user_group_members(
    group_id: str,
    request: Request,
    payload: UserGroupMemberMutationRequest,
    admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupMemberAddResponse:
    return service.add_members(
        group_id=group_id,
        user_ids=payload.user_ids,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )


@router.post(
    "/{group_id}/members/batch-remove",
    response_model=UserGroupMemberRemoveResponse,
)
def remove_user_group_members(
    group_id: str,
    request: Request,
    payload: UserGroupMemberMutationRequest,
    admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> UserGroupMemberRemoveResponse:
    return service.remove_members(
        group_id=group_id,
        user_ids=payload.user_ids,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_user_group_member(
    group_id: str,
    user_id: str,
    request: Request,
    admin: db_models.User = Depends(require_admin_user),
    service: UserGroupService = Depends(get_user_group_service),
) -> None:
    service.remove_member(
        group_id=group_id,
        user_id=user_id,
        actor_user_id=admin.id,
        correlation_id=request.state.correlation_id,
        root_correlation_id=request.state.correlation_id,
    )
