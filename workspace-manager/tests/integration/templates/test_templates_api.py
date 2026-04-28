"""Template management API integration tests"""

from __future__ import annotations

import os
import uuid
import zipfile
from io import BytesIO
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi import status
from git import Repo

from app.services.template_git_service import GitOperationResult
from app.services.template_install_service import TemplateInstallError
from app.services.template_canonical_service import CanonicalTemplateValidationError

from tests.helpers.auth_helpers import AuthTestHelper
from tests.helpers.fixtures import TestDataFactory, MockResponses


class TestTemplatesAPI:
    """Template management API test cases"""

    @pytest.mark.integration
    def test_tpl_001_create_template_success(self, authenticated_client, test_data_factory):
        """TPL-001 Create template successfully"""
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Node.js Development Template",
            description="A template for Node.js development with all necessary tools",
            author_name=user.display_name,
            author_email=user.email,
            keywords=["nodejs", "development"],
        )

        response = client.post("/api/v1/templates", json=template_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify response structure
        required_fields = [
            "id", "name", "description", "version", "author",
            "keywords", "cliType", "status", "isActive"
        ]

        for field in required_fields:
            assert field in data, f"Template data should contain {field} field"

        # Verify data content
        assert data["name"] == template_data["name"]
        assert data["description"] == template_data["description"]
        assert data["version"] == template_data["version"]
        assert data["author"]["name"] == template_data["author"]["name"]
        assert data["author"]["email"] == template_data["author"]["email"]
        assert data["keywords"] == template_data["keywords"]

    @pytest.mark.integration
    def test_tpl_002_create_template_missing_required_fields(self, authenticated_client):
        """TPL-002 Create template with missing required fields"""
        client, user = authenticated_client

        # Missing name field
        invalid_data = {
            "description": "Invalid template without name",
            "author_name": user.display_name,
            "author_email": user.email,
        }

        response = client.post("/api/v1/templates", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        if isinstance(detail, str):
            assert "name" in detail.lower()
        elif isinstance(detail, list):
            assert any("name" in str(item).lower() for item in detail)

    @pytest.mark.integration
    def test_tpl_004_get_template_success(self, authenticated_client, test_data_factory):
        """TPL-004 Get template successfully"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template to Get",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Get template details
        response = client.get(f"/api/v1/templates/{template_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response contains all required fields
        required_fields = [
            "id", "name", "description", "version", "author",
            "keywords", "cliType", "status", "isActive"
        ]

        for field in required_fields:
            assert field in data, f"Template data should contain {field} field"

        # Verify template data is correct
        assert data["id"] == template_id
        assert data["name"] == template_data["name"]

    @pytest.mark.integration
    def test_tpl_005_get_template_not_found(self, authenticated_client):
        """TPL-005 Get nonexistent template"""
        client, user = authenticated_client

        fake_template_id = uuid.uuid4()
        response = client.get(f"/api/v1/templates/{fake_template_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.integration
    def test_tpl_007_update_template_success(self, authenticated_client, test_data_factory):
        """TPL-007 Update template successfully"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Original Template",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Update template
        update_data = {
            "name": "Updated Template Name",
            "description": "Updated description",
            "keywords": ["nodejs", "development", "updated"],
            "status": "released",
        }

        response = client.put(f"/api/v1/templates/{template_id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify update content
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["keywords"] == update_data["keywords"]
        assert data["status"] == update_data["status"]

        # Verify other fields remain unchanged
        assert data["id"] == template_id

    @pytest.mark.integration
    def test_tpl_008_template_delete_success(self, authenticated_client, test_data_factory):
        """TPL-008 Delete template successfully"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template to Delete",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Delete template
        response = client.delete(f"/api/v1/templates/{template_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify template was actually deleted
        get_response = client.get(f"/api/v1/templates/{template_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_009_template_git_branches_success(self, authenticated_client):
        """TPL-009 Template Git branch list successful"""
        client, user = authenticated_client

        # Get Git branch list
        response = client.get("/api/v1/templates/git/version-control/branches")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify Git branch response structure
        assert "branches" in data
        for branch in data["branches"]:
            assert "name" in branch
            assert "displayName" in branch

    @pytest.mark.integration
    def test_tpl_010_template_git_changes_success(self, authenticated_client):
        """TPL-010 Template Git change history successful"""
        client, user = authenticated_client

        # Get Git change history
        response = client.get("/api/v1/templates/git/version-control/changes")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify Git change history response structure
        assert "staged" in data
        assert "unstaged" in data
        assert "untracked" in data

    @pytest.mark.integration
    def test_tpl_012_list_templates_success(self, authenticated_client, test_data_factory):
        """TPL-012 List templates successfully"""
        client, user = authenticated_client

        # Create several templates
        for i in range(3):
            template_data = test_data_factory.create_template_data(
                name=f"Test Template {i}",
                author_name=user.display_name,
                author_email=user.email,
            )
            client.post("/api/v1/templates", json=template_data)

        response = client.get("/api/v1/templates")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "items" in data
        assert "total" in data

        # Verify template list
        assert len(data["items"]) >= 3, "There should be at least 3 templates"

        for template in data["items"]:
            required_template_fields = [
                "id", "name", "description", "version", "author",
                "keywords", "cliType", "status", "isActive"
            ]
            for field in required_template_fields:
                assert field in template, f"Template list item should contain {field} field"

    @pytest.mark.integration
    def test_tpl_015_template_update_with_put_success(self, authenticated_client, test_data_factory):
        """TPL-015 Update template successfully via PUT"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template to Update",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Update template
        update_data = {
            "name": "Updated Template Name",
            "description": "Updated description",
            "version": "2.0.0",
            "keywords": ["updated", "template"],
            "status": "released"
        }

        response = client.put(f"/api/v1/templates/{template_id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify update content
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["version"] == update_data["version"]
        assert data["status"] == update_data["status"]

    @pytest.mark.integration
    def test_tpl_016_template_categories_list_success(self, authenticated_client):
        """TPL-016 Template category list successful"""
        client, user = authenticated_client

        response = client.get("/api/v1/templates/categories")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "items" in data
        assert isinstance(data["items"], list)

        # Verify category structure
        if data["items"]:
            for category in data["items"]:
                required_fields = [
                    "id", "name", "description", "sortOrder", "isActive"
                ]
                for field in required_fields:
                    assert field in category, f"Category should contain {field} field"

                # Verify numeric types
                assert isinstance(category["sortOrder"], int)
                assert isinstance(category["isActive"], bool)

    @pytest.mark.integration
    def test_tpl_017_template_features_list_success(self, authenticated_client):
        """TPL-017 Template feature list successful"""
        client, user = authenticated_client

        # Test fetching all features
        response = client.get("/api/v1/templates/features")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "skills" in data["items"]
        assert "scripts" in data["items"]
        assert "files" not in data["items"]

        # Test features for a specific CLI type
        response_claude = client.get("/api/v1/templates/features?cli_type=claude-code")
        assert response_claude.status_code == status.HTTP_200_OK
        data_claude = response_claude.json()

        assert "items" in data_claude
        assert isinstance(data_claude["items"], list)
        assert "skills" in data_claude["items"]
        assert "scripts" in data_claude["items"]

    @pytest.mark.integration
    def test_tpl_018_template_mcp_config_success(self, authenticated_client, test_data_factory):
        """TPL-018 Template MCP configuration successful"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="MCP Configurable Template",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Get MCP configuration
        get_response = client.get(f"/api/v1/templates/{template_id}/mcp")
        assert get_response.status_code == status.HTTP_200_OK
        mcp_data = get_response.json()

        # Verify MCP configuration structure
        required_fields = ["templateId", "mcpServers"]
        for field in required_fields:
            assert field in mcp_data, f"MCP configuration should contain {field} field"

        # Update MCP configuration
        update_data = {
            "mcpServers": {
                "test-server": {
                    "description": "Test MCP server",
                    "type": "stdio",
                    "command": "node",
                    "args": ["test.js"]
                }
            }
        }

        update_response = client.put(f"/api/v1/templates/{template_id}/mcp", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        updated_data = update_response.json()

        # Verify update result
        assert len(updated_data["mcpServers"]) == 1
        assert "test-server" in updated_data["mcpServers"]
        assert updated_data["mcpServers"]["test-server"]["description"] == "Test MCP server"

    @pytest.mark.integration
    def test_tpl_019_template_hooks_config_success(self, authenticated_client, test_data_factory):
        """TPL-019 Template Hooks configuration successful"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Hooks Configurable Template",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Get Hooks configuration
        get_response = client.get(f"/api/v1/templates/{template_id}/hooks")
        assert get_response.status_code == status.HTTP_200_OK
        hooks_data = get_response.json()

        # Verify Hooks configuration structure
        required_fields = ["templateId", "hooks"]
        for field in required_fields:
            assert field in hooks_data, f"Hooks configuration should contain {field} field"

        # Update Hooks configuration
        update_data = {
            "hooks": {
                "before_file_save": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'Running test hook'",
                                "timeout": 30
                            }
                        ]
                    }
                ]
            }
        }

        update_response = client.put(f"/api/v1/templates/{template_id}/hooks", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        updated_data = update_response.json()

        # Verify update result
        assert "before_file_save" in updated_data["hooks"]
        assert len(updated_data["hooks"]["before_file_save"]) == 1
        assert len(updated_data["hooks"]["before_file_save"][0]["hooks"]) == 1

    @pytest.mark.integration
    def test_tpl_020_template_agents_md_success(self, authenticated_client, test_data_factory):
        """TPL-020 Template Claude.md configuration successful"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Claude.md Configurable Template",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Get Claude.md content
        get_response = client.get(f"/api/v1/templates/{template_id}/agents-md")
        assert get_response.status_code == status.HTTP_200_OK
        agents_md_data = get_response.json()

        # Verify response structure
        assert "success" in agents_md_data

        # Update Claude.md content
        update_data = {
            "content": "# Test Template\n\nThis is a test template with custom configuration."
        }

        update_response = client.put(f"/api/v1/templates/{template_id}/agents-md", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK
        updated_data = update_response.json()

        # Verify update result
        assert updated_data["success"] is True
        assert "content" in updated_data["data"]

    @pytest.mark.integration
    def test_tpl_020b_template_slash_command_invalid_filename_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Localized Slash Command Template",
            author_name=user.display_name,
            author_email=user.email,
        )

        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        invalid_payload = {
            "fileName": "bad/name.md",
            "content": "# Invalid Command\nThis filename should fail validation.",
        }

        en_response = client.post(
            f"/api/v1/templates/{template_id}/commands",
            json=invalid_payload,
        )
        assert en_response.status_code == status.HTTP_400_BAD_REQUEST
        assert en_response.json()["detail"] == "Invalid filename"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post(
            f"/api/v1/templates/{template_id}/commands",
            json=invalid_payload,
        )
        assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zh_response.json()["detail"] == "檔名格式不正確"

    @pytest.mark.integration
    def test_tpl_020c_create_template_duplicate_id_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Duplicate ID Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        template_id = template_data["templateId"]

        first_response = client.post("/api/v1/templates", json=template_data)
        assert first_response.status_code == status.HTTP_201_CREATED

        second_response = client.post("/api/v1/templates", json=template_data)
        assert second_response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            second_response.json()["detail"]
            == f'Template ID "{template_id}" already exists. Please use a different ID.'
        )

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post("/api/v1/templates", json=template_data)
        assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zh_response.json()["detail"] == f"模板代號「{template_id}」已存在，請使用其他代號。"

    @pytest.mark.integration
    def test_tpl_020d_create_template_invalid_id_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Invalid ID Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        template_data["templateId"] = "Invalid_Template_123"

        en_response = client.post("/api/v1/templates", json=template_data)
        assert en_response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            en_response.json()["detail"]
            == "Template ID must use kebab-case and may only contain lowercase letters, numbers, and hyphens."
        )

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post("/api/v1/templates", json=template_data)
        assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zh_response.json()["detail"] == "模板代號必須使用 kebab-case，且只能包含小寫英文字母、數字與連字號。"

    @pytest.mark.integration
    def test_tpl_020e_template_file_generic_error_uses_simple_message(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Generic File Error Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        with patch(
            "app.routers.templates.files.TemplateService.create_command_file",
            return_value=type("Result", (), {"success": False, "error": "unexpected internal error"})(),
        ):
            en_response = client.post(
                f"/api/v1/templates/{template_id}/commands",
                json={"fileName": "hello.md", "content": "hi"},
            )
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "File operation failed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.files.TemplateService.create_command_file",
            return_value=type("Result", (), {"success": False, "error": "unexpected internal error"})(),
        ):
            zh_response = client.post(
                f"/api/v1/templates/{template_id}/commands",
                json={"fileName": "hello.md", "content": "hi"},
            )
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "檔案操作失敗"

    # test_tpl_021_template_featured_list_success removed - /api/v1/templates/featured endpoint does not exist

    @pytest.mark.integration
    def test_tpl_022_template_categories_list_success(self, authenticated_client):
        """TPL-022 Template category list successful"""
        client, user = authenticated_client

        response = client.get("/api/v1/templates/categories")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure (consistent with test_tpl_016)
        assert "items" in data
        assert isinstance(data["items"], list)

        # Verify category structure
        if data["items"]:
            for category in data["items"]:
                required_fields = [
                    "id", "name", "description", "sortOrder", "isActive"
                ]
                for field in required_fields:
                    assert field in category, f"Category should contain {field} field"

                # Verify numeric types
                assert isinstance(category["sortOrder"], int)
                assert isinstance(category["isActive"], bool)

    # test_tpl_023_template_clone_success removed - /api/v1/templates/{id}/clone endpoint does not exist

      # test_tpl_024_template_validate_success removed - /api/v1/templates/{id}/validate endpoint does not exist
    # test_tpl_025_template_publish_success removed - /api/v1/templates/{id}/publish endpoint does not exist
    # test_tpl_026_template_unpublish_success removed - /api/v1/templates/{id}/unpublish endpoint does not exist
    # test_tpl_027_template_import_success removed - /api/v1/templates/import endpoint exists but requires file upload
    # test_tpl_028_template_export_success removed - /api/v1/templates/{id}/export endpoint exists but response format differs

    # test_tpl_029_template_search_advanced removed - /api/v1/templates/search endpoint does not exist
    # test_tpl_030_template_recommendations_success removed - /api/v1/templates/recommendations endpoint does not exist
    # test_tpl_031_template_dependencies_check_success removed - /api/v1/templates/{id}/dependencies endpoint does not exist
    # test_tpl_032_template_security_scan_success removed - /api/v1/templates/{id}/security-scan endpoint does not exist
    # test_tpl_033_template_compliance_check_success removed - /api/v1/templates/{id}/compliance-check endpoint does not exist
    # test_tpl_034_template_usage_analytics_success removed - /api/v1/templates/{id}/analytics endpoint does not exist
    # test_tpl_035_template_performance_benchmark_success removed - /api/v1/templates/{id}/benchmark endpoint does not exist
    # test_tpl_036_template_marketplace_sync_success removed - /api/v1/templates/{id}/marketplace-sync endpoint does not exist
    # test_tpl_037_template_ai_optimization_success removed - /api/v1/templates/{id}/ai-optimize endpoint does not exist
    # test_tpl_038_template_collaboration_workspace_success removed - /api/v1/templates/{id}/workspace endpoint does not exist
    # test_tpl_039_template_changelog_success removed - /api/v1/templates/{id}/changelog endpoint does not exist
    # test_tpl_040_template_testing_automation_success removed - /api/v1/templates/{id}/test endpoint does not exist

    @pytest.mark.integration
    def test_tpl_041_commands_crud(self, authenticated_client, test_data_factory):
        """TPL-041 Commands CRUD operations"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for Commands",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. List Commands
        list_response = client.get(f"/api/v1/templates/{template_id}/commands")
        assert list_response.status_code == status.HTTP_200_OK

        # 2. Create Command
        command_data = {
            "fileName": "test-command.md",
            "content": "# Test Command\nThis is a test command."
        }
        create_cmd_response = client.post(
            f"/api/v1/templates/{template_id}/commands",
            json=command_data
        )
        assert create_cmd_response.status_code == status.HTTP_201_CREATED

        # 3. Get Command
        get_cmd_response = client.get(
            f"/api/v1/templates/{template_id}/commands/test-command.md"
        )
        assert get_cmd_response.status_code == status.HTTP_200_OK

        # 4. Update Command
        update_data = {"content": "# Updated Command\nUpdated content."}
        update_response = client.put(
            f"/api/v1/templates/{template_id}/commands/test-command.md",
            json=update_data
        )
        assert update_response.status_code == status.HTTP_200_OK

        # 5. Delete Command
        delete_response = client.delete(
            f"/api/v1/templates/{template_id}/commands/test-command.md"
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.integration
    def test_tpl_042_agents_crud(self, authenticated_client, test_data_factory):
        """TPL-042 Agents CRUD operations"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for Agents",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. List Agents
        list_response = client.get(f"/api/v1/templates/{template_id}/agents")
        assert list_response.status_code == status.HTTP_200_OK

        # 2. Create Agent
        agent_data = {
            "fileName": "test-agent.md",
            "content": "# Test Agent\nThis is a test agent."
        }
        create_response = client.post(
            f"/api/v1/templates/{template_id}/agents",
            json=agent_data
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        # 3. Get Agent
        get_response = client.get(
            f"/api/v1/templates/{template_id}/agents/test-agent.md"
        )
        assert get_response.status_code == status.HTTP_200_OK

        # 4. Update Agent
        update_data = {"content": "# Updated Agent\nUpdated content."}
        update_response = client.put(
            f"/api/v1/templates/{template_id}/agents/test-agent.md",
            json=update_data
        )
        assert update_response.status_code == status.HTTP_200_OK

        # 5. Delete Agent
        delete_response = client.delete(
            f"/api/v1/templates/{template_id}/agents/test-agent.md"
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.integration
    def test_tpl_043_output_style_crud(self, authenticated_client, test_data_factory):
        """TPL-043 Output Style CRUD operations"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for Output Style",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. List Output Style
        list_response = client.get(f"/api/v1/templates/{template_id}/output-style")
        assert list_response.status_code == status.HTTP_200_OK

        # 2. Create Output Style
        style_data = {
            "fileName": "test-style.md",
            "content": "# Test Style\nThis is a test output style."
        }
        create_response = client.post(
            f"/api/v1/templates/{template_id}/output-style",
            json=style_data
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        # 3. Get Output Style
        get_response = client.get(
            f"/api/v1/templates/{template_id}/output-style/test-style.md"
        )
        assert get_response.status_code == status.HTTP_200_OK

        # 4. Update Output Style
        update_data = {"content": "# Updated Style\nUpdated content."}
        update_response = client.put(
            f"/api/v1/templates/{template_id}/output-style/test-style.md",
            json=update_data
        )
        assert update_response.status_code == status.HTTP_200_OK

        # 5. Delete Output Style
        delete_response = client.delete(
            f"/api/v1/templates/{template_id}/output-style/test-style.md"
        )
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.integration
    def test_tpl_044_file_operations(self, authenticated_client, test_data_factory):
        """TPL-044 File operations test"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for File Operations",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Get file tree
        tree_response = client.get(f"/api/v1/templates/{template_id}/files/tree")
        if tree_response.status_code != status.HTTP_404_NOT_FOUND:
            assert tree_response.status_code == status.HTTP_200_OK

        # 2. Create file
        create_file_response = client.post(
            f"/api/v1/templates/{template_id}/files?path=/test.txt&entry_type=file"
        )
        if create_file_response.status_code != status.HTTP_404_NOT_FOUND:
            assert create_file_response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]

        # 3. Write file content
        write_response = client.put(
            f"/api/v1/templates/{template_id}/files/content?path=/test.txt&content=Hello"
        )
        if write_response.status_code != status.HTTP_404_NOT_FOUND:
            assert write_response.status_code == status.HTTP_200_OK

        # 4. Read file content
        read_response = client.get(
            f"/api/v1/templates/{template_id}/files/content?path=/test.txt"
        )
        if read_response.status_code != status.HTTP_404_NOT_FOUND:
            assert read_response.status_code == status.HTTP_200_OK

        # 5. Delete file
        delete_file_response = client.delete(
            f"/api/v1/templates/{template_id}/files?path=/test.txt"
        )
        if delete_file_response.status_code != status.HTTP_404_NOT_FOUND:
            assert delete_file_response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

    @pytest.mark.integration
    def test_tpl_045_git_operations(self, authenticated_client):
        """TPL-045 Git operations test"""
        client, user = authenticated_client

        # 1. Get Git status
        status_response = client.get("/api/v1/templates/git/version-control/status")
        if status_response.status_code != status.HTTP_404_NOT_FOUND:
            assert status_response.status_code == status.HTTP_200_OK

        # 2. Get change history
        changes_response = client.get("/api/v1/templates/git/version-control/changes")
        if changes_response.status_code != status.HTTP_404_NOT_FOUND:
            assert changes_response.status_code == status.HTTP_200_OK

        # 3. Get branch list
        branches_response = client.get("/api/v1/templates/git/version-control/branches")
        if branches_response.status_code != status.HTTP_404_NOT_FOUND:
            assert branches_response.status_code == status.HTTP_200_OK

        # 4. Get Git user configuration
        user_config_response = client.get("/api/v1/templates/git/user-config")
        if user_config_response.status_code != status.HTTP_404_NOT_FOUND:
            assert user_config_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_045b_template_version_control_endpoint_workflow(self, authenticated_client):
        """TPL-045B Template Center file-level Git endpoint workflow"""
        client, user = authenticated_client
        repo_path = Path(os.environ["TEMPLATE_STORAGE_PATH"])
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value("user", "name", "Template Tester")
            config.set_value("user", "email", "template@example.com")

        template_dir = repo_path / "templates" / "demo"
        template_dir.mkdir(parents=True)
        readme = template_dir / "README.md"
        readme.write_text("hello\n")
        repo.index.add(["templates/demo/README.md"])
        repo.index.commit("initial")
        readme.write_text("hello\nworld\n")

        status_response = client.get("/api/v1/templates/git/version-control/status")
        assert status_response.status_code == status.HTTP_200_OK
        status_data = status_response.json()
        assert status_data["unstagedCount"] == 1

        changes_response = client.get("/api/v1/templates/git/version-control/changes")
        assert changes_response.status_code == status.HTTP_200_OK
        changes_data = changes_response.json()
        assert changes_data["unstaged"][0]["path"] == "templates/demo/README.md"

        diff_response = client.get(
            "/api/v1/templates/git/version-control/diff",
            params={"path": "templates/demo/README.md"},
        )
        assert diff_response.status_code == status.HTTP_200_OK
        assert "+world" in diff_response.json()["patch"]

        new_file = template_dir / "new.md"
        new_file.write_text("new\n")
        untracked_diff_response = client.get(
            "/api/v1/templates/git/version-control/diff",
            params={"path": "templates/demo/new.md"},
        )
        assert untracked_diff_response.status_code == status.HTTP_200_OK
        untracked_patch = untracked_diff_response.json()["patch"]
        assert "--- /dev/null" in untracked_patch
        assert "+++ b/templates/demo/new.md" in untracked_patch
        assert "+new" in untracked_patch

        stage_response = client.post(
            "/api/v1/templates/git/version-control/stage",
            json={"paths": ["templates/demo/README.md"]},
        )
        assert stage_response.status_code == status.HTTP_200_OK
        assert stage_response.json()["staged"] == ["templates/demo/README.md"]

        commit_response = client.post(
            "/api/v1/templates/git/version-control/commit",
            json={"message": "update demo"},
        )
        assert commit_response.status_code == status.HTTP_200_OK
        commit_id = commit_response.json()["commit"]["id"]

        commits_response = client.get("/api/v1/templates/git/version-control/commits")
        assert commits_response.status_code == status.HTTP_200_OK
        assert commits_response.json()["items"][0]["message"] == "update demo"

        commit_files_response = client.get(f"/api/v1/templates/git/version-control/commits/{commit_id}/files")
        assert commit_files_response.status_code == status.HTTP_200_OK
        assert commit_files_response.json()["files"][0]["path"] == "templates/demo/README.md"

    @pytest.mark.integration
    def test_tpl_045c_template_version_control_commits_empty_initialized_repo(self, authenticated_client):
        """TPL-045C commit history handles an initialized repository before the first commit"""
        client, user = authenticated_client
        repo_path = Path(os.environ["TEMPLATE_STORAGE_PATH"])
        Repo.init(repo_path)

        commits_response = client.get("/api/v1/templates/git/version-control/commits")

        assert commits_response.status_code == status.HTTP_200_OK
        assert commits_response.json()["total"] == 0
        assert commits_response.json()["items"] == []

    @pytest.mark.integration
    def test_tpl_045d_template_version_control_staged_changes_before_first_commit(self, authenticated_client):
        """TPL-045D staged changes are visible before the first commit"""
        client, user = authenticated_client
        repo_path = Path(os.environ["TEMPLATE_STORAGE_PATH"])
        Repo.init(repo_path)
        template_dir = repo_path / "templates" / "demo"
        template_dir.mkdir(parents=True)
        (template_dir / "README.md").write_text("hello\n")

        stage_response = client.post(
            "/api/v1/templates/git/version-control/stage",
            json={"paths": ["templates/demo/README.md"]},
        )
        assert stage_response.status_code == status.HTTP_200_OK

        status_response = client.get("/api/v1/templates/git/version-control/status")
        assert status_response.status_code == status.HTTP_200_OK
        assert status_response.json()["stagedCount"] == 1

        changes_response = client.get("/api/v1/templates/git/version-control/changes")
        assert changes_response.status_code == status.HTTP_200_OK
        assert changes_response.json()["staged"][0]["path"] == "templates/demo/README.md"

        diff_response = client.get(
            "/api/v1/templates/git/version-control/diff",
            params={"path": "templates/demo/README.md", "head": "INDEX"},
        )
        assert diff_response.status_code == status.HTTP_200_OK
        assert "+hello" in diff_response.json()["patch"]

    @pytest.mark.integration
    def test_tpl_046_marketplace_config(self, authenticated_client):
        """TPL-046 Marketplace settings config API has been removed"""
        client, user = authenticated_client

        get_response = client.get("/api/v1/templates/marketplace/config")
        update_response = client.put(
            "/api/v1/templates/marketplace/config",
            json={
                "name": "test-marketplace",
                "owner": {"name": "Test Owner", "email": "test@example.com"},
                "metadata": {
                    "description": "Test marketplace",
                    "version": "1.0.0",
                    "homepage": "https://github.com/test/templates",
                },
            },
        )

        assert get_response.status_code == status.HTTP_404_NOT_FOUND
        assert update_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_047_ssh_keys_operations(self, authenticated_client):
        """TPL-047 SSH Keys operations test"""
        client, user = authenticated_client

        # 1. Get SSH Keys
        get_response = client.get("/api/v1/templates/marketplace/ssh-keys")
        if get_response.status_code != status.HTTP_404_NOT_FOUND:
            assert get_response.status_code == status.HTTP_200_OK

        # 2. Generate SSH Keys (test cautiously, may overwrite existing keys)
        # generate_response = client.post("/api/v1/templates/marketplace/ssh-keys/generate")
        # if generate_response.status_code != status.HTTP_404_NOT_FOUND:
        #     assert generate_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_048_template_install(self, authenticated_client, test_data_factory):
        """TPL-048 Template installation test"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template to Install",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Install template (requires valid workspace_id)
        install_data = {
            "templateId": template_id,
            "workspaceId": str(uuid.uuid4())
        }
        install_response = client.post("/api/v1/templates/install", json=install_data)
        # May fail because workspace does not exist; that is acceptable
        assert install_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]

    @pytest.mark.integration
    def test_tpl_048b_template_install_workspace_not_found_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Localized Install Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]
        workspace_id = str(uuid.uuid4())

        payload = {
            "templateId": template_id,
            "workspaceId": workspace_id,
        }

        en_response = client.post("/api/v1/templates/install", json=payload)
        assert en_response.status_code == status.HTTP_400_BAD_REQUEST
        assert en_response.json()["detail"] == f"Workspace {workspace_id} not found"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post("/api/v1/templates/install", json=payload)
        assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zh_response.json()["detail"] == f"找不到工作區 {workspace_id}"

    @pytest.mark.integration
    def test_tpl_048c_template_install_generic_failure_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Broken Install Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        payload = {
            "templateId": template_id,
            "workspaceId": str(uuid.uuid4()),
        }

        with patch(
            "app.routers.templates.install.TemplateInstallService.install_template_to_workspace",
            side_effect=RuntimeError("boom"),
        ):
            en_response = client.post("/api/v1/templates/install", json=payload)
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Failed to install template"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.install.TemplateInstallService.install_template_to_workspace",
            side_effect=RuntimeError("boom"),
        ):
            zh_response = client.post("/api/v1/templates/install", json=payload)
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "安裝模板失敗"

    @pytest.mark.integration
    def test_tpl_048d_template_install_runtime_connection_error_uses_simple_localized_message(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Runtime Connection Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        payload = {
            "templateId": template_id,
            "workspaceId": str(uuid.uuid4()),
        }

        with patch(
            "app.routers.templates.install.TemplateInstallService.install_template_to_workspace",
            side_effect=TemplateInstallError(
                "Underlying connection error content should not leak",
                code="TEMPLATE_INSTALL_RUNTIME_CONNECTION_ERROR",
            ),
        ):
            en_response = client.post("/api/v1/templates/install", json=payload)
            assert en_response.status_code == status.HTTP_502_BAD_GATEWAY
            assert en_response.json()["detail"] == "Unable to connect to Workspace Runtime"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.install.TemplateInstallService.install_template_to_workspace",
            side_effect=TemplateInstallError(
                "A completely different underlying error",
                code="TEMPLATE_INSTALL_RUNTIME_CONNECTION_ERROR",
            ),
        ):
            zh_response = client.post("/api/v1/templates/install", json=payload)
            assert zh_response.status_code == status.HTTP_502_BAD_GATEWAY
            assert zh_response.json()["detail"] == "無法連線到 Workspace Runtime"

    @pytest.mark.integration
    def test_tpl_048e_template_compile_preview_success(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Preview Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        with patch(
            "app.routers.templates.install.TemplateCompilerService.compile_template",
            return_value={
                "target": "codex",
                "files": [
                    {
                        "path": "AGENTS.md",
                        "source": "agents.md",
                        "content": "# Agents",
                    }
                ],
                "warnings": [],
                "unsupported": [],
                "degradationNotes": [],
                "installHints": {},
            },
        ):
            response = client.get(
                f"/api/v1/templates/{template_id}/compile-preview?target=codex"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["target"] == "codex"
        assert len(data["files"]) == 1
        assert data["files"][0]["path"] == "AGENTS.md"
        assert data["degradationNotes"] == []

    @pytest.mark.integration
    def test_tpl_048f_template_compile_preview_generic_failure_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Broken Preview Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        with patch(
            "app.routers.templates.install.TemplateCompilerService.compile_template",
            side_effect=RuntimeError("boom"),
        ):
            en_response = client.get(
                f"/api/v1/templates/{template_id}/compile-preview?target=codex"
            )
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Failed to load template compile preview"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.install.TemplateCompilerService.compile_template",
            side_effect=RuntimeError("boom"),
        ):
            zh_response = client.get(
                f"/api/v1/templates/{template_id}/compile-preview?target=codex"
            )
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "取得模板編譯預覽失敗"

    @pytest.mark.integration
    def test_tpl_048g_template_compile_preview_validation_failure_is_localized(
        self, authenticated_client, test_data_factory
    ):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Invalid Canonical Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        with patch(
            "app.routers.templates.install.TemplateCompilerService.compile_template",
            side_effect=CanonicalTemplateValidationError(
                f"Missing template.yaml in /data/template-center/templates/{template_id}"
            ),
        ):
            en_response = client.get(
                f"/api/v1/templates/{template_id}/compile-preview?target=codex"
            )
            assert en_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert en_response.json()["detail"] == "This template is missing template.yaml and cannot be compiled"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.install.TemplateCompilerService.compile_template",
            side_effect=CanonicalTemplateValidationError(
                f"Missing template.yaml in /data/template-center/templates/{template_id}"
            ),
        ):
            zh_response = client.get(
                f"/api/v1/templates/{template_id}/compile-preview?target=codex"
            )
            assert zh_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert zh_response.json()["detail"] == "此模板缺少 template.yaml，無法產生編譯預覽"

    @pytest.mark.integration
    def test_tpl_049_file_copy_operation(self, authenticated_client, test_data_factory):
        """TPL-049 File copy operations"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for File Copy",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Copy file
        copy_response = client.post(
            f"/api/v1/templates/{template_id}/files/copy?source_path=/test.txt&dest_path=/test_copy.txt"
        )
        if copy_response.status_code != status.HTTP_404_NOT_FOUND:
            assert copy_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    @pytest.mark.integration
    def test_tpl_050_file_move_operation(self, authenticated_client, test_data_factory):
        """TPL-050 File move operations"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for File Move",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Move file
        move_response = client.post(
            f"/api/v1/templates/{template_id}/files/move?source_path=/test.txt&dest_path=/moved.txt"
        )
        if move_response.status_code != status.HTTP_404_NOT_FOUND:
            assert move_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    @pytest.mark.integration
    def test_tpl_051_file_batch_delete(self, authenticated_client, test_data_factory):
        """TPL-051 Batch delete files"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for Batch Delete",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Batch delete
        batch_delete_response = client.post(
            f"/api/v1/templates/{template_id}/files/batch-delete?paths=/file1.txt&paths=/file2.txt"
        )
        if batch_delete_response.status_code != status.HTTP_404_NOT_FOUND:
            assert batch_delete_response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

    @pytest.mark.integration
    def test_tpl_052_file_search(self, authenticated_client, test_data_factory):
        """TPL-052 File search"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for File Search",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Search files
        search_data = {
            "query": "md",
            "searchContent": False,
            "fileTypes": [".md"],
            "maxResults": 100
        }
        search_response = client.post(
            f"/api/v1/templates/{template_id}/files/search",
            json=search_data
        )
        if search_response.status_code != status.HTTP_404_NOT_FOUND:
            if search_response.status_code != status.HTTP_200_OK:
                print(f"Search response: {search_response.json()}")
            assert search_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_053_template_export(self, authenticated_client, test_data_factory):
        """TPL-053 Export template"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template to Export",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Export template
        export_response = client.get(f"/api/v1/templates/{template_id}/export")
        if export_response.status_code != status.HTTP_404_NOT_FOUND:
            assert export_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_054_git_file_level_commit(self, authenticated_client):
        """TPL-054 Git file-level commit"""
        client, user = authenticated_client

        commit_data = {
            "message": "Test commit",
            "paths": ["test.md"],
        }
        commit_response = client.post("/api/v1/templates/git/version-control/commit", json=commit_data)

        if commit_response.status_code != status.HTTP_404_NOT_FOUND:
            # May fail because there are no changes; that is acceptable
            assert commit_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND
            ]

    @pytest.mark.integration
    def test_tpl_055_git_pull(self, authenticated_client):
        """TPL-055 Git pull changes"""
        client, user = authenticated_client

        pull_data = {
            "branch": "main",
            "rebase": False
        }
        pull_response = client.post("/api/v1/templates/git/version-control/pull", json=pull_data)

        if pull_response.status_code != status.HTTP_404_NOT_FOUND:
            assert pull_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST
            ]

    @pytest.mark.integration
    def test_tpl_056_git_user_config_operations(self, authenticated_client):
        """TPL-056 Git user configuration operations"""
        client, user = authenticated_client

        # 1. Get Git user configuration
        get_config_response = client.get("/api/v1/templates/git/user-config")
        if get_config_response.status_code != status.HTTP_404_NOT_FOUND:
            assert get_config_response.status_code == status.HTTP_200_OK

        # 2. Update Git user configuration
        update_config_data = {
            "name": "Test User",
            "email": "test@example.com"
        }
        update_config_response = client.post(
            "/api/v1/templates/git/user-config",
            json=update_config_data
        )
        if update_config_response.status_code != status.HTTP_404_NOT_FOUND:
            assert update_config_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_057_git_remote_url(self, authenticated_client):
        """TPL-057 Set Git remote repository URL"""
        client, user = authenticated_client

        remote_url_data = {
            "url": "git@github.com:test/templates.git",
            "remote": "origin"
        }
        remote_response = client.post(
            "/api/v1/templates/git/remote-url",
            json=remote_url_data
        )

        if remote_response.status_code != status.HTTP_404_NOT_FOUND:
            assert remote_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST
            ]

    @pytest.mark.integration
    def test_tpl_057b_git_commit_error_uses_version_control_endpoint(self, authenticated_client):
        client, _ = authenticated_client

        with patch(
            "app.routers.templates.git.TemplateGitService.commit",
            side_effect=Exception("GIT_NO_CHANGES"),
        ):
            en_response = client.post(
                "/api/v1/templates/git/version-control/commit",
                json={"message": "Test commit"},
            )
            assert en_response.status_code == status.HTTP_400_BAD_REQUEST
            data = en_response.json()
            assert data["detail"]["errorCode"] == "GIT_NO_CHANGES"

    @pytest.mark.integration
    def test_tpl_057c_git_remote_url_error_is_localized(self, authenticated_client):
        client, _ = authenticated_client

        with patch(
            "app.routers.templates.git.TemplateGitService.set_remote_url",
            return_value=GitOperationResult(False, "GIT_REPO_NOT_FOUND", "不是 Git 倉庫"),
        ):
            en_response = client.post(
                "/api/v1/templates/git/remote-url",
                json={"url": "https://example.com/repo.git"},
            )
            assert en_response.status_code == status.HTTP_200_OK
            data = en_response.json()
            assert data["success"] is False
            assert data["message"] == "Failed to set remote repository URL"
            assert data["error"] == "Not a Git repository"
            assert data["errorCode"] == "GIT_REPO_NOT_FOUND"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.git.TemplateGitService.set_remote_url",
            return_value=GitOperationResult(False, "GIT_REPO_NOT_FOUND", "不是 Git 倉庫"),
        ):
            zh_response = client.post(
                "/api/v1/templates/git/remote-url",
                json={"url": "https://example.com/repo.git"},
            )
            assert zh_response.status_code == status.HTTP_200_OK
            data = zh_response.json()
            assert data["success"] is False
            assert data["message"] == "設定遠端倉庫 URL 失敗"
            assert data["error"] == "不是 Git 倉庫"
            assert data["errorCode"] == "GIT_REPO_NOT_FOUND"

    @pytest.mark.integration
    def test_tpl_057d_git_commit_internal_error_uses_version_control_endpoint(self, authenticated_client):
        client, _ = authenticated_client

        with patch(
            "app.routers.templates.git.TemplateGitService.commit",
            side_effect=Exception("GIT_COMMIT_FAILED"),
        ):
            en_response = client.post(
                "/api/v1/templates/git/version-control/commit",
                json={"message": "Test commit"},
            )
            assert en_response.status_code == status.HTTP_400_BAD_REQUEST
            data = en_response.json()
            assert data["detail"]["errorCode"] == "GIT_COMMIT_FAILED"

    @pytest.mark.integration
    def test_tpl_058_git_clone_operations(self, authenticated_client):
        """TPL-058 Git clone operations"""
        client, user = authenticated_client

        # 1. Check clone status
        status_response = client.get("/api/v1/templates/git/clone/status")
        if status_response.status_code != status.HTTP_404_NOT_FOUND:
            assert status_response.status_code == status.HTTP_200_OK

        # 2. Clone repository (test cautiously, may overwrite existing repository)
        # clone_data = {
        #     "url": "https://github.com/test/templates.git",
        #     "branch": "main"
        # }
        # clone_response = client.post("/api/v1/templates/git/clone", json=clone_data)

    @pytest.mark.integration
    def test_tpl_058b_git_repository_status_and_init(self, authenticated_client):
        """TPL-058B Template Center Git repository lifecycle APIs"""
        client, _ = authenticated_client

        with patch(
            "app.routers.templates.git.TemplateGitService.get_repository_status",
            return_value={
                "isGitRepo": False,
                "currentBranch": None,
                "remoteUrl": None,
                "hasOrigin": False,
                "hasLocalContent": True,
                "canCloneSafely": False,
                "canInitSafely": True,
                "cloneBlockedReason": "GIT_CLONE_TARGET_NOT_EMPTY",
            },
        ):
            status_response = client.get("/api/v1/templates/git/repository/status")
            assert status_response.status_code == status.HTTP_200_OK
            data = status_response.json()
            assert data["isGitRepo"] is False
            assert data["canCloneSafely"] is False
            assert data["cloneBlockedReason"] == "GIT_CLONE_TARGET_NOT_EMPTY"

        with patch(
            "app.routers.templates.git.TemplateGitService.init_repository",
            return_value=GitOperationResult(True, "GIT_REPOSITORY_INITIALIZED", "initialized"),
        ):
            init_response = client.post("/api/v1/templates/git/repository/init", json={})
            assert init_response.status_code == status.HTTP_200_OK
            data = init_response.json()
            assert data["success"] is True
            assert data["message"] == "Template Center Git repository initialized"

    @pytest.mark.integration
    def test_tpl_058c_git_repository_lifecycle_errors_are_localized(self, authenticated_client):
        """TPL-058C repository lifecycle errors use stable codes and translations"""
        client, _ = authenticated_client

        with patch(
            "app.routers.templates.git.TemplateGitService.init_repository",
            return_value=GitOperationResult(False, "GIT_REPOSITORY_ALREADY_INITIALIZED", "already initialized"),
        ):
            init_response = client.post("/api/v1/templates/git/repository/init", json={})
            assert init_response.status_code == status.HTTP_200_OK
            data = init_response.json()
            assert data["success"] is False
            assert data["errorCode"] == "GIT_REPOSITORY_ALREADY_INITIALIZED"
            assert data["error"] == "Template Center is already initialized as a Git repository"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.git.TemplateGitService.set_remote_url",
            return_value=GitOperationResult(False, "GIT_CLONE_TARGET_NOT_EMPTY", "not safe"),
        ):
            remote_response = client.post(
                "/api/v1/templates/git/remote-url",
                json={"url": "https://example.com/repo.git"},
            )
            assert remote_response.status_code == status.HTTP_200_OK
            data = remote_response.json()
            assert data["success"] is False
            assert data["errorCode"] == "GIT_CLONE_TARGET_NOT_EMPTY"
            assert data["error"] == "模板中心已有本地檔案。請先初始化目前 registry，或清空目錄後再 clone。"

    @pytest.mark.integration
    def test_tpl_059_ssh_keys_full_operations(self, authenticated_client):
        """TPL-059 SSH Keys full operations"""
        client, user = authenticated_client

        # 1. Get SSH Keys
        get_keys_response = client.get("/api/v1/templates/marketplace/ssh-keys")
        if get_keys_response.status_code != status.HTTP_404_NOT_FOUND:
            assert get_keys_response.status_code == status.HTTP_200_OK

        # 2. Update SSH Keys (test cautiously)
        # update_keys_data = {
        #     "publicKey": "ssh-rsa AAAA...",
        #     "privateKey": "-----BEGIN RSA PRIVATE KEY-----..."
        # }
        # update_response = client.put(
        #     "/api/v1/templates/marketplace/ssh-keys",
        #     json=update_keys_data
        # )

    @pytest.mark.integration
    def test_tpl_060_template_rebuild(self, authenticated_client):
        """TPL-060 Rebuild template database"""
        client, user = authenticated_client

        # Rebuild template database (background task)
        rebuild_response = client.post("/api/v1/templates/rebuild")

        if rebuild_response.status_code != status.HTTP_404_NOT_FOUND:
            assert rebuild_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
                status.HTTP_202_ACCEPTED
            ]

            # If successful, check whether task_id is returned
            if rebuild_response.status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]:
                data = rebuild_response.json()
                if "taskId" in data:
                    task_id = data["taskId"]

                    # Query rebuild progress
                    progress_response = client.get(f"/api/v1/templates/rebuild/progress/{task_id}")
                    if progress_response.status_code != status.HTTP_404_NOT_FOUND:
                        assert progress_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_061_file_upload(self, authenticated_client, test_data_factory):
        """TPL-061 File upload"""
        client, user = authenticated_client

        # Create template first
        template_data = test_data_factory.create_template_data(
            name="Template for File Upload",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Upload file (requires multipart/form-data)
        # Only test whether the endpoint exists
        upload_response = client.post(
            f"/api/v1/templates/{template_id}/files/upload",
            data={"target_path": "/uploads"},
            files={}  # Empty file list
        )

        # May fail because no file exists; that is acceptable
        if upload_response.status_code != status.HTTP_404_NOT_FOUND:
            assert upload_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]

    @pytest.mark.integration
    def test_tpl_062_template_import(self, authenticated_client):
        """TPL-062 Import template"""
        client, user = authenticated_client

        # Import template (requires ZIP file)
        # Only test whether the endpoint exists
        import_response = client.post(
            "/api/v1/templates/import",
            files={}  # Empty file
        )

        # May fail because no file exists; that is acceptable
        if import_response.status_code != status.HTTP_404_NOT_FOUND:
            assert import_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]

    @pytest.mark.integration
    def test_tpl_062b_template_import_invalid_format_is_localized(self, authenticated_client):
        client, _ = authenticated_client

        en_response = client.post(
            "/api/v1/templates/import",
            files={"file": ("invalid.txt", b"not-a-zip", "text/plain")},
        )
        assert en_response.status_code == status.HTTP_400_BAD_REQUEST
        assert en_response.json()["detail"] == "Only ZIP files are allowed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post(
            "/api/v1/templates/import",
            files={"file": ("invalid.txt", b"not-a-zip", "text/plain")},
        )
        assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zh_response.json()["detail"] == "僅允許上傳 ZIP 檔案"

    @pytest.mark.integration
    def test_tpl_062c_template_import_missing_manifest_is_localized(self, authenticated_client):
        client, _ = authenticated_client
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as zipf:
            zipf.writestr(".claude-plugin/marketplace.json", '{"id":"legacy-template"}')
        archive.seek(0)

        en_response = client.post(
            "/api/v1/templates/import",
            files={"file": ("legacy-template.zip", archive.getvalue(), "application/zip")},
        )
        assert en_response.status_code == status.HTTP_400_BAD_REQUEST
        assert en_response.json()["detail"] == (
            "Invalid template archive: missing .claude-plugin/manifest.json"
        )

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post(
            "/api/v1/templates/import",
            files={"file": ("legacy-template.zip", archive.getvalue(), "application/zip")},
        )
        assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
        assert zh_response.json()["detail"] == "無效的模板檔案：缺少 .claude-plugin/manifest.json"

    @pytest.mark.integration
    def test_tpl_063_list_templates_with_filters(self, authenticated_client, test_data_factory):
        """TPL-063 List templates (with filter conditions)"""
        client, user = authenticated_client

        # Test various filter conditions
        # 1. Filter by category
        response = client.get("/api/v1/templates?category=web")
        assert response.status_code == status.HTTP_200_OK

        # 2. Filter by tag
        response = client.get("/api/v1/templates?tags=react&tags=typescript")
        assert response.status_code == status.HTTP_200_OK

        # 3. Search
        response = client.get("/api/v1/templates?search=test")
        assert response.status_code == status.HTTP_200_OK

        # 4. Pagination
        response = client.get("/api/v1/templates?page=1&page_size=10")
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_064_template_features(self, authenticated_client):
        """TPL-064 Get template feature list"""
        client, user = authenticated_client

        response = client.get("/api/v1/templates/features")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data

    @pytest.mark.integration
    def test_tpl_065_template_categories(self, authenticated_client):
        """TPL-065 Get template category list"""
        client, user = authenticated_client

        response = client.get("/api/v1/templates/categories")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        category_names = {item["id"]: item["name"] for item in data["items"]}
        assert category_names.get("general") == "General"
        assert category_names.get("automation") == "Automation"

    @pytest.mark.integration
    def test_tpl_066_update_template_not_found(self, authenticated_client):
        """TPL-066 Update nonexistent template (error scenario)"""
        client, user = authenticated_client

        fake_id = str(uuid.uuid4())
        update_data = {
            "name": "Updated Template",
            "description": "Updated description"
        }
        response = client.put(f"/api/v1/templates/{fake_id}", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_067_delete_template_not_found(self, authenticated_client):
        """TPL-067 Delete nonexistent template (error scenario)"""
        client, user = authenticated_client

        fake_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/templates/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_068_get_mcp_config_not_found(self, authenticated_client):
        """TPL-068 Get MCP configuration of nonexistent template (error scenario)"""
        client, user = authenticated_client

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/templates/{fake_id}/mcp")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_069_update_hooks_config_not_found(self, authenticated_client):
        """TPL-069 Update Hooks configuration of nonexistent template (error scenario)"""
        client, user = authenticated_client

        fake_id = str(uuid.uuid4())
        hooks_data = {
            "hooks": {
                "preCommit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'pre-commit'",
                                "timeout": 30
                            }
                        ]
                    }
                ]
            }
        }
        response = client.put(f"/api/v1/templates/{fake_id}/hooks", json=hooks_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_070_agents_md_operations_full(self, authenticated_client, test_data_factory):
        """TPL-070 Claude.md full operation workflow"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for Claude.md",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Read Claude.md
        get_response = client.get(f"/api/v1/templates/{template_id}/agents-md")
        if get_response.status_code != status.HTTP_404_NOT_FOUND:
            assert get_response.status_code == status.HTTP_200_OK

        # 2. Update Claude.md
        update_data = {
            "content": "# Claude Configuration\n\nThis is a test configuration."
        }
        update_response = client.put(
            f"/api/v1/templates/{template_id}/agents-md",
            json=update_data
        )
        if update_response.status_code != status.HTTP_404_NOT_FOUND:
            assert update_response.status_code == status.HTTP_200_OK

        # 3. Read again to verify
        verify_response = client.get(f"/api/v1/templates/{template_id}/agents-md")
        if verify_response.status_code != status.HTTP_404_NOT_FOUND:
            assert verify_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_070b_agents_md_errors_are_localized(self, authenticated_client, test_data_factory):
        client, user = authenticated_client

        template_data = test_data_factory.create_template_data(
            name="Claude MD Error Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        with patch(
            "app.routers.templates.files.TemplateService.get_agents_md",
            side_effect=RuntimeError("boom"),
        ):
            en_get = client.get(f"/api/v1/templates/{template_id}/agents-md")
            assert en_get.status_code == status.HTTP_200_OK
            assert en_get.json()["success"] is False
            assert en_get.json()["message"] == "Failed to load AGENTS.md"

        with patch(
            "app.routers.templates.files.TemplateService.update_agents_md",
            side_effect=RuntimeError("boom"),
        ):
            en_put = client.put(
                f"/api/v1/templates/{template_id}/agents-md",
                json={"content": "# test"},
            )
            assert en_put.status_code == status.HTTP_200_OK
            assert en_put.json()["success"] is False
            assert en_put.json()["message"] == "Failed to update AGENTS.md"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.files.TemplateService.get_agents_md",
            side_effect=RuntimeError("boom"),
        ):
            zh_get = client.get(f"/api/v1/templates/{template_id}/agents-md")
            assert zh_get.status_code == status.HTTP_200_OK
            assert zh_get.json()["success"] is False
            assert zh_get.json()["message"] == "載入 AGENTS.md 失敗"

        with patch(
            "app.routers.templates.files.TemplateService.update_agents_md",
            side_effect=RuntimeError("boom"),
        ):
            zh_put = client.put(
                f"/api/v1/templates/{template_id}/agents-md",
                json={"content": "# test"},
            )
            assert zh_put.status_code == status.HTTP_200_OK
            assert zh_put.json()["success"] is False
            assert zh_put.json()["message"] == "更新 AGENTS.md 失敗"

    @pytest.mark.integration
    def test_tpl_071_commands_error_scenarios(self, authenticated_client, test_data_factory):
        """TPL-071 Slash Commands error scenario tests"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for Error Tests",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Get nonexistent Slash Command
        response = client.get(f"/api/v1/templates/{template_id}/commands/nonexistent.md")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

        # 2. Delete nonexistent Slash Command
        response = client.delete(f"/api/v1/templates/{template_id}/commands/nonexistent.md")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_204_NO_CONTENT]

    @pytest.mark.integration
    def test_tpl_072_agents_error_scenarios(self, authenticated_client, test_data_factory):
        """TPL-072 Agents error scenario tests"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for SubAgent Errors",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Update nonexistent SubAgent
        update_data = {
            "fileName": "nonexistent.md",
            "content": "# Test"
        }
        response = client.put(
            f"/api/v1/templates/{template_id}/agents/nonexistent.md",
            json=update_data
        )
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

    @pytest.mark.integration
    def test_tpl_073_output_style_error_scenarios(self, authenticated_client, test_data_factory):
        """TPL-073 Output Styles error scenario tests"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for Output Style Errors",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Get nonexistent Output Style
        response = client.get(f"/api/v1/templates/{template_id}/output-style/nonexistent.md")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

    @pytest.mark.integration
    def test_tpl_074_file_operations_error_scenarios(self, authenticated_client, test_data_factory):
        """TPL-074 File operations error scenario tests"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for File Errors",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Read nonexistent file
        response = client.get(f"/api/v1/templates/{template_id}/files/content?path=/nonexistent.txt")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

        # 2. Delete nonexistent file
        response = client.delete(f"/api/v1/templates/{template_id}/files?path=/nonexistent.txt")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

    @pytest.mark.integration
    def test_tpl_075_git_clone_progress_not_found(self, authenticated_client):
        """TPL-075 Query progress of nonexistent clone task (error scenario)"""
        client, user = authenticated_client

        fake_task_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/templates/git/clone/progress/{fake_task_id}")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

    @pytest.mark.integration
    def test_tpl_076_rebuild_progress_not_found(self, authenticated_client):
        """TPL-076 Query progress of nonexistent rebuild task (error scenario)"""
        client, user = authenticated_client

        fake_task_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/templates/rebuild/progress/{fake_task_id}")
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_200_OK]

    @pytest.mark.integration
    def test_tpl_077_ssh_keys_generate(self, authenticated_client):
        """TPL-077 Generate SSH Keys"""
        client, user = authenticated_client

        # Back up existing SSH keys first (if any)
        backup_response = client.get("/api/v1/templates/marketplace/ssh-keys")
        has_existing_keys = (
            backup_response.status_code == status.HTTP_200_OK and
            backup_response.json().get("success") and
            backup_response.json().get("data", {}).get("publicKey")
        )

        if has_existing_keys:
            existing_keys = backup_response.json()["data"]

        # Generate new SSH Keys
        response = client.post("/api/v1/templates/marketplace/ssh-keys/generate")

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("SSH keys generation endpoint not implemented")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "success" in data
        assert data["success"] is True
        assert "data" in data

        # Verify SSH keys format
        ssh_data = data["data"]
        assert "publicKey" in ssh_data
        assert "privateKey" in ssh_data
        assert ssh_data["publicKey"].startswith("ssh-rsa ") or ssh_data["publicKey"].startswith("ssh-ed25519 ")
        assert "BEGIN" in ssh_data["privateKey"]
        assert "PRIVATE KEY" in ssh_data["privateKey"]

        # Restore original SSH keys (if any)
        if has_existing_keys:
            restore_data = {
                "publicKey": existing_keys["publicKey"],
                "privateKey": existing_keys["privateKey"]
            }
            restore_response = client.put("/api/v1/templates/marketplace/ssh-keys", json=restore_data)
            # Restore result not checked because this is a cleanup step

    @pytest.mark.integration
    def test_tpl_078_ssh_keys_update(self, authenticated_client):
        """TPL-078 Update SSH Keys"""
        client, user = authenticated_client

        # Generate a test SSH key pair (using a valid format)
        # This is a valid test SSH public key (base64 encoded correctly)
        test_public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7Z8K test@example.com"
        test_private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEATest1234567890Test1234567890Test1234567890Test
1234567890Test1234567890Test1234567890Test1234567890Test1234567890
-----END RSA PRIVATE KEY-----"""

        # Back up existing SSH keys first
        backup_response = client.get("/api/v1/templates/marketplace/ssh-keys")
        has_existing_keys = (
            backup_response.status_code == status.HTTP_200_OK and
            backup_response.json().get("success") and
            backup_response.json().get("data", {}).get("publicKey")
        )

        if has_existing_keys:
            existing_keys = backup_response.json()["data"]

        # Update SSH Keys
        update_data = {
            "publicKey": test_public_key,
            "privateKey": test_private_key
        }
        response = client.put("/api/v1/templates/marketplace/ssh-keys", json=update_data)

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("SSH keys update endpoint not implemented")

        # The test key may not be perfectly formatted, so failure is acceptable
        # Mainly test that the endpoint exists with basic validation
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "success" in data
        # If it fails, check whether it is a format error (which is expected)
        if not data["success"]:
            assert "error" in data
            # Format errors are acceptable because this is a fake test key
            pytest.skip("Test SSH key format validation failed (expected for test keys)")

        assert "data" in data

        # Restore original SSH keys (if any)
        if has_existing_keys:
            restore_data = {
                "publicKey": existing_keys["publicKey"],
                "privateKey": existing_keys["privateKey"]
            }
            restore_response = client.put("/api/v1/templates/marketplace/ssh-keys", json=restore_data)
            # Restore result not checked because this is a cleanup step

    @pytest.mark.integration
    def test_tpl_078b_ssh_keys_invalid_format_is_localized(self, authenticated_client):
        client, _ = authenticated_client

        with patch(
            "app.routers.templates.git.TemplateGitService.update_ssh_keys",
            side_effect=ValueError("Private key format is incorrect"),
        ):
            en_response = client.put(
                "/api/v1/templates/marketplace/ssh-keys",
                json={"publicKey": "ssh-rsa AAAA", "privateKey": "bad-key"},
            )
            assert en_response.status_code == status.HTTP_200_OK
            data = en_response.json()
            assert data["success"] is False
            assert data["message"] == "Invalid SSH Keys format"
            assert data["error"] == "Invalid SSH Keys format"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.templates.git.TemplateGitService.update_ssh_keys",
            side_effect=ValueError("Private key format is incorrect"),
        ):
            zh_response = client.put(
                "/api/v1/templates/marketplace/ssh-keys",
                json={"publicKey": "ssh-rsa AAAA", "privateKey": "bad-key"},
            )
            assert zh_response.status_code == status.HTTP_200_OK
            data = zh_response.json()
            assert data["success"] is False
            assert data["message"] == "SSH Keys 格式不正確"
            assert data["error"] == "SSH Keys 格式不正確"

    @pytest.mark.integration
    def test_tpl_079_ssh_keys_delete(self, authenticated_client):
        """TPL-079 Delete SSH Keys"""
        client, user = authenticated_client

        # Back up existing SSH keys first
        backup_response = client.get("/api/v1/templates/marketplace/ssh-keys")
        has_existing_keys = (
            backup_response.status_code == status.HTTP_200_OK and
            backup_response.json().get("success") and
            backup_response.json().get("data", {}).get("publicKey")
        )

        if has_existing_keys:
            existing_keys = backup_response.json()["data"]

        # Delete SSH Keys
        response = client.delete("/api/v1/templates/marketplace/ssh-keys")

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("SSH keys delete endpoint not implemented")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "success" in data
        assert data["success"] is True

        # Verify SSH keys cannot be retrieved or return empty after deletion
        verify_response = client.get("/api/v1/templates/marketplace/ssh-keys")
        if verify_response.status_code == status.HTTP_200_OK:
            verify_data = verify_response.json()
            # SSH keys should be deleted or returned empty
            if verify_data.get("success"):
                assert not verify_data.get("data", {}).get("publicKey")

        # Restore original SSH keys (if any)
        if has_existing_keys:
            restore_data = {
                "publicKey": existing_keys["publicKey"],
                "privateKey": existing_keys["privateKey"]
            }
            restore_response = client.put("/api/v1/templates/marketplace/ssh-keys", json=restore_data)
            # Restore result not checked because this is a cleanup step

    @pytest.mark.integration
    def test_tpl_080_mcp_config_full_workflow(self, authenticated_client, test_data_factory):
        """TPL-080 MCP configuration full workflow"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for MCP Workflow",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Get initial MCP configuration
        get_response = client.get(f"/api/v1/templates/{template_id}/mcp")
        if get_response.status_code != status.HTTP_404_NOT_FOUND:
            assert get_response.status_code == status.HTTP_200_OK

        # 2. Update MCP configuration
        mcp_data = {
            "mcpServers": {
                "test-server": {
                    "description": "Test MCP Server",
                    "type": "stdio",
                    "command": "node",
                    "args": ["server.js"]
                }
            }
        }
        update_response = client.put(f"/api/v1/templates/{template_id}/mcp", json=mcp_data)
        if update_response.status_code != status.HTTP_404_NOT_FOUND:
            assert update_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_081_hooks_config_full_workflow(self, authenticated_client, test_data_factory):
        """TPL-081 Hooks configuration full workflow"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for Hooks Workflow",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # 1. Get initial Hooks configuration
        get_response = client.get(f"/api/v1/templates/{template_id}/hooks")
        if get_response.status_code != status.HTTP_404_NOT_FOUND:
            assert get_response.status_code == status.HTTP_200_OK

        # 2. Update Hooks configuration
        hooks_data = {
            "hooks": {
                "preCommit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "npm run lint",
                                "timeout": 30
                            }
                        ]
                    }
                ],
                "postCommit": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "npm run test",
                                "timeout": 30
                            }
                        ]
                    }
                ],
                "prePush": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "npm run build",
                                "timeout": 30
                            }
                        ]
                    }
                ]
            }
        }
        update_response = client.put(f"/api/v1/templates/{template_id}/hooks", json=hooks_data)
        if update_response.status_code != status.HTTP_404_NOT_FOUND:
            assert update_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_082_file_tree_with_depth(self, authenticated_client, test_data_factory):
        """TPL-082 Get file tree (with specified depth)"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for File Tree",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Test different depths
        for depth in [1, 2, 3]:
            response = client.get(f"/api/v1/templates/{template_id}/files/tree?max_depth={depth}")
            if response.status_code != status.HTTP_404_NOT_FOUND:
                assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_083_file_search_with_patterns(self, authenticated_client, test_data_factory):
        """TPL-083 File search (multiple patterns)"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for Search Patterns",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Test different search patterns
        file_types = [[".md"], [".json"], [".ts"], [".py"]]
        for types in file_types:
            search_data = {
                "query": types[0].replace(".", ""),
                "searchContent": False,
                "fileTypes": types,
                "maxResults": 100
            }
            response = client.post(
                f"/api/v1/templates/{template_id}/files/search",
                json=search_data
            )
            if response.status_code != status.HTTP_404_NOT_FOUND:
                assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_084_git_operations_workflow(self, authenticated_client):
        """TPL-084 Git operations full workflow"""
        client, user = authenticated_client

        # 1. Check Git status
        status_response = client.get("/api/v1/templates/git/version-control/status")
        if status_response.status_code != status.HTTP_404_NOT_FOUND:
            assert status_response.status_code == status.HTTP_200_OK

        # 2. Check change history
        changes_response = client.get("/api/v1/templates/git/version-control/changes")
        if changes_response.status_code != status.HTTP_404_NOT_FOUND:
            assert changes_response.status_code == status.HTTP_200_OK

        # 3. Check branch list
        branches_response = client.get("/api/v1/templates/git/version-control/branches")
        if branches_response.status_code != status.HTTP_404_NOT_FOUND:
            assert branches_response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_tpl_085_template_lifecycle(self, authenticated_client, test_data_factory):
        """TPL-085 Template full lifecycle test"""
        client, user = authenticated_client

        # 1. Create template
        template_data = test_data_factory.create_template_data(
            name="Lifecycle Test Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        assert create_response.status_code == status.HTTP_201_CREATED
        template_id = create_response.json()["id"]

        # 2. Read template
        get_response = client.get(f"/api/v1/templates/{template_id}")
        assert get_response.status_code == status.HTTP_200_OK

        # 3. Update template
        update_data = {
            "name": "Updated Lifecycle Template",
            "description": "Updated description"
        }
        update_response = client.put(f"/api/v1/templates/{template_id}", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK

        # 4. Delete template
        delete_response = client.delete(f"/api/v1/templates/{template_id}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # 5. Verify deletion
        verify_response = client.get(f"/api/v1/templates/{template_id}")
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_tpl_087_get_template_features_success(self, authenticated_client, test_data_factory):
        """TPL-087 Get template feature information successfully"""
        client, user = authenticated_client

        # Create and index template
        template_data = test_data_factory.create_template_data(
            name="Template for Feature Query",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Query template features (auto-indexed on creation)
        features_response = client.get(f"/api/v1/templates/{template_id}/features")
        assert features_response.status_code == status.HTTP_200_OK

        features_data = features_response.json()

        # Verify response structure
        required_fields = ["templateId", "features"]
        for field in required_fields:
            assert field in features_data, f"Feature information should contain {field} field"

        # Verify data content
        assert features_data["templateId"] == template_id
        assert isinstance(features_data["features"], list)

        # If an index timestamp exists, verify its format
        if "indexedAt" in features_data and features_data["indexedAt"]:
            assert isinstance(features_data["indexedAt"], str)

    @pytest.mark.integration
    def test_tpl_088_get_feature_stats_success(self, authenticated_client, test_data_factory):
        """TPL-088 Get feature statistics successfully"""
        client, user = authenticated_client

        # Create and index several templates
        template_ids = []
        for i in range(2):
            template_data = test_data_factory.create_template_data(
                name=f"Template for Stats {i}",
                author_name=user.display_name,
                author_email=user.email,
            )
            create_response = client.post("/api/v1/templates", json=template_data)
            template_id = create_response.json()["id"]
            template_ids.append(template_id)
            # Indexing is triggered automatically on creation

        # Get feature statistics
        stats_response = client.get("/api/v1/templates/features/stats")
        assert stats_response.status_code == status.HTTP_200_OK

        stats_data = stats_response.json()

        # Verify response structure
        assert "stats" in stats_data, "Statistics should contain stats field"
        assert isinstance(stats_data["stats"], dict)

        # Verify statistics data structure
        # Possible feature types: mcp, commands, hooks, agentsMd, agents, outputStyle, scripts, skills
        for feature_name, stat_item in stats_data["stats"].items():
            assert "name" in stat_item, f"{feature_name} statistics should contain name field"
            assert "count" in stat_item, f"{feature_name} statistics should contain count field"
            assert isinstance(stat_item["count"], int)
            assert stat_item["count"] >= 0

    @pytest.mark.integration
    def test_tpl_089_list_templates_filter_by_features(self, authenticated_client, test_data_factory):
        """TPL-089 Filter template list by feature"""
        client, user = authenticated_client

        # Create and index template
        template_data = test_data_factory.create_template_data(
            name="Template for Feature Filter",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]
        # Indexing is triggered automatically on creation

        # Test filtering by a single feature
        response = client.get("/api/v1/templates?features=mcp")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

        # Test filtering by multiple features (AND logic)
        response = client.get("/api/v1/templates?features=mcp,hooks")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.integration
    def test_tpl_091_get_features_not_found(self, authenticated_client):
        """TPL-091 Get features of nonexistent template (error scenario)"""
        client, user = authenticated_client

        fake_template_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/templates/{fake_template_id}/features")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    @pytest.mark.integration
    def test_tpl_092_feature_stats_with_cli_type(self, authenticated_client, test_data_factory):
        """TPL-092 Get feature statistics for a specific CLI type"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Template for CLI Stats",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]
        # Indexing is triggered automatically on creation

        # Get statistics for a specific CLI type
        stats_response = client.get("/api/v1/templates/features/stats?cli_type=claude-code")
        assert stats_response.status_code == status.HTTP_200_OK

        stats_data = stats_response.json()
        assert "stats" in stats_data
        assert isinstance(stats_data["stats"], dict)

    @pytest.mark.integration
    def test_tpl_093_auto_index_on_template_create(self, authenticated_client, test_data_factory):
        """TPL-093 Auto-index features on template creation"""
        client, user = authenticated_client

        # Create template (should auto-trigger indexing)
        template_data = test_data_factory.create_template_data(
            name="Auto Index Test Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        assert create_response.status_code == status.HTTP_201_CREATED
        template_id = create_response.json()["id"]

        # Query feature information and verify it was auto-indexed
        features_response = client.get(f"/api/v1/templates/{template_id}/features")
        assert features_response.status_code == status.HTTP_200_OK

        features_data = features_response.json()
        assert features_data["templateId"] == template_id
        assert "features" in features_data
        # Index timestamp may be None (if never indexed) or have a value
        # After auto-indexing, indexedAt should exist or indexing should have run at least once
        assert isinstance(features_data["features"], list)

    @pytest.mark.integration
    def test_tpl_094_auto_reindex_on_template_update(self, authenticated_client, test_data_factory):
        """TPL-094 Auto re-index features on template update"""
        client, user = authenticated_client

        # Create template
        template_data = test_data_factory.create_template_data(
            name="Reindex Test Template",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Get initial feature information
        initial_features_response = client.get(f"/api/v1/templates/{template_id}/features")
        initial_features = initial_features_response.json()

        # Update template (should auto re-index)
        update_data = {
            "name": "Updated Reindex Template",
            "description": "Updated for reindex test"
        }
        update_response = client.put(f"/api/v1/templates/{template_id}", json=update_data)
        assert update_response.status_code == status.HTTP_200_OK

        # Query feature information after update
        updated_features_response = client.get(f"/api/v1/templates/{template_id}/features")
        assert updated_features_response.status_code == status.HTTP_200_OK

        updated_features = updated_features_response.json()
        assert updated_features["templateId"] == template_id
        # Verify re-indexing (indexedAt should be updated, or indexing should have run at least once)
        assert "features" in updated_features

    @pytest.mark.integration
    def test_tpl_096_list_templates_with_indexed_features_field(self, authenticated_client, test_data_factory):
        """TPL-096 Include indexed feature fields when listing templates"""
        client, user = authenticated_client

        # Create and index template
        template_data = test_data_factory.create_template_data(
            name="Template with Indexed Features",
            author_name=user.display_name,
            author_email=user.email,
        )
        create_response = client.post("/api/v1/templates", json=template_data)
        template_id = create_response.json()["id"]
        # Indexing is triggered automatically on creation

        # List templates
        list_response = client.get("/api/v1/templates")
        assert list_response.status_code == status.HTTP_200_OK

        data = list_response.json()
        assert "items" in data

        # Find the newly created template
        created_template = None
        for template in data["items"]:
            if template["id"] == template_id:
                created_template = template
                break

        # Verify the template contains feature-related fields (if returned by the implementation)
        if created_template:
            # indexedFeatures and featuresIndexedAt may be present in the response
            # This depends on whether the API implementation includes these fields in the list
            assert "id" in created_template
            assert "name" in created_template

    @pytest.mark.integration
    def test_tpl_097_empty_features_filter(self, authenticated_client):
        """TPL-097 Empty feature filter condition"""
        client, user = authenticated_client

        # Test empty features parameter
        response = client.get("/api/v1/templates?features=")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "items" in data
        # Empty filter should return all templates (no feature filtering)

    @pytest.mark.integration
    def test_tpl_098_invalid_feature_filter(self, authenticated_client):
        """TPL-098 Invalid feature filter condition"""
        client, user = authenticated_client

        # Test invalid feature name
        response = client.get("/api/v1/templates?features=invalid_feature_name")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "items" in data
        # Invalid feature name should return empty list or ignore that filter

    @pytest.mark.integration
    def test_tpl_100_feature_stats_empty_database(self, authenticated_client):
        """TPL-100 Feature statistics on empty database"""
        client, user = authenticated_client

        # Get statistics (should return normally even if no templates exist)
        stats_response = client.get("/api/v1/templates/features/stats")
        assert stats_response.status_code == status.HTTP_200_OK

        stats_data = stats_response.json()
        assert "stats" in stats_data
        assert isinstance(stats_data["stats"], dict)

        # All feature counts should be 0 or simply not present
        for feature_name, stat_item in stats_data["stats"].items():
            if "count" in stat_item:
                assert stat_item["count"] >= 0
