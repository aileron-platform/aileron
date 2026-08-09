---
title: Agent Runtime 名詞對照
---

# Agent Runtime 名詞對照

這份文件定義 Aileron 在多 Agent runtime 中使用的核心名詞，並對齊 Terragon 的命名模型。Thread、Turn 與 Turn Execution 的完整定義請見 [AI Chat 前後端架構 — 核心名詞](/architecture/overview/ai-chat#核心名詞)。

## 核心原則

Aileron 採用三個彼此獨立的 ID：

- **Thread ID**：Aileron 平台自己的任務或對話 ID。
- **Agent Resume ID**：Agent runtime 用來接續 provider 對話的 continuation ID，掛在單次執行（turn execution）上。
- **Active Turn Execution ID**：目前單次 agent 執行的識別，用於停止與存活檢查，掛在 thread 上。

Claude、Codex 與 OpenCode 的外部 protocol 可保留各自正式的 session/thread 欄位；進入 Aileron 後會立即正規化為 `agentResumeId`。`threads.active_turn_execution_id` 只代表目前執行，執行結束或錯誤時會清空。

## 名詞對照表

| 名詞 | Aileron 對應 | Terragon 對應 | 說明 |
|---|---|---|---|
| Platform Thread ID / Thread ID | `threads.id`、API path `/{thread_id}`、前端 selected thread | `thread.id`、`threadId` | 平台自己的任務或對話 ID。用於 URL、列表、查詢與 thread 操作。 |
| Thread | `threads` row | `thread` row | 使用者看到的一個任務或對話容器。 |
| Agent Resume ID | `thread_turn_executions.agent_resume_id`（逐次執行層級，透過 `ThreadExecutionMetadataResponse.agentResumeId` 對外）、`system_init.content.agentResumeId` | `threadChat.sessionId`、DB `session_id` | Agent CLI 用來接續對話的 ID，掛在單次執行（turn execution）而非整個 thread 上。Claude 原生叫 `session_id`；Codex 原生叫 `thread_id`，但進入第一方 domain 後都使用 resume 語意。 |
| Runtime Thread ID | Codex 原始 `thread_id`，進入 Aileron 後不作為公開名詞 | Codex 原始 `thread_id` | Codex CLI 原始欄位。平台內正規化為 `agentResumeId`，避免和平台 Thread ID 混淆。 |
| Active Turn Execution ID | `threads.active_turn_execution_id`（API 欄位 `activeTurnExecutionId`）、thread events `WS /api/v1/threads/events` | daemon 執行中的 agent process | 目前 thread 正在進行的單次執行識別，用於停止與存活檢查；執行事件寫回 thread messages，前端透過 thread events 重新讀取。執行結束或錯誤時清空。不是接續對話的 resume id。 |
| Thread Chat | Aileron 目前沒有獨立同名概念，thread 本身持有 agent、model、status 與訊息 | `threadChat` | Terragon 一個 platform thread 可有多個 chat 或 agent attempt；Aileron 目前是一個 thread 直接承載 runtime 狀態。 |
| Agent / Agentic Tool | `agentic_tool`：`claude`、`codex`、`opencode` | `agent`：`claudeCode`、`codex`、`opencode`、`gemini`、`amp` | 執行任務的 agent provider 或 tool。 |
| Model | `threads.model`、capabilities model | user message model / threadChat model selection | 實際送進 agent CLI 的模型。 |
| System Init | `thread_messages.type = system_init` | DB message `type: "meta"`、`subtype: "system-init"` | Agent runtime 啟動事件。Claude 會提供 session、tools、MCP metadata；Codex 只提供 runtime continuation id。 |
| Tool Call | `thread_messages.type = tool_call` | DB message `type: "tool-call"` | Agent 發起工具呼叫。 |
| Tool Result | `thread_messages.type = tool_result` | DB message `type: "tool-result"` | 工具執行結果。 |
| Agent Text | `thread_messages.type = agent_text` | DB message `type: "agent"` with text part | Agent 回覆文字。 |
| Thinking | `thread_messages.type = thinking` | DB message `type: "agent"` with thinking part | Agent thinking / reasoning 顯示資料。 |
| User Message | `thread_messages.type = user` | DB message `type: "user"` | 使用者輸入。 |
| Resume | `agent_resume_id` 在 adapter boundary 映射為 Claude `--resume`、Codex `resume` 或 OpenCode session protocol | `threadChat.sessionId` 傳給 Claude / Codex / OpenCode resume or session flag | 重新接續 agent runtime 對話。 |
| Platform Runtime | `workspace-runtime` | daemon / sandbox runtime | 啟動 agent、接收事件、正規化事件並寫回訊息的執行層。 |

## 正規化規則

### Claude Code

Claude Code 原始 init 事件使用 `session_id`：

```json
{
  "type": "system",
  "subtype": "init",
  "session_id": "claude-session-id"
}
```

Aileron 正規化為（`content` 一律包含五個欄位）：

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

Codex 原始 init 事件使用 `thread_id`：

```json
{
  "type": "thread.started",
  "thread_id": "codex-runtime-thread-id"
}
```

Aileron 正規化為（Codex 沒有提供的欄位維持空值，不補造 metadata）：

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

這裡的 `agentResumeId` 表示接續 Agent 對話的 resume handle，不是 Aileron 平台 `threads.id`。

## 使用準則

- 對外操作 Aileron thread 時使用 `threadId`。
- 接續 agent runtime 對話時使用 `agentResumeId` 或後端 `agent_resume_id`。
- 停止執行或做存活檢查時使用 Active Turn Execution ID（`threads.active_turn_execution_id` / `activeTurnExecutionId`）；它與接續對話的 resume id 是不同概念，且掛在 thread 上而非單次執行上。
- 不把 Codex 原始 `thread_id` 對外顯示為平台 `threadId`。
- 不補上 agent 原始事件沒有提供的 metadata；只做欄位正規化。
- 文件與 UI 文案使用 Agent Resume ID 描述接續 handle，不使用 Session 泛稱。
