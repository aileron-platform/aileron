from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from claude_agent_sdk import ClaudeAgentOptions

from app.modules.thread.domain.tool_names import CANVAS_TOOL_NAME, QUESTION_TOOL_NAME
from app.modules.thread.mcp.agent_policy import AILERON_MCP_POLICY_PROMPT
from app.modules.thread.mcp.config import AILERON_MCP_SERVER_PATH
from app.modules.thread.execution import AgentExecutionRequest

CLAUDE_PLAN_ALLOWED_TOOLS = (
    "WebSearch",
    "WebFetch",
    "Read",
    "Bash",
    "ToolSearch",
    QUESTION_TOOL_NAME,
    CANVAS_TOOL_NAME,
)
CLAUDE_AILERON_MCP_PROMPT = (
    "Aileron platform MCP tools are available under their full Claude tool "
    "names: mcp__aileron__ask_user_question and "
    "mcp__aileron__show_canvas_artifact. Do not search for or call the bare "
    "names ask_user_question or show_canvas_artifact. These MCP tools may be "
    "deferred; before the first call, load the schema with ToolSearch using "
    "select:mcp__aileron__ask_user_question or "
    "select:mcp__aileron__show_canvas_artifact. Use "
    "mcp__aileron__ask_user_question for structured user forms and end your "
    "turn immediately after that tool call; do not send any additional "
    "assistant text after the question tool call because the UI must remain "
    "waiting for the user's form submission. Use "
    "mcp__aileron__show_canvas_artifact to show a canvas artifact card after "
    "the artifact is ready.\n\n"
    f"{AILERON_MCP_POLICY_PROMPT}"
)
MCP_CONFIG_DIR = Path(tempfile.gettempdir()) / "aileron-mcp-configs"
_MCP_CONFIG_LOCK = threading.Lock()
ClaudePermissionMode = Literal[
    "default",
    "acceptEdits",
    "plan",
    "bypassPermissions",
    "dontAsk",
    "auto",
]


def _resolve_permission_mode(request: AgentExecutionRequest) -> ClaudePermissionMode:
    permission_mode = request.permission_mode
    if permission_mode is None:
        return "plan" if request.claude_mode == "plan" else "bypassPermissions"
    if permission_mode == "default":
        return "default"
    if permission_mode == "acceptEdits":
        return "acceptEdits"
    if permission_mode == "plan":
        return "plan"
    if permission_mode == "bypassPermissions":
        return "bypassPermissions"
    if permission_mode == "dontAsk":
        return "dontAsk"
    if permission_mode == "auto":
        return "auto"
    raise ValueError("unsupported_permission_mode")


def build_claude_options(
    *,
    workspace_id: str,
    request: AgentExecutionRequest,
    cwd: str | Path,
) -> ClaudeAgentOptions:
    permission_mode = _resolve_permission_mode(request)

    allowed_tools = list(CLAUDE_PLAN_ALLOWED_TOOLS) if permission_mode == "plan" else []

    return ClaudeAgentOptions(
        cwd=cwd,
        cli_path="claude",
        model=request.model,
        resume=request.agent_resume_id,
        mcp_servers=ensure_claude_mcp_config(workspace_id),
        permission_mode=permission_mode,
        allowed_tools=allowed_tools,
        setting_sources=["user", "project"],
        include_partial_messages=False,
        extra_args={"thinking-display": "summarized"},
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": CLAUDE_AILERON_MCP_PROMPT,
        },
    )


def prompt_with_attachments(request: AgentExecutionRequest) -> str:
    if not request.attachments:
        return request.prompt_text
    attachment_lines = "\n".join(
        _attachment_prompt_line(attachment) for attachment in request.attachments
    )
    return f"{request.prompt_text}\n\nAttachments:\n{attachment_lines}"


def ensure_claude_mcp_config(workspace_id: str) -> str:
    config_path = _workspace_mcp_config_path(workspace_id)
    if config_path.exists():
        return str(config_path)

    config = {
        "mcpServers": {
            "aileron": {
                "command": sys.executable,
                "args": [str(AILERON_MCP_SERVER_PATH)],
            }
        }
    }
    payload = json.dumps(config)
    with _MCP_CONFIG_LOCK:
        if config_path.exists():
            return str(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = config_path.with_suffix(f"{config_path.suffix}.{uuid4().hex}.tmp")
        temp_path.write_text(payload)
        temp_path.replace(config_path)
    return str(config_path)


def _workspace_mcp_config_path(workspace_id: str) -> Path:
    safe_workspace_id = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in workspace_id
    ).strip("-")
    return MCP_CONFIG_DIR / f"{safe_workspace_id or 'workspace'}-mcp-config.json"


def _attachment_prompt_line(attachment: dict[str, Any]) -> str:
    attachment_type = str(attachment.get("type") or "file")
    name = str(attachment.get("name") or "unnamed")
    mime_type = str(attachment.get("mimeType") or "application/octet-stream")
    path = str(attachment.get("path") or "")
    if attachment_type == "text-file":
        return f"Attached text file {name} ({mime_type}): {path}"
    if attachment_type == "pdf":
        return f"Attached PDF {name} ({mime_type}): {path}"
    if attachment_type == "image":
        return f"Attached image {name} ({mime_type}): {path}"
    return f"Attached file {name} ({mime_type}): {path}"
