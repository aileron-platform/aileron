"""Codex settings login route tests."""

from __future__ import annotations

from app.db import models as db_models
from app.main import app
from app.modules.settings.router import get_codex_login_service


class FakeCodexLoginService:
    """Fake manager-owned Codex login service."""

    def __init__(self) -> None:
        self.started_for: list[str] = []
        self.status_for: list[tuple[str, str | None]] = []
        self.cancel_for: list[tuple[str, str | None]] = []
        self.logout_for: list[str] = []

    async def start_login(self, user_id: str) -> dict[str, str]:
        self.started_for.append(user_id)
        return {
            "loginId": "login-1",
            "verificationUrl": "https://auth.openai.com/codex/device",
            "userCode": "ABCD-EFGH",
            "type": "chatgptDeviceCode",
        }

    async def get_status(self, user_id: str, login_id: str | None = None) -> dict:
        self.status_for.append((user_id, login_id))
        return {
            "loginStatus": "connected",
            "account": {"email": "codex@example.com", "planType": "pro"},
            "cliState": {
                "authJson": {
                    "auth_mode": "chatgpt",
                    "tokens": {"refresh_token": "refresh-token"},
                },
                "configToml": '[projects."/workspace"]\ntrust_level = "trusted"\n',
                "installationId": "installation-1",
            },
        }

    async def cancel_login(self, user_id: str, login_id: str | None) -> dict[str, str]:
        self.cancel_for.append((user_id, login_id))
        return {"status": "canceled"}

    async def logout(self, user_id: str) -> None:
        self.logout_for.append(user_id)


def test_codex_login_start_does_not_require_running_runtime(
    authenticated_client,
) -> None:
    """Codex login starts through manager when the user has no runtime."""
    client, user = authenticated_client
    fake_service = FakeCodexLoginService()
    app.dependency_overrides[get_codex_login_service] = lambda: fake_service

    response = client.post(
        f"/api/v1/users/{user.id}/settings/codex/login/start", json={}
    )

    assert response.status_code == 200
    data = response.json()["codex"]
    assert data["loginStatus"] == "pending"
    assert data["authFlow"]["loginId"] == "login-1"
    assert "cliState" not in data
    assert fake_service.started_for == [user.id]


def test_codex_login_start_ignores_broken_running_runtime(
    authenticated_client,
    test_app,
) -> None:
    """A broken runtime record does not affect manager-owned login start."""
    client, user = authenticated_client
    _, session_factory = test_app
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id="workspace-1",
                owner_id=user.id,
                name="Broken runtime",
                runtime_status="running",
                runtime_internal_url="http://broken-runtime:3002",
            )
        )
        session.commit()

    fake_service = FakeCodexLoginService()
    app.dependency_overrides[get_codex_login_service] = lambda: fake_service

    response = client.post(
        f"/api/v1/users/{user.id}/settings/codex/login/start", json={}
    )

    assert response.status_code == 200
    assert fake_service.started_for == [user.id]


def test_codex_login_status_persists_backend_cli_state_but_hides_public_response(
    authenticated_client,
    test_app,
    monkeypatch,
) -> None:
    """Connected status stores cliState in DB but omits it from frontend response."""
    client, user = authenticated_client
    _, session_factory = test_app
    fake_service = FakeCodexLoginService()
    app.dependency_overrides[get_codex_login_service] = lambda: fake_service

    async def fake_sync_settings_to_runtimes(user_id: str, changes: dict) -> None:
        return None

    monkeypatch.setattr(
        "app.modules.settings.router._sync_settings_to_runtimes",
        fake_sync_settings_to_runtimes,
    )
    client.post(f"/api/v1/users/{user.id}/settings/codex/login/start", json={})

    response = client.get(f"/api/v1/users/{user.id}/settings/codex/login/status")

    assert response.status_code == 200
    data = response.json()["codex"]
    assert data["loginStatus"] == "connected"
    assert data["account"]["email"] == "codex@example.com"
    assert "cliState" not in data
    assert fake_service.status_for == [(user.id, "login-1")]
    with session_factory() as session:
        settings = session.get(db_models.UserSetting, f"settings-{user.id}")
        assert settings is not None
        codex = settings.additional_settings["codex"]
        assert (
            codex["cliState"]["authJson"]["tokens"]["refresh_token"] == "refresh-token"
        )


def test_codex_logout_clears_manager_source_state(
    authenticated_client,
    test_app,
    monkeypatch,
) -> None:
    """Logout clears manager source auth state and does not depend on runtime logout."""
    client, user = authenticated_client
    _, session_factory = test_app
    with session_factory() as session:
        settings = session.get(db_models.UserSetting, f"settings-{user.id}")
        assert settings is not None
        additional = settings.additional_settings or {}
        additional["codex"] = {
            "loginStatus": "connected",
            "account": {"email": "codex@example.com"},
            "cliState": {"authJson": {"tokens": {"refresh_token": "refresh-token"}}},
            "authFlow": {"loginId": "login-1"},
        }
        settings.additional_settings = additional
        session.commit()

    fake_service = FakeCodexLoginService()
    app.dependency_overrides[get_codex_login_service] = lambda: fake_service
    synced_changes: list[dict] = []

    async def fake_sync_settings_to_runtimes(user_id: str, changes: dict) -> None:
        synced_changes.append(changes)

    monkeypatch.setattr(
        "app.modules.settings.router._sync_settings_to_runtimes",
        fake_sync_settings_to_runtimes,
    )

    response = client.post(f"/api/v1/users/{user.id}/settings/codex/logout", json={})

    assert response.status_code == 200
    data = response.json()["codex"]
    assert data["loginStatus"] == "notConnected"
    assert data["account"] is None
    assert "cliState" not in data
    assert fake_service.logout_for == [user.id]
    assert synced_changes == []
    with session_factory() as session:
        settings = session.get(db_models.UserSetting, f"settings-{user.id}")
        assert settings is not None
        codex = settings.additional_settings["codex"]
        assert codex["loginStatus"] == "notConnected"
        assert codex["cliState"] is None
