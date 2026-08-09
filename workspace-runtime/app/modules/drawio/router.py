"""
Draw.io Integration Router
Provides API endpoints for viewing and editing Draw.io diagrams
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
import logging
import urllib.parse
from typing import Any

from app.modules.drawio.availability import DrawioAvailability, get_drawio_availability
from app.modules.file_system.dependencies import get_file_service_sync
from app.modules.file_system.exceptions import (
    FileManagementException,
    FileNotFoundException,
)
from app.modules.file_system.operations import FileService
from app.modules.localization.catalog import I18nService, get_i18n_service
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/drawio", tags=["Draw.io Integration"])


def _translate(i18n: I18nService, key: str, **kwargs: Any) -> str:
    return i18n.translate(key, **kwargs)


def _unavailable_detail(
    availability: DrawioAvailability, translate: I18nService
) -> dict[str, str | None]:
    return {
        "code": "DRAWIO_UNAVAILABLE",
        "reason": availability.reason,
        "message": _translate(translate, "drawio.errors.service_unavailable"),
    }


async def _ensure_drawio_available(translate: I18nService) -> None:
    availability = await get_drawio_availability(settings)
    if not availability.available:
        raise HTTPException(
            status_code=503,
            detail=_unavailable_detail(availability, translate),
        )


@router.get("/viewer")
async def get_drawio_viewer_url(
    file_path: str = Query(..., description="File path"),
    mode: str = Query("view", description="Mode: view or edit"),
    file_service: FileService = Depends(get_file_service_sync),
    translate: I18nService = Depends(get_i18n_service),
) -> JSONResponse:
    """
    Generate Draw.io viewer URL

    Args:
        file_path: Path to the .drawio file to view
        mode: View mode (view/edit)

    Returns:
        JSON response containing Draw.io URL

    Raises:
        HTTPException: When file does not exist or read fails
    """
    try:
        logger.info(f"Generating Draw.io URL for file: {file_path}, mode: {mode}")
        await _ensure_drawio_available(translate)

        # Read file content
        file_result = file_service.read_file(file_path)
        content = file_result["content"]

        if not content or not content.strip():
            raise HTTPException(
                status_code=400,
                detail=_translate(translate, "drawio.errors.empty_file"),
            )

        # External URL of Draw.io service (browser-accessible)
        drawio_base_url = settings.DRAWIO_EXTERNAL_URL

        # Build URL parameters
        params = {
            "embed": "1",  # Enable embed mode
            "proto": "json",  # Use JSON protocol for PostMessage communication
            "spin": "1",  # Show loading animation
            "ui": "atlas",  # Use Atlas UI theme
            "lang": "zh",  # Language setting
        }

        # Set different parameters based on mode
        if mode == "edit":
            params.update(
                {
                    "modified": "unsavedChanges",  # Mark as unsaved
                    "saveAndExit": "1",  # Enable save and exit
                    "noSaveBtn": "0",  # Show save button
                }
            )
        else:
            # View mode
            params.update(
                {
                    "chrome": "0",  # Hide toolbar
                    "toolbar": "0",  # Turn off Draw.io built-in hover toolbar
                    "nav": "1",  # Show navigation controls
                }
            )

        # Build complete URL
        query_string = urllib.parse.urlencode(params)
        # Do not embed XML in URL, send via PostMessage instead
        # Frontend will send load message after receiving init event
        full_url = f"{drawio_base_url}/?{query_string}"

        logger.info(f"Generated Draw.io URL successfully for {file_path}")

        return JSONResponse(
            content={"url": full_url, "mode": mode, "file_path": file_path}
        )

    except HTTPException:
        raise
    except FileNotFoundException as e:
        logger.error(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail=e.to_dict())
    except FileManagementException as e:
        logger.error(f"File management error generating Draw.io URL: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Error generating Draw.io URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_translate(
                translate, "drawio.errors.url_generation_failed", error=str(e)
            ),
        )


@router.post("/save")
async def save_drawio_file(
    file_path: str = Query(..., description="File path"),
    content: str = Body(..., description="XML content", embed=True),
    file_service: FileService = Depends(get_file_service_sync),
    translate: I18nService = Depends(get_i18n_service),
) -> JSONResponse:
    """
    Save Draw.io file

    Args:
        file_path: File path
        content: XML content

    Returns:
        JSON response of save result

    Raises:
        HTTPException: When save fails
    """
    try:
        logger.info(f"Saving Draw.io file: {file_path}")
        await _ensure_drawio_available(translate)

        # Validate content is not empty
        if not content or not content.strip():
            raise HTTPException(
                status_code=400,
                detail=_translate(translate, "drawio.errors.empty_content"),
            )

        # Validate if valid XML
        # Simple check: ensure contains mxfile or mxGraphModel tag
        if not ("<mxfile" in content or "<mxGraphModel" in content):
            logger.warning(f"Invalid Draw.io XML format for {file_path}")
            raise HTTPException(
                status_code=400,
                detail=_translate(translate, "drawio.errors.invalid_xml"),
            )

        # Save file
        file_service.write_file(file_path, content)

        logger.info(f"Draw.io file saved successfully: {file_path}")

        return JSONResponse(
            content={
                "success": True,
                "message": _translate(translate, "drawio.save_success"),
                "file_path": file_path,
            }
        )

    except HTTPException:
        raise
    except FileManagementException as e:
        logger.error(f"File management error saving Draw.io file: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Error saving Draw.io file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_translate(translate, "drawio.errors.save_failed", error=str(e)),
        )


@router.get("/availability")
async def get_drawio_availability_endpoint() -> JSONResponse:
    """Get Draw.io integration availability."""
    availability = await get_drawio_availability(settings)
    return JSONResponse(
        content={
            "available": availability.available,
            "reason": availability.reason,
            "checked_at": availability.checked_at.isoformat(),
        }
    )
