"""Tool Approval Data Models"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApprovalDecision(str, Enum):
    """Approval decision"""

    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


class ToolApprovalRequest(BaseModel):
    """Tool approval request"""

    request_id: str = Field(..., description="Request ID")
    workspace_id: str = Field(..., description="Workspace ID")
    session_id: str = Field(..., description="Session ID")
    tool_name: str = Field(..., description="Tool name")
    tool_input: Dict[str, Any] = Field(..., description="Tool input parameters")
    timeout_seconds: int = Field(default=60, description="Timeout in seconds")

    model_config = {"populate_by_name": True}


class ToolApprovalResponse(BaseModel):
    """Tool approval response"""

    request_id: str = Field(..., description="Request ID")
    decision: ApprovalDecision = Field(..., description="Approval decision")
    reason: Optional[str] = Field(default=None, description="Decision reason")

    model_config = {"populate_by_name": True}


class WebSocketApprovalRequest(BaseModel):
    """WebSocket approval request message"""

    type: str = Field(default="tool_approval_request", description="Message type")
    request_id: str = Field(..., description="Request ID")
    session_id: str = Field(..., description="Session ID")
    tool_name: str = Field(..., description="Tool name")
    tool_input: Dict[str, Any] = Field(..., description="Tool input parameters")
    timeout: int = Field(..., description="Timeout in seconds")

    model_config = {"populate_by_name": True}


class WebSocketApprovalResponse(BaseModel):
    """WebSocket approval response message"""

    type: str = Field(default="tool_approval_response", description="Message type")
    request_id: str = Field(..., alias="request_id", description="Request ID")
    approved: bool = Field(..., description="Whether approved")
    reason: Optional[str] = Field(default=None, description="Decision reason")

    model_config = {"populate_by_name": True}

