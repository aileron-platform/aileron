"""Prompt Invocation Catalog routes."""

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.openapi import build_responses

from .catalog import (
    PromptInvocationCatalogService,
    PromptInvocationCatalogUnavailableError,
)
from .config import PromptInvocationTool
from .dependencies import make_prompt_invocation_catalog_dependency
from .models import PromptInvocationCatalogResponse


def create_prompt_invocations_router(tool: PromptInvocationTool) -> APIRouter:
    """Create a Prompt Invocation Catalog router for one Agentic Tool."""

    router = APIRouter(
        prefix=f"/cli-settings/{tool.value}/prompt-invocations",
        tags=[f"{tool.value} - Prompt Invocations"],
    )
    get_service = make_prompt_invocation_catalog_dependency(tool)

    @router.get(
        "",
        response_model=PromptInvocationCatalogResponse,
        summary="List Prompt Invocations",
        responses=build_responses(401, 404, 500, 503),
    )
    async def list_prompt_invocations(
        workspace_id: str = Path(..., description="Workspace ID"),
        service: PromptInvocationCatalogService = Depends(get_service),
    ) -> PromptInvocationCatalogResponse:
        try:
            return service.list_catalog(workspace_id)
        except PromptInvocationCatalogUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "errorCode": "PROMPT_INVOCATION_CATALOG_UNAVAILABLE",
                    "message": str(error),
                    "sourceErrors": [
                        source_error.model_dump(by_alias=True)
                        for source_error in error.source_errors
                    ],
                },
            ) from error

    return router
