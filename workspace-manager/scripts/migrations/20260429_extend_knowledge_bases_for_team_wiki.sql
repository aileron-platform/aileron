-- Extend knowledge bases with Team Wiki status and optional Git metadata.
ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS version_control_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS git_lfs_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS git_default_branch varchar(255) NOT NULL DEFAULT 'main',
    ADD COLUMN IF NOT EXISTS git_last_commit_sha varchar(64),
    ADD COLUMN IF NOT EXISTS wiki_initialized_at timestamp with time zone,
    ADD COLUMN IF NOT EXISTS last_indexed_at timestamp with time zone,
    ADD COLUMN IF NOT EXISTS last_index_status varchar(32),
    ADD COLUMN IF NOT EXISTS last_index_error text;
