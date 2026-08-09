from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.config.settings import Settings, get_settings
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.knowledge_base.attachments import (
    KnowledgeBaseAttachmentService,
)
from app.modules.knowledge_base.files import KnowledgeBaseFileService
from app.modules.knowledge_base.access import KnowledgeBaseService
from app.modules.workspace.runtime.provisioning import RuntimeProvisionService
from app.modules.workspace.runtime.database import (
    WorkspaceRuntimeDatabaseService,
)


def _create_owner_and_workspace(session_factory) -> tuple[str, str]:
    with session_factory() as session:
        owner = db_models.User(
            id="kb-runtime-owner",
            username="kb-runtime-owner",
            email="kb-runtime-owner@example.com",
            oidc_subject="kb-runtime-owner-oidc",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        workspace = db_models.Workspace(
            id=str(uuid4()),
            owner_id=owner.id,
            name="KB Runtime Workspace",
            runtime="universal",
            provisioner="docker",
            runtime_status="stopped",
            runtime_internal_port=3002,
            canvas_internal_port=3003,
            browser_credential_key_id="test-browser-key",
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        session.add_all([owner, workspace])
        session.commit()
        return owner.id, workspace.id


@pytest.fixture
def kb_runtime_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "runtime-kb-flow"
    paths = {
        "RUNTIME_SCRIPT_ROOT": root / "runtime-scripts",
        "HOST_WORKSPACES_DIR": root / "host-workspaces",
        "HOST_WORKSPACE_SCRIPTS_DIR": root / "host-workspace-scripts",
        "HOST_RUNTIME_HOME_DIR": root / "host-runtime-home",
        "HOST_KNOWLEDGE_BASES_DIR": root / "knowledge-bases",
        "MANAGER_WORKSPACES_DIR": root / "manager-workspaces",
        "MANAGER_WORKSPACE_SCRIPTS_DIR": root / "manager-workspace-scripts",
        "MANAGER_RUNTIME_HOME_DIR": root / "manager-runtime-home",
        "MANAGER_KNOWLEDGE_BASES_DIR": root / "knowledge-bases",
        "RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": root / "runtime-jwks.json",
    }
    for key, path in paths.items():
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("NODE_ENV", "test")
    get_settings.cache_clear()
    yield paths
    get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.usefixtures("kb_runtime_paths")
def test_execution_plan_uses_latest_read_only_candidate_snapshot(
    test_app,
    monkeypatch: pytest.MonkeyPatch,
):
    _, session_factory = test_app
    owner_id, workspace_id = _create_owner_and_workspace(session_factory)
    owner_actor = AuthorizationActor(
        user_id=owner_id,
        platform_role="member",
    )
    fake_image_service = type(
        "FakeImageService",
        (),
        {
            "get_docker_image_name": lambda _self, _runtime: "workspace-runtime:test",
            "get_browser_image_name": lambda _self: "workspace-browser:test",
            "get_canvas_image_name": lambda _self: "workspace-canvas:test",
        },
    )()
    monkeypatch.setattr(
        "app.modules.container_images.catalog.get_container_image_service",
        lambda: fake_image_service,
    )
    runtime_database_service = WorkspaceRuntimeDatabaseService(
        settings=Settings(
            DATABASE_URL=(
                "postgresql://test_user:test_password@postgres-test:5432/"
                "test_workspace_manager"
            ),
            RUNTIME_DATABASE_CREDENTIAL_KEY_FILE="/unused",
        ),
        credential_key=b"test-runtime-database-credential-key",
    )

    with session_factory() as session:
        kb = KnowledgeBaseService(session).create_kb(
            actor=owner_actor,
            name="Runtime Docs",
            slug="runtime-docs",
        )
        KnowledgeBaseFileService(session).create_entry(
            actor=owner_actor,
            kb_id=kb.id,
            path="/raw/readme.md",
            entry_type="file",
            content="hello kb",
        )
        mutation = KnowledgeBaseAttachmentService(session).attach(
            actor=owner_actor,
            workspace_id=workspace_id,
            kb_id=kb.id,
            mount_alias="runtime-docs",
        )
        attachment_id = mutation.attachment.id

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        plan = RuntimeProvisionService(
            session,
            runtime_database_service=runtime_database_service,
        ).prepare_execution_plane(
            workspace,
            runtime_instance_id="f1e4b143-628e-46e2-8ab0-df8687eb163c",
        )
        mount = next(
            volume
            for volume in plan.runtime_context.volumes
            if volume.target == "/knowledge/runtime-docs"
        )
        assert mount.read_only is True
        assert (Path(mount.source) / "raw/readme.md").read_text(
            encoding="utf-8"
        ) == "hello kb"

        KnowledgeBaseAttachmentService(session).update_attachment(
            actor=owner_actor,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            mount_alias="runtime-docs-v2",
        )

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        plan = RuntimeProvisionService(
            session,
            runtime_database_service=runtime_database_service,
        ).prepare_execution_plane(
            workspace,
            runtime_instance_id="998d9f26-279d-4b6f-9ae4-31c146025bba",
        )
        knowledge_targets = {
            volume.target
            for volume in plan.runtime_context.volumes
            if volume.target.startswith("/knowledge/")
        }
        assert knowledge_targets == {"/knowledge/runtime-docs-v2"}

        KnowledgeBaseAttachmentService(session).detach(
            actor=owner_actor,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
        )

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        plan = RuntimeProvisionService(
            session,
            runtime_database_service=runtime_database_service,
        ).prepare_execution_plane(
            workspace,
            runtime_instance_id="a1a55307-256d-480c-b1d8-b92398cb5035",
        )
        assert not any(
            volume.target.startswith("/knowledge/")
            for volume in plan.runtime_context.volumes
        )
        assert (
            session.get(
                db_models.WorkspaceKnowledgeBaseAttachment,
                attachment_id,
            )
            is None
        )
