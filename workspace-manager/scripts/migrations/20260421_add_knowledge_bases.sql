-- Add knowledge base metadata, sharing, and workspace attachment tables.
ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS runtime_mounted_kb_signature text;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id varchar(64) PRIMARY KEY,
    slug varchar(255) NOT NULL,
    name varchar(255) NOT NULL,
    description text,
    owner_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_size_bytes integer NOT NULL DEFAULT 0,
    quota_bytes integer,
    tombstoned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_bases_owner_slug_unique UNIQUE (owner_id, slug)
);

CREATE TABLE IF NOT EXISTS knowledge_base_shares (
    id varchar(64) PRIMARY KEY,
    kb_id varchar(64) NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role varchar(32) NOT NULL CHECK (role IN ('viewer', 'editor', 'manager')),
    granted_by_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_base_shares_kb_user_unique UNIQUE (kb_id, user_id)
);

CREATE TABLE IF NOT EXISTS workspace_knowledge_base_attachments (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kb_id varchar(64) NOT NULL REFERENCES knowledge_bases(id) ON DELETE RESTRICT,
    mount_alias varchar(255) NOT NULL,
    mode varchar(16) NOT NULL CHECK (mode IN ('rw', 'ro')),
    attached_by_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT workspace_kb_attachments_workspace_kb_unique UNIQUE (workspace_id, kb_id),
    CONSTRAINT workspace_kb_attachments_workspace_alias_unique UNIQUE (workspace_id, mount_alias)
);
