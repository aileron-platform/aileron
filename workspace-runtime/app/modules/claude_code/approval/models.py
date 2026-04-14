"""工具審批資料模型"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApprovalDecision(str, Enum):
    """審批決策"""

    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


class ToolApprovalRequest(BaseModel):
    """工具審批請求"""

    request_id: str = Field(..., description="請求 ID")
    workspace_id: str = Field(..., description="工作區 ID")
    session_id: str = Field(..., description="會話 ID")
    tool_name: str = Field(..., description="工具名稱")
    tool_input: Dict[str, Any] = Field(..., description="工具輸入參數")
    timeout_seconds: int = Field(default=60, description="超時秒數")

    model_config = {"populate_by_name": True}


class ToolApprovalResponse(BaseModel):
    """工具審批回應"""

    request_id: str = Field(..., description="請求 ID")
    decision: ApprovalDecision = Field(..., description="審批決策")
    reason: Optional[str] = Field(default=None, description="決策原因")

    model_config = {"populate_by_name": True}


class WebSocketApprovalRequest(BaseModel):
    """WebSocket 審批請求訊息"""

    type: str = Field(default="tool_approval_request", description="訊息類型")
    request_id: str = Field(..., description="請求 ID")
    session_id: str = Field(..., description="會話 ID")
    tool_name: str = Field(..., description="工具名稱")
    tool_input: Dict[str, Any] = Field(..., description="工具輸入參數")
    timeout: int = Field(..., description="超時秒數")

    model_config = {"populate_by_name": True}


class WebSocketApprovalResponse(BaseModel):
    """WebSocket 審批回應訊息"""

    type: str = Field(default="tool_approval_response", description="訊息類型")
    request_id: str = Field(..., alias="request_id", description="請求 ID")
    approved: bool = Field(..., description="是否批准")
    reason: Optional[str] = Field(default=None, description="決策原因")

    model_config = {"populate_by_name": True}

