---
sidebar_position: 2
title: Claude Code Integration
---

# Claude Code Integration

## Overview

Aileron currently provides its most complete agent experience through Claude Code. This gives teams a ready-to-use way to run Claude Code agents directly from the browser UI for code generation, analysis, refactoring, and day-to-day development work.

Aileron is not limited to Claude Code, though. The platform is evolving toward a broader multi-agent architecture, with OpenCode, Gemini, and Codex support being expanded over time. For now, **Claude Code remains the most complete and production-ready integration in the product**.

The goal is not only to integrate a powerful agent, but to make that agent usable inside governed, repeatable, enterprise-ready workspaces.

## Agent Support Status

| Agent | Status | Notes |
|-------|--------|-------|
| Claude Code | Fully supported | Most complete today: chat, settings, automation, and OpenSpec workflow integration |
| Gemini | Partial support | Settings and foundational integration exist; end-to-end support is still expanding |
| OpenCode | Partial support | Settings and foundational integration exist; more workflow and execution support is planned |
| Codex | Partial support | Settings and foundational integration exist; more execution and governance support is planned |

## Features

### Agent Session

Each Claude Code invocation creates an Agent Session:

```
Frontend Chat Panel
  │  Create session
  ▼
Workspace Runtime
  │  Run claude CLI
  │  Stream output (stdout/stderr)
  ▼
WebSocket → Frontend
  │  Real-time display of thinking / tool use / output
```

### Supported Permission Modes

| Mode | Description |
|------|-------------|
| `default` | Standard mode; tool calls require confirmation |
| `acceptEdits` | Auto-accept file edits |
| `dontAsk` | Never prompt; auto-execute all operations |
| `auto` | Fully automated mode |

### Claude Code Settings Management

The workspace settings page lets you manage:

- **Model selection**: choose the Claude model
- **Hooks**: configure custom pre/post hook commands
- **MCP servers**: configure MCP server connections
- **Sub-agents**: Claude Code sub-agent settings
- **Slash commands**: custom `/` commands
- **Environment variables**: inject `ANTHROPIC_API_KEY` and other runtime env vars

### Environment Variable Injection

The Claude API key and other sensitive settings are configured dynamically via the frontend "Environment Variables" page and injected into the workspace runtime container. This helps platform teams avoid baking environment-specific secrets into images or local setup steps.

## Chat Panel

The frontend Chat Panel provides:

- **Streaming output**: real-time display of Claude's thinking process and tool calls
- **Tool-call visualization**: shows file read/write, bash execution, and other operations
- **Permission mode toggle**: switch authorization modes mid-conversation
- **Session management**: view session history, resume, or start new sessions

## WebSocket Agent Session

```javascript
// Connect to Agent Session WebSocket
const ws = new WebSocket(
  `ws://localhost:3002/api/v1/ws/agent-sessions/${sessionId}`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: 'thinking' | 'tool_use' | 'tool_result' | 'text' | 'done' | 'error'
};
```

## Automation Integration

Claude Code can be scheduled to run via the Automation feature — see [Automation Tasks](./automation). Automation is also most complete with Claude Code today, while broader multi-agent scheduling support continues to evolve.
