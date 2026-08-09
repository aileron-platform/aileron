from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException
from pydantic import BaseModel, Field


class ResourceResult(BaseModel):
    revision: str | None = None
    validation_results: list[Any] | None = Field(
        default=None,
        alias="validationResults",
    )
    resource: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


def raise_resource_error(
    code: str,
    message: str,
    status_code: int,
    validation: list[Any] | None = None,
) -> NoReturn:
    detail: dict[str, Any] = {"errorCode": code, "message": message}
    if validation is not None:
        detail["validationResults"] = validation
    raise HTTPException(status_code=status_code, detail=detail)
