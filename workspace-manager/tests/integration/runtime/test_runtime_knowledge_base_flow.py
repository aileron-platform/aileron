from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.config.settings import get_settings
from app.db import models as db_models
from app.services.knowledge_base_attachment_service import KnowledgeBaseAttachmentService
from app.services.knowledge_base_file_service import KnowledgeBaseFileService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.orchestrator.models import RuntimeInfo, RuntimeStatusType
from app.services.runtime_provision_service import RuntimeProvisionService
from app.services.workspace_lifecycle_service import WorkspaceLifecycleService


def _create_owner_and_workspace(session_factory) -> tuple[str, str]:
    with session_factory() as session:
        owner = db_models.User(
            id="kb-runtime-owner",
            username="kb-runtime-owner",
            email="kb-runtime-owner@example.com",
            keycloak_id="kb-runtime-owner-keycloak",
        )
        workspace = db_models.Workspace(
            id="workspace-runtime-kb",
            owner_id=owner.id,
            name="KB Runtime Workspace",
            runtime="universal",
            provisioner="docker",
            runtime_status="stopped",
            runtime_internal_port=3002,
            runtime_external_port=31002,
            canvas_internal_port=3003,
            canvas_external_port=31003,
            terminal_external_port=31004,
            browser_webrtc_external_port=36080,
            browser_cdp_external_port=39223,
            canvas_external_port=33003,
            canvas_api_external_port=33013,
            env_vars=[],
            port_mappings=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        session.add(owner)
        session.add(workspace)
        session.commit()
        return owner.id, workspace.id


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.runtime_contexts = []

    def create_workspace_runtime(self, workspace, context):
        self.runtime_contexts.append(context)
        return RuntimeInfo(
            identifier=f"runtime-{workspace.id}",
            workspace_id=workspace.id,
            status=RuntimeStatusType.RUNNING,
            internal_url=f"http://workspace-runtime-{workspace.id}:3002",
            external_url=f"http://localhost:{workspace.runtime_external_port}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            platform="docker",
            extra_info={
                "container_name": f"workspace-runtime-{workspace.id}",
                "ports": {
                    "3002/tcp": workspace.runtime_external_port,
                    "3003/tcp": workspace.canvas_external_port,
                    "3004/tcp": workspace.terminal_external_port,
                },
            },
        )

    def create_chrome_runtime(self, workspace, context):
        return RuntimeInfo(
            identifier=f"browser-{workspace.id}",
            workspace_id=workspace.id,
            status=RuntimeStatusType.RUNNING,
            internal_url=f"http://workspace-browser-{workspace.id}:6080",
            external_url=f"http://localhost:{workspace.browser_webrtc_external_port}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            platform="docker",
        )

    def create_canvas_runtime(self, workspace, context):
        return RuntimeInfo(
            identifier=f"canvas-{workspace.id}",
            workspace_id=workspace.id,
            status=RuntimeStatusType.RUNNING,
            internal_url=f"http://workspace-canvas-{workspace.id}:3003",
            external_url=f"http://localhost:{workspace.canvas_external_port}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            platform="docker",
        )


@pytest.fixture
def kb_runtime_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "runtime-kb-flow"
    paths = {
        "RUNTIME_SCRIPT_ROOT": root / "runtime-scripts",
        "HOST_WORKSPACES_DIR": root / "host-workspaces",
        "HOST_WORKSPACE_SCRIPTS_DIR": root / "host-workspace-scripts",
        "HOST_CLAUDE_DATA_DIR": root / "host-claude-data",
        "HOST_KNOWLEDGE_BASES_DIR": root / "knowledge-bases",
        "MANAGER_WORKSPACES_DIR": root / "manager-workspaces",
        "MANAGER_WORKSPACE_SCRIPTS_DIR": root / "manager-workspace-scripts",
        "MANAGER_CLAUDE_DATA_DIR": root / "manager-claude-data",
        "MANAGER_KNOWLEDGE_BASES_DIR": root / "knowledge-bases",
    }
    for key, path in paths.items():
        monkeypatch.setenv(key, str(path))
    monkeypatch.setenv("NODE_ENV", "test")
    get_settings.cache_clear()
    yield paths
    get_settings.cache_clear()


@pytest.mark.integration
def test_runtime_provision_mounts_and_detaches_knowledge_base(
    test_app,
    kb_runtime_paths,
    monkeypatch: pytest.MonkeyPatch,
):
    _, session_factory = test_app
    owner_id, workspace_id = _create_owner_and_workspace(session_factory)

    with session_factory() as session:
        kb_service = KnowledgeBaseService(session)
        file_service = KnowledgeBaseFileService(session)
        attachment_service = KnowledgeBaseAttachmentService(session)

        kb = kb_service.create_kb(
            owner_id=owner_id,
            name="Runtime Docs",
            slug="runtime-docs",
        )
        file_service.create_entry(
            user_id=owner_id,
            kb_id=kb.id,
            path="/readme.md",
            entry_type="file",
            content="hello kb",
        )
        attachment = attachment_service.attach(
            user_id=owner_id,
            workspace_id=workspace_id,
            kb_id=kb.id,
            mode="rw",
        )
        session.commit()
        kb_id = kb.id
        attachment_id = attachment.id

    fake_orchestrator = _FakeOrchestrator()
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
        "app.services.runtime_provision_service.OrchestratorFactory.get_orchestrator",
        lambda: fake_orchestrator,
    )
    monkeypatch.setattr(
        "app.services.container_image_service.get_container_image_service",
        lambda: fake_image_service,
    )

    with session_factory() as session:
        service = RuntimeProvisionService(session)
        service.execute_runtime_provision(workspace_id)

    first_runtime_context = fake_orchestrator.runtime_contexts[-1]
    kb_mounts = {volume.target: volume for volume in first_runtime_context.volumes if volume.target.startswith("/knowledge/")}
    assert "/knowledge/runtime-docs" in kb_mounts
    assert kb_mounts["/knowledge/runtime-docs"].read_only is False
    assert (Path(kb_mounts["/knowledge/runtime-docs"].source) / "readme.md").read_text(encoding="utf-8") == "hello kb"

    with session_factory() as session:
        attachment_service = KnowledgeBaseAttachmentService(session)
        attachment_service.detach(user_id=owner_id, attachment_id=attachment_id)
        session.commit()

    with session_factory() as session:
        service = RuntimeProvisionService(session)
        service.execute_runtime_provision(workspace_id)

    second_runtime_context = fake_orchestrator.runtime_contexts[-1]
    second_kb_mounts = [volume for volume in second_runtime_context.volumes if volume.target.startswith("/knowledge/")]
    assert second_kb_mounts == []

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        assert workspace.runtime_mounted_kb_signature is not None
        attachment_count = session.query(db_models.WorkspaceKnowledgeBaseAttachment).filter_by(workspace_id=workspace_id).count()
        assert attachment_count == 0


@pytest.mark.integration
def test_runtime_provision_clears_tombstoned_knowledge_base_attachment_on_start(
    test_app,
    kb_runtime_paths,
    monkeypatch: pytest.MonkeyPatch,
):
    _, session_factory = test_app
    owner_id, workspace_id = _create_owner_and_workspace(session_factory)

    with session_factory() as session:
        kb_service = KnowledgeBaseService(session)
        attachment_service = KnowledgeBaseAttachmentService(session)

        kb = kb_service.create_kb(
            owner_id=owner_id,
            name="Tombstone Docs",
            slug="tombstone-docs",
        )
        attachment_service.attach(
            user_id=owner_id,
            workspace_id=workspace_id,
            kb_id=kb.id,
            mode="rw",
        )
        kb_service.delete_kb(user_id=owner_id, kb_id=kb.id, force=True)
        session.commit()

    fake_orchestrator = _FakeOrchestrator()
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
        "app.services.runtime_provision_service.OrchestratorFactory.get_orchestrator",
        lambda: fake_orchestrator,
    )
    monkeypatch.setattr(
        "app.services.container_image_service.get_container_image_service",
        lambda: fake_image_service,
    )

    with session_factory() as session:
        service = RuntimeProvisionService(session)
        service.execute_runtime_provision(workspace_id)

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        attachments = (
            session.query(db_models.WorkspaceKnowledgeBaseAttachment)
            .filter_by(workspace_id=workspace_id)
            .all()
        )
        assert attachments == []
        assert workspace.runtime_mounted_kb_signature is not None

    with session_factory() as session:
        service = RuntimeProvisionService(session)
        service.execute_runtime_provision(workspace_id)

    runtime_context = fake_orchestrator.runtime_contexts[-1]
    kb_mounts = [volume for volume in runtime_context.volumes if volume.target.startswith("/knowledge/")]
    assert kb_mounts == []


@pytest.mark.integration
def test_restart_workspace_rebuild_uses_latest_knowledge_base_attachments(
    test_app,
    kb_runtime_paths,
    monkeypatch: pytest.MonkeyPatch,
):
    _, session_factory = test_app
    owner_id, workspace_id = _create_owner_and_workspace(session_factory)

    with session_factory() as session:
        kb_service = KnowledgeBaseService(session)
        attachment_service = KnowledgeBaseAttachmentService(session)

        kb = kb_service.create_kb(
            owner_id=owner_id,
            name="Rebuild Docs",
            slug="rebuild-docs",
        )
        attachment = attachment_service.attach(
            user_id=owner_id,
            workspace_id=workspace_id,
            kb_id=kb.id,
            mode="rw",
        )
        session.commit()
        attachment_id = attachment.id

    fake_orchestrator = _FakeOrchestrator()
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
        "app.services.runtime_provision_service.OrchestratorFactory.get_orchestrator",
        lambda: fake_orchestrator,
    )
    monkeypatch.setattr(
        "app.services.container_image_service.get_container_image_service",
        lambda: fake_image_service,
    )

    with session_factory() as session:
        RuntimeProvisionService(session).execute_runtime_provision(workspace_id)
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        workspace.runtime_container_id = "runtime-container-123"
        session.commit()

    with session_factory() as session:
        attachment_service = KnowledgeBaseAttachmentService(session)
        attachment_service.update_attachment(
            user_id=owner_id,
            attachment_id=attachment_id,
            mount_alias="rebuild-docs-v2",
            mode="ro",
        )
        session.commit()

    with session_factory() as session:
        WorkspaceLifecycleService(session).restart_workspace_task(workspace_id)

    rebuilt_runtime_context = fake_orchestrator.runtime_contexts[-1]
    kb_mounts = {
        volume.target: volume
        for volume in rebuilt_runtime_context.volumes
        if volume.target.startswith("/knowledge/")
    }

    assert "/knowledge/rebuild-docs-v2" in kb_mounts
    assert "/knowledge/rebuild-docs" not in kb_mounts
    assert kb_mounts["/knowledge/rebuild-docs-v2"].read_only is True
