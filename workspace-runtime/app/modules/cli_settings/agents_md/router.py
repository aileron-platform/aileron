"""CLI Agents MD 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses

from .dependencies import make_agents_md_service_dependency
from .models import AgentsMdDocument, AgentsMdScope, AgentsMdUpdateRequest, AgentsMdUpdateResponse
from .service import AgentsMdService, AgentsMdTool, get_agents_md_config


def create_agents_md_router(tool: AgentsMdTool) -> APIRouter:
    config = get_agents_md_config(tool)
    router = APIRouter(
        prefix=f"/{tool.value}",
        tags=[f"{tool.value} - Agents MD"],
    )

    get_service = make_agents_md_service_dependency(tool)

    @router.get(
        f"/{config.endpoint_name}",
        response_model=AgentsMdDocument,
        summary="取得 Agents MD 內容",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def get_agents_md(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: AgentsMdScope = Query(..., description="檔案範圍"),
        service: AgentsMdService = Depends(get_service),
    ) -> AgentsMdDocument:
        return service.get_document(workspace_id, scope)

    @router.put(
        f"/{config.endpoint_name}",
        response_model=AgentsMdUpdateResponse,
        summary="更新 Agents MD 內容",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def update_agents_md(
        payload: AgentsMdUpdateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        service: AgentsMdService = Depends(get_service),
    ) -> AgentsMdUpdateResponse:
        return service.update_document(workspace_id, payload)

    return router
