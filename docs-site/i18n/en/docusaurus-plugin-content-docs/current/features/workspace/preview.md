---
title: Preview
---

# Preview

## Purpose and Entry Point

Enter Workspace Preview to inspect Web application output. The Canvas interaction surface is called Web Canvas.

## Roles and Allowed Operations

Entry requires `workspace.detail.read`; publishing and interaction remain constrained by Runtime availability, routes, and the Canvas contract.

## Core Concepts

Preview is the product feature name; Web Canvas is the surface; Canvas is the manifest, bridge, and technical contract identifier.

## Primary Workflow

Detect the manifest, select a route, and start preview. Publishing uses the fixed per-user resource flow.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

contentDir remains inside the managed root. Missing manifest, build failure, and invalid route produce diagnosable states.

## Source Basis

- `frontend/src/features/workspace/features/canvas/`
- `workspace-runtime/app/modules/canvas/`
- `workspace-runtime/app/modules/canvas/publishing.py`

## Related Architecture and APIs

- [protocol](/architecture/overview/canvas/protocol)
- [publishing](/architecture/overview/canvas/publishing)
- [runtime-api](/api/runtime-api)
