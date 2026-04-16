"""seed 模組單元測試"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db import models as db_models
from app.db.seed import create_default_workspace, ensure_bootstrap_default_workspace


@pytest.mark.unit
def test_create_default_workspace_creates_record_in_docker_mode(
    test_app,
    create_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-user-default", email="admin@aileron.com", username="admin")
    monkeypatch.setattr(
        "app.db.seed.get_settings",
        lambda: SimpleNamespace(
            RUNTIME_PROVISIONER="docker",
            BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED=False,
            BOOTSTRAP_DEFAULT_WORKSPACE_ID="default-workspace",
            BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL="admin@aileron.com",
            BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL="",
            BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH="main",
            BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE=None,
            RUNTIME_K8S_NAMESPACE="workspace-system",
        ),
    )
    monkeypatch.setattr("app.db.seed.SessionLocal", session_factory)

    with session_factory() as session:
        create_default_workspace(session)
        session.commit()

        workspace = session.get(db_models.Workspace, "default-workspace")
        assert workspace is not None
        assert workspace.provisioner == "docker"
        assert workspace.runtime_external_url == "http://localhost:3002"
        assert workspace.runtime_internal_url == "http://workspace-runtime-default-workspace:3002"
        assert workspace.nextjs_container_id == "workspace-nextjs-default-workspace"
        assert workspace.nextjs_internal_url == "http://workspace-nextjs-default-workspace:3003"
        assert workspace.web_preview_internal_url == workspace.nextjs_internal_url


@pytest.mark.unit
def test_create_default_workspace_skips_record_in_kubernetes_mode(
    test_app,
    create_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-user-default", email="admin@aileron.com", username="admin")
    monkeypatch.setattr(
        "app.db.seed.get_settings",
        lambda: SimpleNamespace(
            RUNTIME_PROVISIONER="kubernetes",
            BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED=False,
            BOOTSTRAP_DEFAULT_WORKSPACE_ID="default-workspace",
            BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL="admin@aileron.com",
            BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL="",
            BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH="main",
            BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE=None,
            RUNTIME_K8S_NAMESPACE="workspace-system",
        ),
    )

    with session_factory() as session:
        create_default_workspace(session)
        session.commit()

        workspace = session.get(db_models.Workspace, "default-workspace")
        assert workspace is None


@pytest.mark.unit
def test_create_default_workspace_creates_kubernetes_record_when_enabled(
    test_app,
    create_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-user-default", email="admin@aileron.com", username="admin")
    monkeypatch.setattr(
        "app.db.seed.get_settings",
        lambda: SimpleNamespace(
            RUNTIME_PROVISIONER="kubernetes",
            BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED=True,
            BOOTSTRAP_DEFAULT_WORKSPACE_ID="default-workspace",
            BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL="admin@aileron.com",
            BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL="https://github.com/example/repo.git",
            BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH="main",
            BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE="workspace-system",
            RUNTIME_K8S_NAMESPACE="workspace-system",
        ),
    )

    with session_factory() as session:
        create_default_workspace(session)
        session.commit()

        workspace = session.get(db_models.Workspace, "default-workspace")
        assert workspace is not None
        assert workspace.provisioner == "kubernetes"
        assert workspace.runtime_status == "starting"
        assert workspace.target_namespace == "workspace-system"
        assert workspace.runtime_internal_url is None
        assert workspace.nextjs_internal_url is None


@pytest.mark.unit
def test_ensure_bootstrap_default_workspace_retries_until_owner_exists(
    test_app,
    create_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session_factory = test_app
    monkeypatch.setattr(
        "app.db.seed.get_settings",
        lambda: SimpleNamespace(
            RUNTIME_PROVISIONER="kubernetes",
            BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED=True,
            BOOTSTRAP_DEFAULT_WORKSPACE_ID="default-workspace",
            BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL="admin@aileron.com",
            BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL="",
            BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH="main",
            BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE="workspace-system",
            RUNTIME_K8S_NAMESPACE="workspace-system",
        ),
    )
    monkeypatch.setattr("app.db.seed.SessionLocal", session_factory)

    attempt = {"count": 0}

    def create_user_on_second_attempt(*args, **kwargs):
        attempt["count"] += 1
        if attempt["count"] == 1:
            return None
        create_user(
            id="admin-user-default",
            email="admin@aileron.com",
            username="admin",
        )
        return None

    monkeypatch.setattr("app.db.seed.time.sleep", create_user_on_second_attempt)

    created = ensure_bootstrap_default_workspace(
        max_attempts=3,
        retry_interval_seconds=0,
    )

    assert created is True
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, "default-workspace")
        assert workspace is not None
        assert workspace.provisioner == "kubernetes"
