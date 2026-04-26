"""TeamRoute"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.openapi import build_responses
from app.models import Team, TeamCreate, TeamListResponse, TeamUpdate
from app.services import get_team_service
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Team"])


@router.get(
    "/",
    response_model=TeamListResponse,
    summary="List teams",
    responses=build_responses(500),
)
async def list_teams(service: TeamService = Depends(get_team_service)) -> TeamListResponse:
    """Get team list."""
    return service.list()


@router.post(
    "/",
    response_model=Team,
    status_code=status.HTTP_201_CREATED,
    summary="Create team",
    responses=build_responses(422, 500),
)
async def create_team(payload: TeamCreate, service: TeamService = Depends(get_team_service)) -> Team:
    """Create new team."""
    return service.create(payload)


@router.get(
    "/{team_id}",
    response_model=Team,
    summary="Get team",
    responses=build_responses(404, 500),
)
async def get_team(
    team_id: str,
    request: Request,
    service: TeamService = Depends(get_team_service),
) -> Team:
    """Get specified team."""
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
    summary="Update team",
    responses=build_responses(404, 422, 500),
)
async def update_team(
    team_id: str,
    payload: TeamUpdate,
    request: Request,
    service: TeamService = Depends(get_team_service),
) -> Team:
    """Update team information."""
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
    summary="Delete team",
    responses=build_responses(404, 500),
)
async def delete_team(
    team_id: str,
    request: Request,
    service: TeamService = Depends(get_team_service),
) -> None:
    """Delete specified team."""
    team = service.get(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("team.not_found")
        )
    service.delete(team_id)
