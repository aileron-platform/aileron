# Manual Migration Notes

This directory contains SQL migration scripts that must be applied manually at deploy time.
The project follows a "fresh start" model per AGENTS.md rule 6 — no automated migrations are run.
Apply each script relevant to your deployment in order before restarting services.

## Pending cleanup: restructure-kb-directories

After deploying the `restructure-kb-directories` change, run the following cleanup steps on any
existing KB instances:

### 1. No database table to drop

`KnowledgeBaseLintReport` was file-based only (stored under `reports/lint/*.json`).
No SQL DROP TABLE is required.

### 2. Remove legacy directories from existing KB storage roots

For each knowledge base directory under `MANAGER_KNOWLEDGE_BASES_DIR/<kb_id>/`:

```sh
# Remove normalized layer
rm -rf <kb_root>/normalized

# Remove reports layer
rm -rf <kb_root>/reports

# Remove business-only wiki directories that are now template-controlled
# (only remove if they were created by default and not populated by users)
rm -rf <kb_root>/wiki/decisions
rm -rf <kb_root>/wiki/projects
```

> **Note**: Review contents before removing `wiki/decisions` and `wiki/projects`.
> If users have added content there, either keep the directories or migrate the files.

### 3. Seed missing `.aileron-kb/sources-metadata.json`

New KB initializations create this file automatically.
For existing KBs, seed it with an empty object:

```sh
echo '{}' > <kb_root>/.aileron-kb/sources-metadata.json
```
