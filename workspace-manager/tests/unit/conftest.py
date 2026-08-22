"""Unit test common settings and mock fixtures"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi import Request

# SetupTestEnvironment
os.environ.setdefault("ENV", "testing")
_UNIT_DATABASE_URL_FILE = Path("/tmp/aileron-unit-database-url")
_UNIT_DATABASE_URL_FILE.write_text("sqlite:///:memory:\n", encoding="utf-8")
os.environ.setdefault("DATABASE_URL_FILE", str(_UNIT_DATABASE_URL_FILE))

from app.db import models as db_models
from app.modules.identity.user_authorization_policy import canonical_role_issues

# ============================================================================
# DataFactory Fixtures
# ============================================================================


@pytest.fixture
def user_factory():
    """UserFactory"""
    _counter = 0

    def create_user(**kwargs) -> db_models.User:
        nonlocal _counter
        _counter += 1
        platform_role = kwargs.get("platform_role")
        role_status = kwargs.get("role_status", "missing")
        sync_status = kwargs.get("sync_status", "synced")
        is_active = kwargs.get("is_active", True)
        identity_enabled = kwargs.get("identity_enabled", True)
        defaults = {
            "id": kwargs.get("id", f"user-{_counter}"),
            "username": kwargs.get("username", f"testuser-{_counter}"),
            "email": kwargs.get("email", f"testuser-{_counter}@example.com"),
            "first_name": kwargs.get("first_name", "Test"),
            "last_name": kwargs.get("last_name", f"User{_counter}"),
            "display_name": kwargs.get("display_name", f"Test User {_counter}"),
            "avatar_url": kwargs.get("avatar_url"),
            "is_active": is_active,
            "oidc_issuer": kwargs.get("oidc_issuer", "https://oidc.test.example"),
            "oidc_subject": kwargs.get("oidc_subject", f"subject-{_counter}"),
            "identity_enabled": identity_enabled,
            "sync_status": sync_status,
            "platform_role": platform_role,
            "role_status": role_status,
            "role_issues": kwargs.get(
                "role_issues", canonical_role_issues(role_status)
            ),
            "created_at": kwargs.get("created_at", datetime.now()),
            "updated_at": kwargs.get("updated_at", datetime.now()),
        }

        user = db_models.User(**defaults)
        return user

    return create_user


# ============================================================================
# Common Test Helpers
# ============================================================================


@pytest.fixture
def request_factory():
    """Create Request mock with consistent state / headers structure"""

    def build_request(
        path: str, headers: dict[str, str] | None = None, method: str = "GET"
    ) -> Mock:
        request = Mock(spec=Request)
        request.url = Mock(path=path)
        request.method = method
        request.headers = headers or {}
        request.state = SimpleNamespace()
        return request

    return build_request


@pytest.fixture
def httpx_response_factory():
    """Create customizable httpx response mock"""

    def build_response(
        *,
        status_code: int = 200,
        json_data: Any | None = None,
        text: str = "",
        raise_error: Exception | None = None,
        headers: dict[str, str] | None = None,
    ) -> Mock:
        response = Mock()
        response.status_code = status_code
        response.text = text
        response.headers = headers or {"content-type": "application/json"}
        response.json = Mock(
            return_value=json_data if json_data is not None else {"success": True}
        )
        response.raise_for_status = Mock()
        if raise_error is not None:
            response.raise_for_status.side_effect = raise_error
        return response

    return build_response


# ============================================================================
# TestMarkConfiguration
# ============================================================================


def pytest_configure(config):
    """ConfigurationUnitTestMark"""
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "auth: marks tests as authentication tests")
    config.addinivalue_line("markers", "workspace: marks tests as workspace tests")
    config.addinivalue_line("markers", "automation: marks tests as automation tests")
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "high_priority: marks high priority tests")
