"""Map Codex SDK notifications to side-effect-free internal events."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Union

from codex_app_server.generated.v2_all import (
    AgentMessageDeltaNotification,
    AgentMessageThreadItem,
    CommandExecutionOutputDeltaNotification,
    CommandExecutionStatus,
    CommandExecutionThreadItem,
    ErrorNotification,
    FileChangeOutputDeltaNotification as SdkFileChangeOutputDeltaNotification,
    FileChangePatchUpdatedNotification,
    FileChangeThreadItem,
    FileUpdateChange,
    ImageGenerationThreadItem,
    ItemCompletedNotification,
    ItemStartedNotification,
    PatchApplyStatus,
    PlanDeltaNotification,
    ReasoningSummaryPartAddedNotification,
    ReasoningSummaryTextDeltaNotification,
    ReasoningTextDeltaNotification,
    ReasoningThreadItem,
    ThreadTokenUsageUpdatedNotification,
)
from codex_app_server.models import UnknownNotification

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TextDelta:
    item_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class TextFinal:
    item_id: str
    text: str


@dataclass(frozen=True, slots=True)
class CommandToolStart:
    item_id: str
    command: str
    cwd: str


@dataclass(frozen=True, slots=True)
class CommandOutputDelta:
    item_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class CommandToolEnd:
    item_id: str
    aggregated_output: str
    status: CommandExecutionStatus
    exit_code: int | None


@dataclass(frozen=True, slots=True)
class FileChangeStart:
    item_id: str
    changes: list[FileUpdateChange]


@dataclass(frozen=True, slots=True)
class FileChangeOutputDelta:
    item_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class FileChangePatchUpdated:
    item_id: str
    changes: list[FileUpdateChange]


@dataclass(frozen=True, slots=True)
class FileChangeEnd:
    item_id: str
    changes: list[FileUpdateChange]
    status: PatchApplyStatus


@dataclass(frozen=True, slots=True)
class ImageGenerationEnd:
    item_id: str
    status: str
    result: str
    saved_path: str | None
    revised_prompt: str | None


@dataclass(frozen=True, slots=True)
class ThinkingDelta:
    item_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class ThinkingPart:
    item_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ThinkingEnd:
    item_id: str


@dataclass(frozen=True, slots=True)
class PlanDelta:
    item_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class TokenUsageEvent:
    token_usage: dict


@dataclass(frozen=True, slots=True)
class IgnoredEvent:
    method: str


@dataclass(frozen=True, slots=True)
class StreamError:
    message: str
    will_retry: bool


CodexEvent = Union[
    TextDelta,
    TextFinal,
    CommandToolStart,
    CommandOutputDelta,
    CommandToolEnd,
    FileChangeStart,
    FileChangeOutputDelta,
    FileChangePatchUpdated,
    FileChangeEnd,
    ImageGenerationEnd,
    ThinkingDelta,
    ThinkingPart,
    ThinkingEnd,
    PlanDelta,
    TokenUsageEvent,
    IgnoredEvent,
    StreamError,
]


class NotificationMapper:
    """Pure Codex notification decoder."""

    def __init__(self) -> None:
        self._logged_methods: set[str] = set()

    def dispatch(self, method: str, payload) -> CodexEvent:
        if isinstance(payload, AgentMessageDeltaNotification):
            return TextDelta(item_id=payload.item_id, delta=payload.delta)

        if isinstance(payload, CommandExecutionOutputDeltaNotification):
            return CommandOutputDelta(item_id=payload.item_id, delta=payload.delta)

        if isinstance(payload, SdkFileChangeOutputDeltaNotification):
            return FileChangeOutputDelta(item_id=payload.item_id, delta=payload.delta)

        if isinstance(payload, FileChangePatchUpdatedNotification):
            return FileChangePatchUpdated(item_id=payload.item_id, changes=payload.changes)

        if isinstance(payload, ReasoningSummaryTextDeltaNotification):
            return ThinkingDelta(item_id=payload.item_id, delta=payload.delta)

        if isinstance(payload, ReasoningTextDeltaNotification):
            return ThinkingDelta(item_id=payload.item_id, delta=payload.delta)

        if isinstance(payload, ReasoningSummaryPartAddedNotification):
            return ThinkingPart(item_id=payload.item_id, text="")

        if isinstance(payload, PlanDeltaNotification):
            return PlanDelta(item_id=payload.item_id, delta=payload.delta)

        if isinstance(payload, ThreadTokenUsageUpdatedNotification):
            return TokenUsageEvent(
                token_usage=payload.token_usage.model_dump(by_alias=False)
            )

        if isinstance(payload, ErrorNotification):
            return StreamError(
                message=payload.error.message,
                will_retry=payload.will_retry,
            )

        if isinstance(payload, ItemStartedNotification):
            item = self._unwrap_item(payload.item)
            if isinstance(item, CommandExecutionThreadItem):
                return CommandToolStart(
                    item_id=item.id,
                    command=item.command,
                    cwd=str(self._unwrap_value(item.cwd)),
                )
            if isinstance(item, FileChangeThreadItem):
                return FileChangeStart(item_id=item.id, changes=item.changes)

        if isinstance(payload, ItemCompletedNotification):
            item = self._unwrap_item(payload.item)
            if isinstance(item, AgentMessageThreadItem):
                return TextFinal(item_id=item.id, text=item.text)
            if isinstance(item, CommandExecutionThreadItem):
                return CommandToolEnd(
                    item_id=item.id,
                    aggregated_output=item.aggregated_output or "",
                    status=item.status,
                    exit_code=item.exit_code,
                )
            if isinstance(item, FileChangeThreadItem):
                return FileChangeEnd(
                    item_id=item.id,
                    changes=item.changes,
                    status=item.status,
                )
            if isinstance(item, ImageGenerationThreadItem):
                saved_path = (
                    str(self._unwrap_value(item.saved_path))
                    if item.saved_path
                    else None
                )
                return ImageGenerationEnd(
                    item_id=item.id,
                    status=item.status,
                    result=item.result,
                    saved_path=saved_path,
                    revised_prompt=item.revised_prompt,
                )
            if isinstance(item, ReasoningThreadItem):
                return ThinkingEnd(item_id=item.id)

        if isinstance(payload, UnknownNotification):
            return self._ignored(method)

        return self._ignored(method)

    @staticmethod
    def _unwrap_item(item):
        return getattr(item, "root", item)

    @staticmethod
    def _unwrap_value(value):
        return getattr(value, "root", value)

    def _ignored(self, method: str) -> IgnoredEvent:
        if method not in self._logged_methods:
            self._logged_methods.add(method)
            logger.debug("Ignoring Codex notification method=%s", method)
        return IgnoredEvent(method=method)
