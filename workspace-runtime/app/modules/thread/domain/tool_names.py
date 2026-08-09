"""Canonical names for platform MCP tools as they appear in agent streams."""

from __future__ import annotations

QUESTION_TOOL_NAME = "mcp__aileron__ask_user_question"
CANVAS_TOOL_NAME = "mcp__aileron__show_canvas_artifact"

QUESTION_EXPIRED_CODE = "question_expired"
QUESTION_EXPIRED_ALREADY_ANSWERED = "already_answered"
QUESTION_EXPIRED_SUPERSEDED = "superseded"
QUESTION_EXPIRED_NOT_DELIVERED = "not_delivered"
QUESTION_EXPIRED_QUEUED_MESSAGES = "queued_messages"
