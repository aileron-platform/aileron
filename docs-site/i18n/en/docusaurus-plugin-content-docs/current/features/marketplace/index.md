---
title: Application Center
---

# Application Center

Application Center shows only plugins in the Aileron Managed Registry working tree. Platform admins can create them directly or import them from a Git repository or ZIP archive. Aileron does not register or track external Marketplace catalogs.

A created or imported plugin is immediately available. There is no Draft, Publish, Sync, Rollback, or separate Re-import state. Importing an existing package ID asks the user to choose a version and explicitly confirm Replace.

Package format is immutable and controls editor capabilities:

- `claude-native` supports Claude Code native resources, including Output Styles.
- `codex-native` supports Codex native resources without Output Styles.
- `agent-plugin/1.0.0` initially exposes only Basic, MCP, Skills, and Files.

Members and admins can browse, export, and install. Creating, importing, editing, and deleting require Platform Admin.

## Related pages

- [Browse and Install](./browse-and-install)
- [Create and Import](./author-and-publish)
- [Registry and Governance](./registry-and-governance)
- [Manager API](/api/manager-api)
