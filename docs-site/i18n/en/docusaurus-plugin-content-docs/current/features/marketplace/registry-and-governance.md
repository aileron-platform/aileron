---
title: Registry and Governance
---

# Registry and Governance

Platform admins manage Managed Plugins in Application Center and manage the Managed Registry, Git identity, SSH keys, version control, and activity in Marketplace Settings.

The Managed Registry is a mutable working tree. Aileron does not create immutable release tags, commit or push automatically, or track external Marketplace Sources. Users decide when to perform Git operations, and the system provides no content rollback.

Import reads a Git or ZIP source only for the duration of the operation and copies selected content plus provenance into the Registry. The source is not a persistent product object and has no refresh, removal-impact, sync, or update state.

Activity is an append-only terminal audit with `import`, `install`, `copy`, or `delete` actions, not an authoritative installation lifecycle. CLI command results use the existing audit retention policy.
