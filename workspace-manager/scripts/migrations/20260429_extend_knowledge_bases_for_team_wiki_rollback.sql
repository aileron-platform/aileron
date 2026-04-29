-- Roll back Team Wiki status and optional Git metadata columns.
ALTER TABLE knowledge_bases
    DROP COLUMN IF EXISTS last_index_error,
    DROP COLUMN IF EXISTS last_index_status,
    DROP COLUMN IF EXISTS last_indexed_at,
    DROP COLUMN IF EXISTS wiki_initialized_at,
    DROP COLUMN IF EXISTS git_last_commit_sha,
    DROP COLUMN IF EXISTS git_default_branch,
    DROP COLUMN IF EXISTS git_lfs_enabled,
    DROP COLUMN IF EXISTS version_control_enabled;
