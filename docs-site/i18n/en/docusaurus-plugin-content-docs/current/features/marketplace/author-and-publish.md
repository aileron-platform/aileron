---
title: Create and Import
---

# Create and Import

Platform admins create a plugin by choosing its package format, compatible Target Client, package ID, display name, and version. Creation writes directly to the Managed Registry working tree, so the plugin can be edited, installed, or copied without a separate publishing step.

`Import Plugin` accepts a Git repository or ZIP archive. Manager rescans the source on the server, lists discovered plugins and formats, and copies only the candidates the user selects.

Package IDs are unique across Application Center. A duplicate import requires explicit Replace confirmation. The same version may be overwritten and Aileron keeps no rollback. To update upstream content, run Import again and Replace; there is no separate Re-import or automatic synchronization.

Application Center does not run Git commit, tag, or push automatically. User Copy can use working-tree content immediately. CLI installation resolves content through its configured Git repository, so uncommitted or unpushed content is naturally unavailable to the remote CLI flow.
