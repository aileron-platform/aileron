"""Internal API dependency injection"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config.settings import get_settings
from .service import InternalService

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_internal_token(
    authorization: Annotated[str | None, Header(description="Internal API authentication Token")] = None,
) -> None:
    """Verify internal API call permission"""
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Internal API call missing Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token for internal API",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Check if token is valid
    expected_token = getattr(settings, 'INTERNAL_API_TOKEN', 'dev-internal-token')
    if token != expected_token:
        logger.warning(f"Invalid internal API token: {token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API token",
        )

    logger.debug("Internal API token verified successfully")


def get_internal_service() -> InternalService:
    """Get Internal Service instance"""
    return InternalService()


__all__ = [
    "verify_internal_token",
    "get_internal_service",
]
