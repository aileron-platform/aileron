from __future__ import annotations

from codex_app_server.generated.v2_all import (
    AgentMessageDeltaNotification,
    AgentMessageThreadItem,
    CommandExecutionOutputDeltaNotification,
    CommandExecutionStatus,
    CommandExecutionThreadItem,
    FileChangePatchUpdatedNotification,
    FileChangeThreadItem,
    FileUpdateChange,
    ImageGenerationThreadItem,
    ItemCompletedNotification,
    ItemStartedNotification,
    PatchApplyStatus,
    PlanDeltaNotification,
    ReasoningSummaryTextDeltaNotification,
    ThreadTokenUsage,
    ThreadTokenUsageUpdatedNotification,
    TokenUsageBreakdown,
)

from app.modules.agent_session.services.tools.codex.notification_mapper import (
    CommandOutputDelta,
    CommandToolEnd,
    CommandToolStart,
    FileChangeEnd,
    FileChangePatchUpdated,
    FileChangeStart,
    ImageGenerationEnd,
    PlanDelta,
    TextDelta,
    TextFinal,
    ThinkingDelta,
    TokenUsageEvent,
    NotificationMapper,
)


def _change(path: str = "a.py") -> FileUpdateChange:
    return FileUpdateChange.model_validate(
        {"path": path, "diff": "diff --git", "kind": {"type": "update"}}
    )


def test_notification_mapper_handles_text_and_token_usage() -> None:
    mapper = NotificationMapper()

    delta = mapper.dispatch(
        "item/agentMessage/delta",
        AgentMessageDeltaNotification(
            itemId="item-1",
            delta="hi",
            threadId="thread-1",
            turnId="turn-1",
        ),
    )
    assert delta == TextDelta(item_id="item-1", delta="hi")

    final = mapper.dispatch(
        "item/completed",
        ItemCompletedNotification(
            item=AgentMessageThreadItem(id="item-1", text="hello", type="agentMessage"),
            threadId="thread-1",
            turnId="turn-1",
        ),
    )
    assert final == TextFinal(item_id="item-1", text="hello")

    usage = mapper.dispatch(
        "thread/tokenUsage/updated",
        ThreadTokenUsageUpdatedNotification(
            threadId="thread-1",
            turnId="turn-1",
            tokenUsage=ThreadTokenUsage(
                last=TokenUsageBreakdown(
                    totalTokens=1,
                    inputTokens=1,
                    outputTokens=0,
                    cachedInputTokens=0,
                    reasoningOutputTokens=0,
                ),
                total=TokenUsageBreakdown(
                    totalTokens=3,
                    inputTokens=2,
                    outputTokens=1,
                    cachedInputTokens=0,
                    reasoningOutputTokens=0,
                ),
            ),
        ),
    )
    assert isinstance(usage, TokenUsageEvent)
    assert usage.token_usage["total"]["total_tokens"] == 3


def test_notification_mapper_handles_command_events() -> None:
    mapper = NotificationMapper()
    item = CommandExecutionThreadItem(
        id="cmd-1",
        type="commandExecution",
        command="ls",
        commandActions=[],
        cwd="/workspace",
        status=CommandExecutionStatus.in_progress,
    )

    started = mapper.dispatch(
        "item/started",
        ItemStartedNotification(item=item, threadId="thread-1", turnId="turn-1"),
    )
    assert started == CommandToolStart(item_id="cmd-1", command="ls", cwd="/workspace")

    delta = mapper.dispatch(
        "item/commandExecution/outputDelta",
        CommandExecutionOutputDeltaNotification(
            itemId="cmd-1",
            delta="out",
            threadId="thread-1",
            turnId="turn-1",
        ),
    )
    assert delta == CommandOutputDelta(item_id="cmd-1", delta="out")

    completed = mapper.dispatch(
        "item/completed",
        ItemCompletedNotification(
            item=item.model_copy(
                update={
                    "status": CommandExecutionStatus.completed,
                    "aggregated_output": "done",
                    "exit_code": 0,
                }
            ),
            threadId="thread-1",
            turnId="turn-1",
        ),
    )
    assert completed == CommandToolEnd(
        item_id="cmd-1",
        aggregated_output="done",
        status=CommandExecutionStatus.completed,
        exit_code=0,
    )


def test_notification_mapper_handles_file_reasoning_and_plan_events() -> None:
    mapper = NotificationMapper()
    change = _change()
    file_item = FileChangeThreadItem(
        id="file-1",
        type="fileChange",
        changes=[change],
        status=PatchApplyStatus.in_progress,
    )

    assert mapper.dispatch(
        "item/started",
        ItemStartedNotification(item=file_item, threadId="thread-1", turnId="turn-1"),
    ) == FileChangeStart(item_id="file-1", changes=[change])

    assert mapper.dispatch(
        "item/fileChange/patchUpdated",
        FileChangePatchUpdatedNotification(
            itemId="file-1",
            changes=[change],
            threadId="thread-1",
            turnId="turn-1",
        ),
    ) == FileChangePatchUpdated(item_id="file-1", changes=[change])

    file_end = mapper.dispatch(
        "item/completed",
        ItemCompletedNotification(
            item=file_item.model_copy(update={"status": PatchApplyStatus.completed}),
            threadId="thread-1",
            turnId="turn-1",
        ),
    )
    assert file_end == FileChangeEnd(item_id="file-1", changes=[change], status=PatchApplyStatus.completed)
    assert [
        {"type": "diff", "path": item.path, "newText": item.diff}
        for item in file_end.changes
    ] == [{"type": "diff", "path": "a.py", "newText": "diff --git"}]

    assert mapper.dispatch(
        "item/reasoning/summaryTextDelta",
        ReasoningSummaryTextDeltaNotification(
            itemId="think-1",
            summaryIndex=0,
            delta="thinking",
            threadId="thread-1",
            turnId="turn-1",
        ),
    ) == ThinkingDelta(item_id="think-1", delta="thinking")

    assert mapper.dispatch(
        "item/plan/delta",
        PlanDeltaNotification(
            itemId="plan-1",
            delta="step",
            threadId="thread-1",
            turnId="turn-1",
        ),
    ) == PlanDelta(item_id="plan-1", delta="step")


def test_notification_mapper_handles_image_generation_completion() -> None:
    mapper = NotificationMapper()

    event = mapper.dispatch(
        "item/completed",
        ItemCompletedNotification(
            item=ImageGenerationThreadItem.model_validate(
                {
                    "id": "image-1",
                    "type": "imageGeneration",
                    "status": "completed",
                    "result": "result-data",
                    "revisedPrompt": "a tiny robot",
                    "savedPath": "/home/developer/.codex/generated_images/image.png",
                }
            ),
            threadId="thread-1",
            turnId="turn-1",
        ),
    )

    assert event == ImageGenerationEnd(
        item_id="image-1",
        status="completed",
        result="result-data",
        saved_path="/home/developer/.codex/generated_images/image.png",
        revised_prompt="a tiny robot",
    )
