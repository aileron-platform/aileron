"""TeamService 單元測試"""

from __future__ import annotations

import pytest

from app.models import Team, TeamCreate, TeamUpdate
from app.services.team_service import TeamService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def team_service():
    """TeamService 實例"""
    return TeamService()


@pytest.fixture
def sample_team_create():
    """範例團隊創建請求"""
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
    """團隊列表測試"""

    def test_list_teams_empty(self, team_service):
        """測試：空團隊列表"""
        # Act
        result = team_service.list()

        # Assert
        assert result.total == 0
        assert len(result.items) == 0

    def test_list_teams_with_data(self, team_service, sample_team_create):
        """測試：列出團隊"""
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
    """團隊查詢測試"""

    def test_get_team_success(self, team_service, sample_team_create):
        """測試：成功獲取團隊"""
        # Arrange
        created_team = team_service.create(sample_team_create)

        # Act
        result = team_service.get(created_team.id)

        # Assert
        assert result is not None
        assert result.id == created_team.id
        assert result.name == "Test Team"

    def test_get_team_not_found(self, team_service):
        """測試：團隊不存在返回 None"""
        # Act
        result = team_service.get("nonexistent-team")

        # Assert
        assert result is None


# ============================================================================
# Team Create Tests
# ============================================================================

@pytest.mark.unit
class TestTeamCreate:
    """團隊創建測試"""

    def test_create_team_success(self, team_service, sample_team_create):
        """測試：成功創建團隊"""
        # Act
        result = team_service.create(sample_team_create)

        # Assert
        assert isinstance(result, Team)
        assert result.name == "Test Team"
        assert result.description == "Test team description"
        assert result.owner_id == "user-123"
        assert result.member_count == 1

    def test_create_team_with_optional_fields(self, team_service):
        """測試：創建帶可選字段的團隊"""
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
    """團隊更新測試"""

    def test_update_team_success(self, team_service, sample_team_create):
        """測試：成功更新團隊"""
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
        """測試：更新不存在的團隊返回 None"""
        # Arrange
        team_update = TeamUpdate(name="Updated Name")

        # Act
        result = team_service.update("nonexistent-team", team_update)

        # Assert
        assert result is None

    def test_update_team_partial_fields(self, team_service, sample_team_create):
        """測試：部分字段更新"""
        # Arrange
        created_team = team_service.create(sample_team_create)
        original_description = created_team.description

        team_update = TeamUpdate(name="Only Name Updated")

        # Act
        result = team_service.update(created_team.id, team_update)

        # Assert
        assert result is not None
        assert result.name == "Only Name Updated"
        assert result.description == original_description  # 描述不變


# ============================================================================
# Team Delete Tests
# ============================================================================

@pytest.mark.unit
class TestTeamDelete:
    """團隊刪除測試"""

    def test_delete_team_success(self, team_service, sample_team_create):
        """測試：成功刪除團隊"""
        # Arrange
        created_team = team_service.create(sample_team_create)

        # Act
        team_service.delete(created_team.id)

        # Assert
        assert team_service.get(created_team.id) is None

    def test_delete_team_not_found(self, team_service):
        """測試：刪除不存在的團隊優雅處理"""
        # Act & Assert (不應該拋出異常)
        team_service.delete("nonexistent-team")
