"""Unit Tests for TeamService"""

from __future__ import annotations

import pytest

from app.models import Team, TeamCreate, TeamUpdate
from app.services.team_service import TeamService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def team_service():
    """TeamService Instance"""
    return TeamService()


@pytest.fixture
def sample_team_create():
    """Sample Team Creation Request"""
    return TeamCreate(
        name="Test Team",
        description="Test team description",
        owner_id="user-123"
    )


# ============================================================================
# Team List Tests
# ============================================================================

@pytest.mark.unit
class TestTeamList:
    """Team List Tests"""

    def test_list_teams_empty(self, team_service):
        """Test: Empty Team List"""
        # Act
        result = team_service.list()

        # Assert
        assert result.total == 0
        assert len(result.items) == 0

    def test_list_teams_with_data(self, team_service, sample_team_create):
        """Test: List Teams"""
        # Arrange
        team_service.create(sample_team_create)
        team_service.create(TeamCreate(name="Team 2", description="Desc 2", owner_id="user-456"))

        # Act
        result = team_service.list()

        # Assert
        assert result.total == 2
        assert len(result.items) == 2


# ============================================================================
# Team Get Tests
# ============================================================================

@pytest.mark.unit
class TestTeamGet:
    """Team Query Tests"""

    def test_get_team_success(self, team_service, sample_team_create):
        """Test: Successfully Get Team"""
        # Arrange
        created_team = team_service.create(sample_team_create)

        # Act
        result = team_service.get(created_team.id)

        # Assert
        assert result is not None
        assert result.id == created_team.id
        assert result.name == "Test Team"

    def test_get_team_not_found(self, team_service):
        """Test: Return None When Team Does Not Exist"""
        # Act
        result = team_service.get("nonexistent-team")

        # Assert
        assert result is None


# ============================================================================
# Team Create Tests
# ============================================================================

@pytest.mark.unit
class TestTeamCreate:
    """Team Creation Tests"""

    def test_create_team_success(self, team_service, sample_team_create):
        """Test: Successfully Create Team"""
        # Act
        result = team_service.create(sample_team_create)

        # Assert
        assert isinstance(result, Team)
        assert result.name == "Test Team"
        assert result.description == "Test team description"
        assert result.owner_id == "user-123"
        assert result.member_count == 1

    def test_create_team_with_optional_fields(self, team_service):
        """Test: Create Team With Optional Fields"""
        # Arrange
        team_create = TeamCreate(
            name="Team with Avatar",
            description="Description",
            owner_id="user-123",
            avatar_url="https://example.com/avatar.jpg"
        )

        # Act
        result = team_service.create(team_create)

        # Assert
        assert result.avatar_url == "https://example.com/avatar.jpg"


# ============================================================================
# Team Update Tests
# ============================================================================

@pytest.mark.unit
class TestTeamUpdate:
    """Team Update Tests"""

    def test_update_team_success(self, team_service, sample_team_create):
        """Test: Successfully Update Team"""
        # Arrange
        created_team = team_service.create(sample_team_create)
        team_update = TeamUpdate(
            name="Updated Team Name",
            description="Updated description"
        )

        # Act
        result = team_service.update(created_team.id, team_update)

        # Assert
        assert result is not None
        assert result.name == "Updated Team Name"
        assert result.description == "Updated description"

    def test_update_team_not_found(self, team_service):
        """Test: Return None When Updating Non-Existent Team"""
        # Arrange
        team_update = TeamUpdate(name="Updated Name")

        # Act
        result = team_service.update("nonexistent-team", team_update)

        # Assert
        assert result is None

    def test_update_team_partial_fields(self, team_service, sample_team_create):
        """Test: Partial Field Update"""
        # Arrange
        created_team = team_service.create(sample_team_create)
        original_description = created_team.description

        team_update = TeamUpdate(name="Only Name Updated")

        # Act
        result = team_service.update(created_team.id, team_update)

        # Assert
        assert result is not None
        assert result.name == "Only Name Updated"
        assert result.description == original_description  # Description unchanged


# ============================================================================
# Team Delete Tests
# ============================================================================

@pytest.mark.unit
class TestTeamDelete:
    """Team Deletion Tests"""

    def test_delete_team_success(self, team_service, sample_team_create):
        """Test: Successfully Delete Team"""
        # Arrange
        created_team = team_service.create(sample_team_create)

        # Act
        team_service.delete(created_team.id)

        # Assert
        assert team_service.get(created_team.id) is None

    def test_delete_team_not_found(self, team_service):
        """Test: Graceful Handle When Deleting Non-Existent Team"""
        # Act & Assert (should not raise exception)
        team_service.delete("nonexistent-team")
