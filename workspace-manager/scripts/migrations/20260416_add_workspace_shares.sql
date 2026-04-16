-- Add workspace_shares table for per-workspace access control.
CREATE TABLE IF NOT EXISTS workspace_shares (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    shared_with_user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role varchar(32) NOT NULL CHECK (role IN ('viewer', 'editor', 'manager')),
    granted_by_user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT workspace_shares_workspace_user_unique UNIQUE (workspace_id, shared_with_user_id)
);
