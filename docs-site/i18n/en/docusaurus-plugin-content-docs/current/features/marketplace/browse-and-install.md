---
title: Browse and Install
---

# Browse and Install

Application Center lists only Managed Registry plugins. Cards show name, package format, version, Target Clients, and validation status. They do not show Draft, Published, Git Dirty, Remote Ready, Created/Imported, or Public/Private tags.

Plugin Installation hands the complete artifact to the compatible Target Client CLI. CLI command output and the terminal result are authoritative for installation and enablement; Aileron displays and audits that response without deriving separate client state. Codex loads newly installed capabilities in a new session.

User Copy reads the current Managed Registry working tree and applies an explicit `(packageFormat, targetClient)` projection into the client user scope under Workspace Runtime HOME. Preflight reports projected, skipped, conflicting, and blocking resources. Partial copy and overwrites still require confirmation. The result is a set of shared standalone Workspace resources, not an installed plugin, and it does not synchronize future updates.

Deleting a plugin does not perform remote cleanup, CLI uninstall, or User Copy cleanup. If the CLI can no longer find the plugin in its Git repository, a later install naturally returns the CLI error.
