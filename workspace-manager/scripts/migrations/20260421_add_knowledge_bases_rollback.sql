-- Roll back knowledge base metadata, sharing, and workspace attachment tables.
DROP TABLE IF EXISTS workspace_knowledge_base_attachments;
DROP TABLE IF EXISTS knowledge_base_shares;
DROP TABLE IF EXISTS knowledge_bases;

ALTER TABLE workspaces
    DROP COLUMN IF EXISTS runtime_mounted_kb_signature;
