"""Workspace Manager OpenAPI 共用定義。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class APIErrorDetail(BaseModel):
    """標準 API 錯誤內容。"""

    error: str | None = Field(default=None, description="錯誤類型")
    message: str | None = Field(default=None, description="錯誤訊息")
    detail: str | dict | None = Field(default=None, description="詳細錯誤內容")
    request_id: str | None = Field(default=None, description="請求追蹤 ID")
    error_code: str | None = Field(default=None, description="機器可讀錯誤代碼")
    status_code: int | None = Field(default=None, description="HTTP 狀態碼")


COMMON_ERROR_RESPONSES = {
    400: {"model": APIErrorDetail, "description": "請求格式錯誤或參數不合法。"},
    401: {"model": APIErrorDetail, "description": "未提供有效的認證資訊。"},
    403: {"model": APIErrorDetail, "description": "目前使用者沒有操作權限。"},
    404: {"model": APIErrorDetail, "description": "指定資源不存在。"},
    409: {"model": APIErrorDetail, "description": "資源狀態衝突，無法完成操作。"},
    413: {"model": APIErrorDetail, "description": "請求內容超出允許大小限制。"},
    422: {"description": "請求資料驗證失敗。"},
    500: {"model": APIErrorDetail, "description": "伺服器內部錯誤。"},
    502: {"model": APIErrorDetail, "description": "上游服務回應錯誤。"},
    503: {"model": APIErrorDetail, "description": "服務暫時不可用。"},
}


def build_responses(
    *status_codes: int,
    model: type[BaseModel] | None = None,
    descriptions: dict[int, str] | None = None,
    examples: dict[int, dict[str, Any]] | None = None,
) -> dict[int, dict]:
    """依狀態碼挑選共用 OpenAPI 錯誤回應。"""

    responses: dict[int, dict] = {}
    for status_code in status_codes:
        if status_code not in COMMON_ERROR_RESPONSES:
            continue
        response = dict(COMMON_ERROR_RESPONSES[status_code])
        if model is not None and status_code != 422:
            response["model"] = model
        if descriptions and status_code in descriptions:
            response["description"] = descriptions[status_code]
        if examples and status_code in examples:
            response["content"] = {"application/json": {"examples": examples[status_code]}}
        responses[status_code] = response
    return responses
