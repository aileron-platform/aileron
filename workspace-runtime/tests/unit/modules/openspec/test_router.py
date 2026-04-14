from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.openspec.models import (
    OpenSpecActionAvailability,
    OpenSpecActionContextSubview,
    OpenSpecActionGroup,
    OpenSpecActionItem,
    OpenSpecActionProfile,
    OpenSpecChangeStatus,
    OpenSpecNavigationChange,
    OpenSpecWorkspaceResponse,
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
