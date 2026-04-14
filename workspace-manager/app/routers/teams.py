"""團隊路由"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.openapi import build_responses
from app.models import Team, TeamCreate, TeamListResponse, TeamUpdate
from app.services import get_team_service
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["團隊"])


@router.get(
    "/",
    response_model=TeamListResponse,
    summary="列出團隊",
    responses=build_responses(500),
)
async def list_teams(service: TeamService = Depends(get_team_service)) -> TeamListResponse:
    """取得團隊列表"""
    return service.list()


@router.post(
    "/",
    response_model=Team,
    status_code=status.HTTP_201_CREATED,
    summary="建立團隊",
    responses=build_responses(422, 500),
)
async def create_team(payload: TeamCreate, service: TeamService = Depends(get_team_service)) -> Team:
    """建立新團隊"""
    return service.create(payload)


@router.get(
    "/{team_id}",
    response_model=Team,
    summary="取得團隊",
    responses=build_responses(404, 500),
)
async def get_team(
    team_id: str,
    request: Request,
    service: TeamService = Depends(get_team_service),
) -> Team:
    """取得指定團隊"""
    team = service.get(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("team.not_found")
        )
    return team


@router.put(
    "/{team_id}",
    response_model=Team,
    summary="更新團隊",
    responses=build_responses(404, 422, 500),
)
async def update_team(
    team_id: str,
    payload: TeamUpdate,
    request: Request,
    service: TeamService = Depends(get_team_service),
) -> Team:
    """更新團隊資訊"""
    team = service.update(team_id, payload)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("team.not_found")
        )
    return team


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除團隊",
    responses=build_responses(404, 500),
)
async def delete_team(
    team_id: str,
    request: Request,
    service: TeamService = Depends(get_team_service),
) -> None:
    """刪除指定團隊"""
    team = service.get(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("team.not_found")
        )
    service.delete(team_id)
