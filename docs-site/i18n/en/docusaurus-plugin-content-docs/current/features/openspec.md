---
sidebar_position: 3
title: OpenSpec Workflows
---

# OpenSpec Workflows

## Overview

OpenSpec is integrated into Aileron as a built-in workspace capability, not just a side command or an external documentation flow. It brings proposal writing, design capture, task breakdown, and implementation progress into the same workspace workflow.

In Aileron, OpenSpec means:

- browsing `openspec/` documents directly inside the workspace
- launching workflow actions from the chat composer
- relying on a built-in OpenSpec CLI foundation inside the runtime

## Built-In Capabilities

### OpenSpec Browser

The `OpenSpec` section in the workspace sidebar reads the project's `openspec/` tree directly and helps you navigate:

- `proposal.md`
- `design.md`
- `tasks.md`
- each capability's `spec.md`

This turns OpenSpec from a loose set of Markdown files into a first-class workspace surface with navigation, status, and context.

### OpenSpec Actions

The chat composer includes an `OpenSpec Actions` entry point that inserts workflow drafts for the next step, such as:

- `propose`
- `explore`
- `apply`
- `archive`
- `continue`
- `verify`

These actions are modeled as workflow-aware actions with grouping, availability, and recommendation states rather than as generic slash commands.

### Runtime CLI Foundation

`workspace-runtime` includes the OpenSpec CLI directly so every workspace can execute OpenSpec workflows in a consistent environment without requiring additional project-level installation steps.

## Why It Matters

OpenSpec in Aileron is not just about making the docs visible. It connects the full workflow:

1. inspect the current change and spec state
2. understand whether the next step is propose, explore, apply, or archive
3. launch that action directly from the chat composer
4. continue editing and tracking the work inside the workspace

## Current Status

OpenSpec is already a built-in capability with workspace navigation, chat composer actions, and runtime CLI integration. Recommendation logic, state awareness, and richer workflow behaviors will keep improving over time.

## Roadmap

- improve change-aware and profile-aware recommendations
- expand workflow consistency across more actions
- integrate more naturally with multi-agent workflows
- connect more deeply with team collaboration and worktree-oriented development flows
