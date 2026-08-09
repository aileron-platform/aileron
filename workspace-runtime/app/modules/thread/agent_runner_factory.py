from __future__ import annotations

import asyncio

from app.modules.thread.composite_agent_runner import CompositeAgentRunner

_runners: dict[str, CompositeAgentRunner] = {}


def get_agent_runner(workspace_id: str) -> CompositeAgentRunner:
    from app.modules.thread.claude_sdk_agent_runner import ClaudeSdkAgentRunner
    from app.modules.thread.codex_sdk_agent_runner import CodexSdkAgentRunner
    from app.modules.thread.opencode_acp_agent_runner import (
        OpenCodeAcpAgentRunner,
    )

    runner = _runners.get(workspace_id)
    if runner is None:
        runner = CompositeAgentRunner(
            opencode_runner=OpenCodeAcpAgentRunner(workspace_id=workspace_id),
            codex_runner=CodexSdkAgentRunner(workspace_id=workspace_id),
            claude_runner=ClaudeSdkAgentRunner(workspace_id=workspace_id),
        )
        _runners[workspace_id] = runner
    return runner


async def evict_idle_agent_runners() -> int:
    evicted = 0
    for runner in list(_runners.values()):
        evicted += await runner.evict_idle()
    return evicted


async def drain_agent_runners() -> None:
    """Stop all agent executions without creating new runner instances."""

    results = await asyncio.gather(
        *(runner.drain_all() for runner in list(_runners.values())),
        return_exceptions=True,
    )
    if any(isinstance(result, BaseException) for result in results):
        raise RuntimeError("agent_drain_incomplete")
