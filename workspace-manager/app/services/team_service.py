"""TeamService"""

from __future__ import annotations

from typing import Dict, Optional
from uuid import uuid4

from app.models import Team, TeamCreate, TeamListResponse, TeamUpdate


class TeamService:
    """Manage team and member information"""

    def __init__(self) -> None:
        self._teams: Dict[str, Team] = {}

    def list(self) -> TeamListResponse:
        """List all teams"""
        return TeamListResponse(items=list(self._teams.values()), total=len(self._teams))

    def get(self, team_id: str) -> Optional[Team]:
        """Get single team"""
        return self._teams.get(team_id)

    def create(self, payload: TeamCreate) -> Team:
        """Create new team"""
        team_id = str(uuid4())
        team = Team(
            id=team_id,
            name=payload.name,
            description=payload.description,
            avatar_url=payload.avatar_url,
            owner_id=payload.owner_id,
            member_count=1,
        )
        self._teams[team_id] = team
        return team

    def update(self, team_id: str, payload: TeamUpdate) -> Optional[Team]:
        """Update team information"""
        team = self._teams.get(team_id)
        if not team:
            return None
        updated_data = team.model_dump()
        for field, value in payload.model_dump(exclude_none=True).items():
            updated_data[field] = value
        team = Team(**updated_data)
        self._teams[team_id] = team
        return team

    def delete(self, team_id: str) -> None:
        """DeleteTeam"""
        self._teams.pop(team_id, None)


__all__ = ["TeamService"]
