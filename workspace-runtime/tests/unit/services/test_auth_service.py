from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

from app.services import auth_service as auth_module


def test_simple_user_defaults() -> None:
    user = auth_module.SimpleUser("user-1", email="u@example.com")

    assert user.id == "user-1"
    assert user.user_id == "user-1"
    assert user.username == "user-1"
    assert user.roles == []


def test_auth_service_init_enables_keycloak(monkeypatch) -> None:
    fake_auth_module = ModuleType("app.modules.auth")
    fake_auth_module.get_keycloak_config = lambda: SimpleNamespace(enabled=True)
    fake_auth_module.get_jwt_utils = lambda: "jwt-utils"
    monkeypatch.setitem(sys.modules, "app.modules.auth", fake_auth_module)

    service = auth_module.AuthService()

    assert service._keycloak_enabled is True
    assert service._jwt_utils == "jwt-utils"


def test_auth_service_init_handles_setup_errors(monkeypatch) -> None:
    fake_auth_module = ModuleType("app.modules.auth")
    fake_auth_module.get_keycloak_config = lambda: (_ for _ in ()).throw(RuntimeError("broken config"))
    fake_auth_module.get_jwt_utils = lambda: "unused"
    monkeypatch.setitem(sys.modules, "app.modules.auth", fake_auth_module)

    service = auth_module.AuthService()

    assert service._keycloak_enabled is False
    assert service._jwt_utils is None


async def test_validate_access_token_returns_none_when_disabled() -> None:
    service = auth_module.AuthService()
    service._keycloak_enabled = False
    service._jwt_utils = None

    assert await service.validate_access_token("a.b.c") is None


async def test_validate_access_token_rejects_invalid_jwt_format() -> None:
    service = auth_module.AuthService()
    service._keycloak_enabled = True
    service._jwt_utils = AsyncMock()

    assert await service.validate_access_token("not-a-jwt") is None
    service._jwt_utils.decode_token_async.assert_not_called()


async def test_validate_access_token_returns_user_from_payload() -> None:
    service = auth_module.AuthService()
    service._keycloak_enabled = True
    service._jwt_utils = AsyncMock()
    service._jwt_utils.decode_token_async.return_value = {
        "sub": "user-123",
        "email": "u@example.com",
        "preferred_username": "tester",
        "realm_access": {"roles": ["admin", "writer"]},
    }

    user = await service.validate_access_token("aaa.bbb.ccc")

    assert user is not None
    assert user.id == "user-123"
    assert user.email == "u@example.com"
    assert user.username == "tester"
    assert user.roles == ["admin", "writer"]
    service._jwt_utils.decode_token_async.assert_awaited_once_with("aaa.bbb.ccc", verify_audience=False)


async def test_validate_access_token_handles_missing_sub_and_decode_error() -> None:
    service = auth_module.AuthService()
    service._keycloak_enabled = True
    service._jwt_utils = AsyncMock()
    service._jwt_utils.decode_token_async.return_value = {"email": "u@example.com"}

    assert await service.validate_access_token("aaa.bbb.ccc") is None

    service._jwt_utils.decode_token_async.side_effect = RuntimeError("decode failed")
    assert await service.validate_access_token("aaa.bbb.ccc") is None


def test_get_auth_service_returns_singleton() -> None:
    auth_module._auth_service = None

    service1 = auth_module.get_auth_service()
    service2 = auth_module.get_auth_service()

    assert service1 is service2
