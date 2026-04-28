"""Unit Tests for TemplateFeatureDetectionService"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import Template as TemplateDB, TemplateFeature, TemplateFeatureMapping
from app.services.template_base_service import TemplateBaseService
from app.services.template_feature_detection_service import (
    TemplateFeatureDetectionService,
    FeatureIndexResult,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_template_base_service(tmp_path):
    """Mock TemplateBaseService"""
    service = MagicMock(spec=TemplateBaseService)
    template_dir = tmp_path / "templates" / "test-template"
    service._get_template_dir = MagicMock(return_value=template_dir)
    service._resolve_template_dir = MagicMock(return_value=template_dir)
    service._get_template = MagicMock()
    return service


@pytest.fixture
def feature_detection_service(mock_db_session, mock_template_base_service):
    """TemplateFeatureDetectionService Instance"""
    return TemplateFeatureDetectionService(mock_db_session, mock_template_base_service)


@pytest.fixture
def mock_template_db():
    """Sample Template Database Model"""
    return TemplateDB(
        id="test-template",
        name="Test Template",
        description="Test Description",
        author_name="Test Author",
        author_email="test@example.com",
        version="1.0.0",
        cli_type="claude-code",
        status="draft",
        keywords=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_features():
    """Sample Feature List"""
    return [
        TemplateFeature(
            id="feat-mcp",
            feature_key="mcp",
            feature_name="MCP",
            description="MCP Servers",
            sort_order=1,
            is_active=True
        ),
        TemplateFeature(
            id="feat-commands",
            feature_key="commands",
            feature_name="Slash Commands",
            description="Slash Commands",
            sort_order=2,
            is_active=True
        ),
        TemplateFeature(
            id="feat-hooks",
            feature_key="hooks",
            feature_name="Hooks",
            description="Hooks",
            sort_order=3,
            is_active=True
        ),
    ]


# ============================================================================
# Feature Detection Tests
# ============================================================================

@pytest.mark.unit
class TestFeatureDetection:
    """Feature Detection Tests"""

    def test_detect_mcp_feature_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When MCP YAML File Exists"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        mcp_dir = template_dir / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "test.yaml").write_text("command: test\n", encoding="utf-8")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["mcp"] is True

    def test_detect_mcp_feature_not_exists(self, feature_detection_service, tmp_path):
        """Test: Detection Fails When MCP File Does Not Exist"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["mcp"] is False

    def test_detect_mcp_non_yaml_file(self, feature_detection_service, tmp_path):
        """Test: Detection Fails When MCP Directory Has No YAML File"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        mcp_dir = template_dir / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "mcp.json").write_text(json.dumps({"mcpServers": {"test": {}}}), encoding="utf-8")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["mcp"] is False

    def test_detect_mcp_empty_directory(self, feature_detection_service, tmp_path):
        """Test: Detection Fails When MCP Directory Is Empty"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        (template_dir / "mcp").mkdir()

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["mcp"] is False

    def test_detect_commands_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When Commands Directory Has Files"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        commands_dir = template_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "test.md").write_text("# Test Command")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["commands"] is True

    def test_detect_commands_empty_directory(self, feature_detection_service, tmp_path):
        """Test: Detection Fails When Commands Directory Is Empty"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        commands_dir = template_dir / "commands"
        commands_dir.mkdir()

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["commands"] is False

    def test_detect_commands_only_gitkeep(self, feature_detection_service, tmp_path):
        """Test: Detection Fails For Directory With Only .gitkeep"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        commands_dir = template_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / ".gitkeep").write_text("")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["commands"] is False

    def test_detect_hooks_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When Hooks YAML File Exists"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        hooks_dir = template_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "pre-tool-use.yaml").write_text("matcher: '*'\n", encoding="utf-8")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["hooks"] is True

    def test_detect_agents_md_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When AGENTS.md Exists"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        agents_md = template_dir / "agents.md"
        agents_md.write_text("# Agent Instructions\n\nSome content here.")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["agentsMd"] is True

    def test_detect_agents_md_too_small(self, feature_detection_service, tmp_path):
        """Test: Detection Fails When AGENTS.md Is Too Small"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        agents_md = template_dir / "agents.md"
        agents_md.write_text("abc")  # < 10 bytes

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["agentsMd"] is False

    def test_detect_agents_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When Agents Directory Has Files"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        agents_dir = template_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "agent.md").write_text("# Agent")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["agents"] is True

    def test_detect_output_style_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When Output Style File Exists"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        output_style = template_dir / "output-style.yaml"
        output_style.write_text("tone: concise\n", encoding="utf-8")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["outputStyle"] is True

    def test_detect_scripts_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When Scripts Directory Has Files"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        scripts_dir = template_dir / "resources" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "script.sh").write_text("#!/bin/bash")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["scripts"] is True

    def test_detect_skills_exists(self, feature_detection_service, tmp_path):
        """Test: Successfully Detect When Skills Directory Has Files"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        skills_dir = template_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill.md").write_text("# Skill")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        assert result["skills"] is True

    def test_detect_no_features(self, feature_detection_service, tmp_path):
        """Test: Empty Template Has No Features"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        for feature_key, detected in result.items():
            assert detected is False

    def test_detect_all_features(self, feature_detection_service, tmp_path):
        """Test: Template Contains All Features"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)

        # MCP
        mcp_dir = template_dir / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "test.yaml").write_text("command: test\n", encoding="utf-8")

        # Hooks
        hooks_dir = template_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "pre-tool-use.yaml").write_text("matcher: '*'\n", encoding="utf-8")

        # Slash Commands
        commands_dir = template_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "test.md").write_text("# Test")

        # AGENTS.md
        (template_dir / "agents.md").write_text("# Agent Instructions\n")

        # SubAgents
        agents_dir = template_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "agent.md").write_text("# Agent")

        # Output Styles
        (template_dir / "output-style.yaml").write_text("tone: concise\n", encoding="utf-8")

        # Scripts
        scripts_dir = template_dir / "resources" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "script.sh").write_text("#!/bin/bash")

        # Skills
        skills_dir = template_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill.md").write_text("# Skill")

        # Act
        result = feature_detection_service.detect_features("test-template")

        # Assert
        for feature_key, detected in result.items():
            assert detected is True, f"Feature {feature_key} should be detected"


# ============================================================================
# Feature Indexing Tests
# ============================================================================

@pytest.mark.unit
class TestFeatureIndexing:
    """Feature Indexing Tests"""

    def test_index_features_creates_mappings(
        self, feature_detection_service, mock_db_session, mock_template_base_service,
        mock_template_db, mock_features, tmp_path
    ):
        """Test: Successfully Build Feature Mappings"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True)
        mcp_dir = template_dir / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "test.yaml").write_text("command: test\n", encoding="utf-8")

        mock_template_base_service._get_template.return_value = mock_template_db

        # Mock query chain for deleting old mappings
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = None
        mock_db_session.query.return_value = mock_query

        # Mock feature query
        mock_feature_query = MagicMock()
        mock_feature_filter = MagicMock()
        mock_feature_query.filter.return_value = mock_feature_filter
        mock_feature_filter.first.return_value = mock_features[0]  # Return MCP feature

        def query_side_effect(model):
            if model == TemplateFeatureMapping:
                return mock_query
            elif model == TemplateFeature:
                return mock_feature_query
            return MagicMock()

        mock_db_session.query.side_effect = query_side_effect

        # Act
        result = feature_detection_service.index_features("test-template")

        # Assert
        assert result.success is True
        assert result.template_id == "test-template"
        assert "mcp" in result.detected_features
        assert result.indexed_count == 1
        assert result.failed_count == 0
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    def test_index_features_template_not_found(
        self, feature_detection_service, mock_template_base_service
    ):
        """Test: Indexing Fails When Template Does Not Exist"""
        # Arrange
        mock_template_base_service._get_template.return_value = None

        # Act
        result = feature_detection_service.index_features("nonexistent")

        # Assert
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_index_features_handles_exception(
        self, feature_detection_service, mock_db_session, mock_template_base_service,
        mock_template_db
    ):
        """Test: Correctly Handle When Indexing Process Throws Exception"""
        # Arrange
        mock_template_base_service._get_template.return_value = mock_template_db
        mock_db_session.query.side_effect = Exception("Database error")

        # Act
        result = feature_detection_service.index_features("test-template")

        # Assert
        assert result.success is False
        assert "failed" in result.message.lower()
        mock_db_session.rollback.assert_called()


# ============================================================================
# Feature Query Tests
# ============================================================================

@pytest.mark.unit
class TestFeatureQuery:
    """Feature Query Tests"""

    def test_get_template_features_returns_list(
        self, feature_detection_service, mock_db_session, mock_features
    ):
        """Test: Query Indexed Features Return List"""
        # Arrange
        mock_mapping1 = MagicMock()
        mock_mapping1.feature_id = "feat-mcp"
        mock_mapping2 = MagicMock()
        mock_mapping2.feature_id = "feat-hooks"

        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()

        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.all.return_value = [mock_mapping1, mock_mapping2]

        # Mock feature queries
        def query_side_effect(model):
            if model == TemplateFeatureMapping:
                return mock_query
            elif model == TemplateFeature:
                mock_feat_query = MagicMock()
                mock_feat_filter = MagicMock()
                mock_feat_query.filter.return_value = mock_feat_filter

                # Return different features based on call order
                call_count = [0]
                def first_side_effect():
                    result = [mock_features[0], mock_features[2]][call_count[0]]
                    call_count[0] += 1
                    return result

                mock_feat_filter.first.side_effect = first_side_effect
                return mock_feat_query
            return MagicMock()

        mock_db_session.query.side_effect = query_side_effect

        # Act
        result = feature_detection_service.get_template_features("test-template")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_template_features_empty(
        self, feature_detection_service, mock_db_session
    ):
        """Test: Query Template With No Indexed Features"""
        # Arrange
        mock_query = MagicMock()
        mock_join = MagicMock()
        mock_filter = MagicMock()

        mock_query.join.return_value = mock_join
        mock_join.filter.return_value = mock_filter
        mock_filter.all.return_value = []

        mock_db_session.query.return_value = mock_query

        # Act
        result = feature_detection_service.get_template_features("test-template")

        # Assert
        assert result == []

    def test_get_template_features_handles_exception(
        self, feature_detection_service, mock_db_session
    ):
        """Test: Return Empty List When Query Throws Exception"""
        # Arrange
        mock_db_session.query.side_effect = Exception("Database error")

        # Act
        result = feature_detection_service.get_template_features("test-template")

        # Assert
        assert result == []
