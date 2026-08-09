"""Aileron platform MCP server.

Spawned directly by agent CLIs via MCP config; MUST stay stdlib-only.
Tool call/result events flow back through the agent message stream, so this
server never talks to the runtime API.
"""

from __future__ import annotations

import json
import sys
from typing import Any

QUESTION_FORM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "Stable form id in kebab-case, e.g. 'import-strategy'",
        },
        "title": {"type": "string", "description": "Form title shown to the user"},
        "questions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "radio",
                            "checkbox",
                            "select",
                            "text",
                            "textarea",
                            "number",
                            "date",
                            "yes-no",
                            "option-cards",
                            "color",
                        ],
                    },
                    "options": {"type": "array", "items": {"type": "string"}},
                    "cards": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                                "icon": {"type": "string"},
                                "mood": {"type": "string"},
                                "palette": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "displayFont": {"type": "string"},
                                "bodyFont": {"type": "string"},
                            },
                            "required": ["id", "label"],
                        },
                    },
                    "placeholder": {"type": "string"},
                    "default": {
                        "type": ["string", "array"],
                        "items": {"type": "string"},
                    },
                    "required": {"type": "boolean"},
                    "min": {"type": ["number", "string"]},
                    "max": {"type": ["number", "string"]},
                    "step": {"type": "number"},
                    "unit": {"type": "string"},
                    "mode": {"type": "string", "enum": ["date", "datetime"]},
                    "yes_label": {"type": "string"},
                    "no_label": {"type": "string"},
                    "multiple": {"type": "boolean"},
                    "swatches": {"type": "array", "items": {"type": "string"}},
                    "allow_custom": {"type": "boolean"},
                    "show_if": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "eq": {"type": "string"},
                            "in": {"type": "array", "items": {"type": "string"}},
                            "not_empty": {"type": "boolean"},
                        },
                        "required": ["q"],
                    },
                    "options_by": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "map": {"type": "object"},
                        },
                        "required": ["q", "map"],
                    },
                },
                "required": ["id", "label", "type"],
            },
        },
    },
    "required": ["id", "title", "questions"],
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "ask_user_question",
        "description": (
            "Use this tool as mcp__aileron__ask_user_question to ask the user "
            "one or more questions using a structured form "
            "(radio/checkbox/select/text/textarea/number/date/yes-no/"
            "option-cards/color, with show_if and options_by conditions). "
            "Hard cap: 5 questions. Count before emitting; if more, delete "
            "the least decision-critical until 5 or fewer remain. A question "
            "earns its place only when its answer changes the result. "
            "The form is delivered to the user asynchronously. After calling "
            "this tool you MUST end your turn immediately and send no "
            "additional assistant text; the user's answers will arrive as a "
            "follow-up user message in a later turn."
        ),
        "inputSchema": QUESTION_FORM_SCHEMA,
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "show_canvas_artifact",
        "description": (
            "Use this tool as mcp__aileron__show_canvas_artifact to show the "
            "user a card announcing a canvas artifact you produced (a page or "
            "view served by the workspace canvas app). Call it after the "
            "artifact is ready. This does not pause the turn."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Artifact title"},
                "route": {
                    "type": "string",
                    "description": "Canvas route path, e.g. '/landing'",
                },
            },
            "required": ["title"],
        },
    },
]

QUESTION_DELIVERED_TEXT = (
    "Question form delivered to the user. They will answer asynchronously; "
    "the answers will arrive as a follow-up user message. "
    "End your turn now and wait. Do not send any additional assistant text."
)
CANVAS_SHOWN_TEXT = "Canvas artifact card shown to the user."


def _text_result(
    text: str,
    *,
    is_error: bool = False,
    structured_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if structured_content is not None:
        result["structuredContent"] = structured_content
    if is_error:
        result["isError"] = True
    return result


def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    tool_name = params.get("name")
    if tool_name == "ask_user_question":
        arguments = params.get("arguments")
        return _text_result(
            QUESTION_DELIVERED_TEXT,
            structured_content=arguments if isinstance(arguments, dict) else None,
        )
    if tool_name == "show_canvas_artifact":
        return _text_result(CANVAS_SHOWN_TEXT)
    return _text_result(f"Unknown tool: {tool_name}", is_error=True)


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        params = request.get("params") or {}
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aileron", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _handle_tools_call(request.get("params") or {}),
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": {}}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
