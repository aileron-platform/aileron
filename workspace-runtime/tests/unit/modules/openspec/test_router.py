from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.openspec.models import (
    OpenSpecActionAvailability,
    OpenSpecActionContextSubview,
    OpenSpecActionGroup,
    OpenSpecActionItem,
    OpenSpecCustomizationActionResponse,
    OpenSpecCustomizationDebugResponse,
    OpenSpecCustomizationDiagnostic,
    OpenSpecCustomizationFileKind,
    OpenSpecCustomizationFileResponse,
    OpenSpecCustomizationResolutionStep,
    OpenSpecCustomizationStateResponse,
    OpenSpecCustomizationValidationResponse,
    OpenSpecActionProfile,
    OpenSpecChangeStatus,
    OpenSpecNavigationChange,
    OpenSpecWorkspaceResponse,
    OpenSpecWorkspaceSummaryCounts,
    OpenSpecWorkspaceSummaryResponse,
    OpenSpecSpecDocument,
    OpenSpecWorkspaceState,
)

openspec_router_module = importlib.import_module("app.modules.openspec.router")


class FakeOpenSpecService:
    def __init__(self) -> None:
        self.last_context: tuple[OpenSpecActionContextSubview | None, str | None] | None = None

    def get_workspace_state(
        self,
        workspace_id: str,
        *,
        translate=None,
        language=None,
        subview=None,
        focused_change_name=None,
    ) -> OpenSpecWorkspaceResponse:
        self.last_context = (subview, focused_change_name)
        title = translate("openspec.actions.propose.title") if translate else "Propose"
        description = translate("openspec.actions.propose.description") if translate else "Create change"
        return OpenSpecWorkspaceResponse(
            workspaceId=workspace_id,
            state=OpenSpecWorkspaceState(
                cliInstalled=True,
                cliVersion="1.3.0",
                initialized=True,
                profile=OpenSpecActionProfile.CORE,
                projectSynced=True,
                activeChanges=[],
            ),
            actions=[
                OpenSpecActionItem(
                    id="propose",
                    title=title,
                    description=description,
                    group=OpenSpecActionGroup.START,
                    profile=OpenSpecActionProfile.CORE,
                    availability=OpenSpecActionAvailability.ENABLED,
                    recommended=True,
                    requiresChange=False,
                    supportsChangeArgument=False,
                    draftTemplate="/opsx:propose ",
                )
            ],
            changes=[
                OpenSpecNavigationChange(
                    name="add-auth",
                    status=OpenSpecChangeStatus.IN_PROGRESS,
                    archived=False,
                    proposalPath="/openspec/changes/add-auth/proposal.md",
                    designPath="/openspec/changes/add-auth/design.md",
                    tasksPath="/openspec/changes/add-auth/tasks.md",
                    specs=[
                        OpenSpecSpecDocument(
                            capabilityName="auth",
                            path="/openspec/changes/add-auth/specs/auth/spec.md",
                        )
                    ],
                    completedTasks=1,
                    totalTasks=3,
                )
            ],
        )

    def get_workspace_summary(self, workspace_id: str) -> OpenSpecWorkspaceSummaryResponse:
        return OpenSpecWorkspaceSummaryResponse(
            workspaceId=workspace_id,
            initialized=True,
            counts=OpenSpecWorkspaceSummaryCounts(
                inProgress=1,
                complete=2,
                archived=3,
            ),
        )

    def get_customization_state(self, workspace_id: str) -> OpenSpecCustomizationStateResponse:
        return OpenSpecCustomizationStateResponse(
            workspaceId=workspace_id,
            configPath="/openspec/config.yaml",
            configPresent=True,
            defaultSchema="review-flow",
            builtInSchemas=["spec-driven"],
            schemas=[],
        )

    def read_customization_file(self, workspace_id: str, path: str) -> OpenSpecCustomizationFileResponse:
        return OpenSpecCustomizationFileResponse(
            workspaceId=workspace_id,
            path=path,
            name="config.yaml",
            kind=OpenSpecCustomizationFileKind.CONFIG,
            content="schema: review-flow\n",
            editable=True,
            language="yaml",
            metadata={},
        )

    def update_customization_file(self, workspace_id: str, path: str, content: str) -> OpenSpecCustomizationActionResponse:
        return OpenSpecCustomizationActionResponse(success=True, message="saved", path=path)

    def fork_customization_schema(self, workspace_id: str, *, source_schema: str, destination_schema: str) -> OpenSpecCustomizationActionResponse:
        return OpenSpecCustomizationActionResponse(success=True, message="forked", schemaName=destination_schema, path=f"/openspec/schemas/{destination_schema}")

    def init_customization_schema(self, workspace_id: str, *, name: str, description: str | None = None, artifacts: list[str] | None = None) -> OpenSpecCustomizationActionResponse:
        return OpenSpecCustomizationActionResponse(success=True, message="created", schemaName=name, path=f"/openspec/schemas/{name}")

    def validate_customization(self, workspace_id: str, *, path: str) -> OpenSpecCustomizationValidationResponse:
        return OpenSpecCustomizationValidationResponse(
            workspaceId=workspace_id,
            targetPath=path,
            schemaName="review-flow",
            valid=True,
            diagnostics=[OpenSpecCustomizationDiagnostic(level="info", message="ok")],
        )

    def debug_customization(self, workspace_id: str, *, path: str) -> OpenSpecCustomizationDebugResponse:
        return OpenSpecCustomizationDebugResponse(
            workspaceId=workspace_id,
            targetPath=path,
            schemaName="review-flow",
            resolvedName="review-flow",
            source="project",
            path="/openspec/schemas/review-flow",
            resolutionOrder=[
                OpenSpecCustomizationResolutionStep(order=1, label="selected schema", value="review-flow", selected=True),
            ],
        )


def _translate_zh(key: str) -> str:
    translations = {
        "openspec.actions.propose.title": "提案",
        "openspec.actions.propose.description": "建立 change",
    }
    return translations[key]


def test_openspec_router_returns_workspace_state() -> None:
    app = FastAPI()
    app.include_router(openspec_router_module.router, prefix="/api/v1")
    fake_service = FakeOpenSpecService()
    app.dependency_overrides[openspec_router_module.get_openspec_service] = lambda: fake_service

    @app.middleware("http")
    async def inject_i18n(request, call_next):
        request.state.language = "zh-TW"
        request.state.translate = _translate_zh
        return await call_next(request)

    client = TestClient(app)

    response = client.get(
        "/api/v1/workspaces/ws-1/openspec",
        params={"subview": "complete", "focusedChangeName": "add-auth"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspaceId"] == "ws-1"
    assert payload["state"]["cliInstalled"] is True
    assert payload["actions"][0]["id"] == "propose"
    assert payload["actions"][0]["title"] == "提案"
    assert payload["actions"][0]["description"] == "建立 change"
    assert payload["changes"][0]["name"] == "add-auth"
    assert payload["changes"][0]["status"] == "in-progress"
    assert fake_service.last_context == (OpenSpecActionContextSubview.COMPLETE, "add-auth")


def test_openspec_router_returns_workspace_summary() -> None:
    app = FastAPI()
    app.include_router(openspec_router_module.router, prefix="/api/v1")
    fake_service = FakeOpenSpecService()
    app.dependency_overrides[openspec_router_module.get_openspec_service] = lambda: fake_service

    client = TestClient(app)

    response = client.get("/api/v1/workspaces/ws-1/openspec/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "workspaceId": "ws-1",
        "initialized": True,
        "counts": {
            "inProgress": 1,
            "complete": 2,
            "archived": 3,
        },
    }


def test_openspec_router_accepts_customization_subview() -> None:
    app = FastAPI()
    app.include_router(openspec_router_module.router, prefix="/api/v1")
    fake_service = FakeOpenSpecService()
    app.dependency_overrides[openspec_router_module.get_openspec_service] = lambda: fake_service

    @app.middleware("http")
    async def inject_i18n(request, call_next):
        request.state.language = "zh-TW"
        request.state.translate = _translate_zh
        return await call_next(request)

    client = TestClient(app)

    response = client.get(
        "/api/v1/workspaces/ws-1/openspec",
        params={"subview": "customization"},
    )

    assert response.status_code == 200
    assert fake_service.last_context == (OpenSpecActionContextSubview.CUSTOMIZATION, None)


def test_openspec_customization_router_returns_state_and_file() -> None:
    app = FastAPI()
    app.include_router(openspec_router_module.router, prefix="/api/v1")
    fake_service = FakeOpenSpecService()
    app.dependency_overrides[openspec_router_module.get_openspec_service] = lambda: fake_service

    client = TestClient(app)

    state_response = client.get("/api/v1/workspaces/ws-1/openspec/customization")
    file_response = client.get(
        "/api/v1/workspaces/ws-1/openspec/customization/file",
        params={"path": "/openspec/config.yaml"},
    )

    assert state_response.status_code == 200
    assert state_response.json()["defaultSchema"] == "review-flow"
    assert file_response.status_code == 200
    assert file_response.json()["kind"] == "config"

    update_response = client.put(
        "/api/v1/workspaces/ws-1/openspec/customization/file",
        params={"path": "/openspec/config.yaml"},
        json={"content": "schema: rapid\n"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["message"] == "saved"


def test_openspec_customization_router_supports_validate_and_debug() -> None:
    app = FastAPI()
    app.include_router(openspec_router_module.router, prefix="/api/v1")
    fake_service = FakeOpenSpecService()
    app.dependency_overrides[openspec_router_module.get_openspec_service] = lambda: fake_service

    client = TestClient(app)

    validate_response = client.post(
        "/api/v1/workspaces/ws-1/openspec/customization/validate",
        json={"path": "/openspec/schemas/review-flow/schema.yaml"},
    )
    debug_response = client.get(
        "/api/v1/workspaces/ws-1/openspec/customization/debug",
        params={"path": "/openspec/schemas/review-flow/schema.yaml"},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["valid"] is True
    assert debug_response.status_code == 200
    assert debug_response.json()["resolvedName"] == "review-flow"

    fork_response = client.post(
        "/api/v1/workspaces/ws-1/openspec/customization/schemas/fork",
        json={"sourceSchema": "spec-driven", "destinationSchema": "review-flow-copy"},
    )
    create_response = client.post(
        "/api/v1/workspaces/ws-1/openspec/customization/schemas",
        json={"name": "new-flow", "description": "Manual QA workflow", "artifacts": ["proposal", "tasks"]},
    )

    assert fork_response.status_code == 200
    assert fork_response.json()["schemaName"] == "review-flow-copy"
    assert create_response.status_code == 200
    assert create_response.json()["schemaName"] == "new-flow"
