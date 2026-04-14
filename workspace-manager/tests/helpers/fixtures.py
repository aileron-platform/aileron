"""測試資料夾具"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from pydantic import BaseModel


class TestDataFactory:
    """測試資料工廠"""

    @staticmethod
    def create_user_data(
        email: str | None = None,
        password: str | None = None,
        username: str | None = None,
        display_name: str | None = None,
        full_name: str | None = None,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """創建用戶測試資料"""
        return {
            "email": email or f"test_{uuid.uuid4().hex[:8]}@example.com",
            "username": username or f"test_user_{uuid.uuid4().hex[:8]}",
            "display_name": display_name or "Test User",
            "full_name": full_name or display_name or "Test User",
            "password": password or "testpassword123",
            "is_active": is_active,
        }

    @staticmethod
    def create_team_data(
        name: str | None = None,
        description: str | None = None,
        owner_id: uuid.UUID | None = None,
    ) -> Dict[str, Any]:
        """創建團隊測試資料"""
        return {
            "id": str(uuid.uuid4()),
            "name": name or f"Test Team {uuid.uuid4().hex[:8]}",
            "description": description or "A test team for testing purposes",
            "owner_id": str(owner_id) if owner_id else str(uuid.uuid4()),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_workspace_data(
        name: str | None = None,
        description: str | None = None,
        owner_id: uuid.UUID | None = None,
        template_id: uuid.UUID | None = None,
        git_url: str | None = None,
        branch: str | None = None,
        runtime: str = "docker",
        cli_type: str = "claude-code",
        provisioner: str = "docker",
        targetNamespace: str | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """創建工作區測試資料

        支援額外的 kwargs 來兼容舊的測試程式碼，如 team_id, config 等
        """
        return {
            "name": name or f"Test Workspace {uuid.uuid4().hex[:8]}",
            "description": description or "A test workspace for testing purposes",
            "ownerId": str(owner_id) if owner_id is not None else None,  # 使用 alias
            "templateId": str(template_id) if template_id else None,  # 使用 alias
            "gitUrl": git_url,  # 使用 alias
            "branch": branch or "main",
            "runtime": runtime,
            "provisioner": provisioner,
            "targetNamespace": targetNamespace,
            "cliType": cli_type,  # 使用 alias
            "setupScript": "#!/bin/bash\necho 'Setting up workspace...'",  # 使用 alias
            "envVars": [],  # 使用 alias
            "portMappings": [],  # 使用 alias
            "preferredCli": "claude-code",  # 使用 alias
            "fallbackEnabled": True,  # 使用 alias
            "workspacePath": "/workspace",  # 使用 alias
        }

    @staticmethod
    def create_template_data(
        name: str | None = None,
        description: str | None = None,
        author_name: str | None = None,
        author_email: str | None = None,
        keywords: list[str] | None = None,
        version: str = "1.0.0",
        cli_type: str = "claude-code",
        status: str = "draft",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """創建範本測試資料

        支援額外的 kwargs 來兼容舊的測試程式碼，如 is_public, category, owner_id 等
        """
        template_id = f"test-template-{uuid.uuid4().hex[:8]}"
        return {
            "templateId": template_id,  # 使用 alias
            "name": name or f"Test Template {uuid.uuid4().hex[:8]}",
            "description": description or "A test template for testing purposes",
            "author": {
                "name": author_name or "Test Author",
                "email": author_email or f"author_{uuid.uuid4().hex[:8]}@example.com",
                "url": None,
            },
            "keywords": keywords or ["test", "template"],
            "version": version,
            "cli_type": cli_type,
            "status": status,
            "initCommands": "echo 'Initializing template...'",  # 使用 alias
        }

    @staticmethod
    def create_auth_token_data(
        user_id: uuid.UUID,
        expires_in: int = 3600,
        scopes: list[str] | None = None,
    ) -> Dict[str, Any]:
        """創建認證 Token 測試資料"""
        return {
            "access_token": f"test_token_{uuid.uuid4().hex}",
            "refresh_token": f"refresh_token_{uuid.uuid4().hex}",
            "token_type": "bearer",
            "expires_in": expires_in,
            "scope": " ".join(scopes or ["read", "write"]),
            "user_id": str(user_id),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.now(timezone.utc).timestamp() + expires_in,
        }


class MockResponses:
    """Mock API 回應"""

    @staticmethod
    def success_response(data: Any) -> Dict[str, Any]:
        """成功回應格式"""
        return {
            "success": True,
            "data": data,
            "message": "操作成功",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def error_response(
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        status_code: int = 400,
    ) -> Dict[str, Any]:
        """錯誤回應格式"""
        return {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": {},
            },
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def paginated_response(
        data: list[Any],
        page: int = 1,
        page_size: int = 10,
        total: int | None = None,
    ) -> Dict[str, Any]:
        """分頁回應格式"""
        if total is None:
            total = len(data)

        return {
            "success": True,
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": page * page_size < total,
                "has_prev": page > 1,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@pytest.fixture
def test_data_factory():
    """測試資料工廠 fixture"""
    return TestDataFactory()


@pytest.fixture
def mock_responses():
    """Mock 回應 fixture"""
    return MockResponses()


# 常用的測試資料
TEST_USER = {
    "id": str(uuid.uuid4()),
    "email": "test@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "is_active": True,
}

TEST_TEAM = {
    "id": str(uuid.uuid4()),
    "name": "Test Team",
    "description": "A test team",
    "owner_id": TEST_USER["id"],
    "is_active": True,
}

TEST_WORKSPACE = {
    "id": str(uuid.uuid4()),
    "name": "Test Workspace",
    "description": "A test workspace",
    "owner_id": TEST_USER["id"],
    "team_id": TEST_TEAM["id"],
    "status": "stopped",
}

TEST_TEMPLATE = {
    "id": str(uuid.uuid4()),
    "name": "Test Template",
    "description": "A test template",
    "is_public": True,
    "is_active": True,
    "created_by": TEST_USER["id"],
}
