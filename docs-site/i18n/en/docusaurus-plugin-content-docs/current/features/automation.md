---
sidebar_position: 3
title: Automation Tasks
---

# Automation Tasks

## Overview

The Automation feature lets you schedule agent workflows on a timer, enabling automated AI workflows. Today, Claude Code has the most complete automation support, while broader agent coverage is still being expanded.

## Tech Stack

| Component | Description |
|-----------|-------------|
| Celery | Distributed task queue |
| Redis | Broker + backend |
| Celery Beat | Scheduled tasks |
| Flower | Task monitoring UI |

## Creating an Automation Task

Create tasks from the frontend Automation Dashboard:

1. Pick a target workspace
2. Set a cron expression (schedule)
3. Enter an agent prompt, workflow draft, or execution command
4. Choose the permission mode
5. Save and enable

## Cron Expressions

Standard cron format:

```
# min hour day month weekday
0 9 * * 1-5    # 9am every weekday
*/30 * * * *   # Every 30 minutes
0 0 * * 0      # Midnight every Sunday
```

## Task Monitoring

### Flower UI

```
http://localhost:5555
```

Flower provides:
- Real-time task execution state
- Execution history
- Worker status
- Task retry

### API

```bash
# List automation tasks
GET /api/v1/automation/tasks

# List runs for a specific task
GET /api/v1/automation/tasks/{task_id}/runs

# Manually trigger a task
POST /api/v1/automation/tasks/{task_id}/trigger
```

## Use Cases

- **Daily code review**: schedule Claude to review newly committed code
- **Documentation updates**: automatically update API docs or README
- **Test runs**: periodically run the test suite and report results
- **Code refactoring**: periodically optimize a specific module
- **Changelog generation**: organize git log into release notes

## Current Status

Automation currently works best with Claude Code workflows. As the platform fills out OpenCode, Gemini, and Codex integrations, more cross-agent automation scenarios will be added over time.
