---
sidebar_position: 5
title: Knowledge Base
---

# Knowledge Base

Knowledge Base stores reusable team knowledge, project guidance, runbooks, and indexed wiki content that can be mounted into workspaces. It is managed by Workspace Manager, shared through roles, and mounted into runtime containers when a workspace attachment is configured.

## Core Concepts

| Concept | Description |
|---------|-------------|
| Knowledge Base | Independent knowledge repository with files, wiki content, metadata, and maintenance state |
| Owner | Creator with full management access |
| Share | Role grant for another user |
| Attachment | Workspace mount configuration |
| Mount alias | Runtime mount name, exposed as `/knowledge/<alias>` |
| Mode | `ro` for read-only, `rw` for read/write |

## Storage

Docker development stores knowledge bases under:

```text
./data/knowledge-bases/<kbId>
```

Workspace Manager reads the same data through `MANAGER_KNOWLEDGE_BASES_DIR=/host/knowledge-bases`. Kubernetes deployments use the Helm `kubernetes.knowledgeBases.*` values to create a shared PVC, and workspace-operator mounts attached knowledge bases into runtime pods.

Typical layout:

```text
<kbId>/
├── AGENTS.md
├── purpose.md
├── schema.md
├── wiki/
│   ├── index.md
│   ├── overview.md
│   └── log.md
└── .aileron-kb/
    ├── ingest-cache.json
    ├── ingest-queue.json
    ├── graph-cache.json
    ├── reviews.json
    ├── sources-metadata.json
    └── wiki-index.json
```

## Content and Metadata

| Path | Purpose |
|------|---------|
| `AGENTS.md` | Agent instructions and boundaries for this knowledge base |
| `purpose.md` | Scope, intent, and maintenance rules |
| `schema.md` | Content taxonomy and naming rules |
| `wiki/` | Main knowledge content for humans and agents |
| `.aileron-kb/ingest-cache.json` | Ingestion cache |
| `.aileron-kb/ingest-queue.json` | Pending ingestion queue |
| `.aileron-kb/graph-cache.json` | Graph or index cache |
| `.aileron-kb/reviews.json` | Review items |
| `.aileron-kb/sources-metadata.json` | Source file metadata |
| `.aileron-kb/wiki-index.json` | Wiki page index |

## Workspace Attachments

An attached knowledge base appears inside runtime at:

```text
/knowledge/<mountAlias>
```

Common flow:

1. Create a knowledge base.
2. Upload or edit wiki and source files.
3. Attach the knowledge base to a workspace with an alias and mode.
4. Restart or reconcile runtime so the mount is applied.
5. Use `/knowledge/<alias>` from terminal sessions or agents.

## API Summary

Workspace Manager exposes:

| Type | Path |
|------|------|
| Knowledge Base management | `/api/v1/knowledge-bases` |
| Workspace attachments | `/api/v1/workspaces/{workspace_id}/knowledge-bases` |

See [Manager API](/api/manager-api#knowledge-base) for endpoint details.
