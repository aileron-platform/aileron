from __future__ import annotations

from enum import Enum


class ThreadStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    BOOTING = "booting"
    WORKING = "working"
    STOPPING = "stopping"
    COMPLETE = "complete"
    STOPPED = "stopped"
    ERROR = "error"
    CANCELED = "canceled"


class AgenticTool(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    OPENCODE = "opencode"


class ClaudeMode(str, Enum):
    EXECUTE = "execute"
    PLAN = "plan"


RUNNING_STATUSES = {
    ThreadStatus.QUEUED,
    ThreadStatus.BOOTING,
    ThreadStatus.WORKING,
    ThreadStatus.STOPPING,
}

RUNTIME_RESTART_RECONCILIATION_STATUSES = {
    ThreadStatus.QUEUED,
    ThreadStatus.BOOTING,
    ThreadStatus.WORKING,
}
