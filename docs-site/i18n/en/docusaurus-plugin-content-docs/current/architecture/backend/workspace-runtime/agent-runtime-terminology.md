---
title: Agent Runtime Terminology
---

# Agent Runtime Terminology

This page defines the core terminology Aileron uses in a multi-agent runtime and aligns it with Terragon's naming model. For complete definitions of Thread, Turn, and Turn Execution, see [AI Chat Frontend and Backend Architecture — Core Terminology](/architecture/overview/ai-chat#core-terminology).

## Core Principle

Aileron uses three independent identifiers:

- **Thread ID**: Aileron's platform task or conversation id.
- **Agent Resume ID**: The continuation id used by the agent runtime to resume a provider conversation. It belongs to an individual execution (turn execution).
- **Active Turn Execution ID**: The identifier of the current individual agent execution, used for stopping and liveness checks. It belongs to a thread.

Claude, Codex, and OpenCode may keep their formal session/thread fields at the external protocol boundary. Aileron immediately normalizes those values to `agentResumeId`. `threads.active_turn_execution_id` only identifies the current execution and is cleared when it completes or errors.

## Terminology Map

| Term | Aileron Mapping | Terragon Mapping | Meaning |
|---|---|---|---|
| Platform Thread ID / Thread ID | `threads.id`, API path `/{thread_id}`, selected frontend thread | `thread.id`, `threadId` | The platform-owned task or conversation id. Used for URLs, lists, lookups, and thread operations. |
| Thread | `threads` row | `thread` row | The task or conversation container visible to the user. |
| Agent Resume ID | `thread_turn_executions.agent_resume_id` (per-execution, exposed through `ThreadExecutionMetadataResponse.agentResumeId`), `system_init.content.agentResumeId` | `threadChat.sessionId`, DB `session_id` | The id used by the agent CLI to continue a conversation. It belongs to an individual execution (turn execution), not the whole thread. Claude calls it `session_id`; Codex calls it `thread_id`, but the first-party domain uses resume semantics. |
| Runtime Thread ID | Raw Codex `thread_id`; not a public Aileron term after normalization | Raw Codex `thread_id` | Codex CLI's raw field. The platform normalizes it to `agentResumeId` to avoid confusing it with the platform Thread ID. |
| Active Turn Execution ID | `threads.active_turn_execution_id` (API field `activeTurnExecutionId`), thread events `WS /api/v1/threads/events` | Running agent process in the daemon | Identifies the individual execution currently running for the thread and is used for stopping and liveness checks. Execution events are written back as thread messages, and the frontend refetches through thread events. It is cleared when execution completes or errors. It is not the resume id. |
| Thread Chat | Aileron has no separate concept with this name; a thread directly holds agent, model, status, and messages | `threadChat` | Terragon can have multiple chats or agent attempts under a platform thread. Aileron currently stores runtime state directly on the thread. |
| Agent / Agentic Tool | `agentic_tool`: `claude`, `codex`, `opencode` | `agent`: `claudeCode`, `codex`, `opencode`, `gemini`, `amp` | The agent provider or tool executing the task. |
| Model | `threads.model`, capabilities model | user message model / threadChat model selection | The model passed to the agent CLI. |
| System Init | `thread_messages.type = system_init` | DB message `type: "meta"`, `subtype: "system-init"` | Agent runtime startup event. Claude provides session, tools, and MCP metadata; Codex only provides the runtime continuation id. |
| Tool Call | `thread_messages.type = tool_call` | DB message `type: "tool-call"` | A tool call emitted by the agent. |
| Tool Result | `thread_messages.type = tool_result` | DB message `type: "tool-result"` | A tool execution result. |
| Agent Text | `thread_messages.type = agent_text` | DB message `type: "agent"` with text part | Text produced by the agent. |
| Thinking | `thread_messages.type = thinking` | DB message `type: "agent"` with thinking part | Agent thinking / reasoning display data. |
| User Message | `thread_messages.type = user` | DB message `type: "user"` | User input. |
| Resume | `agent_resume_id` mapped at the adapter boundary to Claude `--resume`, Codex `resume`, or the OpenCode session protocol | `threadChat.sessionId` passed to Claude / Codex / OpenCode resume or session flag | Continue an agent runtime conversation. |
| Platform Runtime | `workspace-runtime` | daemon / sandbox runtime | The execution layer that starts agents, receives events, normalizes events, and persists messages. |

## Normalization Rules

### Claude Code

Claude Code emits `session_id` in the raw init event:

```json
{
  "type": "system",
  "subtype": "init",
  "session_id": "claude-session-id"
}
```

Aileron normalizes it to (`content` always carries five fields):

```json
{
  "type": "system_init",
  "content": {
    "agentResumeId": "claude-session-id",
    "model": "claude-model-id",
    "cwd": "/workspace",
    "tools": ["Bash", "Read"],
    "mcpServers": []
  }
}
```

### Codex

Codex emits `thread_id` in the raw init event:

```json
{
  "type": "thread.started",
  "thread_id": "codex-runtime-thread-id"
}
```

Aileron normalizes it to (fields Codex does not provide stay empty; no metadata is invented):

```json
{
  "type": "system_init",
  "content": {
    "agentResumeId": "codex-runtime-thread-id",
    "model": null,
    "cwd": null,
    "tools": [],
    "mcpServers": []
  }
}
```

Here, `agentResumeId` is a provider conversation resume handle, not Aileron's platform `threads.id`.

## Usage Guidelines

- Use `threadId` when operating on an Aileron platform thread.
- Use `agentResumeId` or backend `agent_resume_id` when resuming an agent runtime conversation.
- Use the Active Turn Execution ID (`threads.active_turn_execution_id` / `activeTurnExecutionId`) for stopping and liveness checks. It is distinct from the resume id and belongs to the thread rather than to an individual execution.
- Do not expose Codex's raw `thread_id` as the platform `threadId`.
- Do not invent metadata that the agent raw event did not provide; only normalize fields.
- Documentation and UI copy use Agent Resume ID for continuation handles instead of the generic Session term.
