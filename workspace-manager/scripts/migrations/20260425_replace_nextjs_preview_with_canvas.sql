ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS canvas_container_id text,
    ADD COLUMN IF NOT EXISTS canvas_status text DEFAULT 'stopped',
    ADD COLUMN IF NOT EXISTS canvas_created_at timestamp with time zone,
    ADD COLUMN IF NOT EXISTS canvas_last_seen timestamp with time zone,
    ADD COLUMN IF NOT EXISTS canvas_internal_url text,
    ADD COLUMN IF NOT EXISTS canvas_external_url text,
    ADD COLUMN IF NOT EXISTS canvas_internal_port integer DEFAULT 3003,
    ADD COLUMN IF NOT EXISTS canvas_external_port integer,
    ADD COLUMN IF NOT EXISTS canvas_api_internal_port integer DEFAULT 3013,
    ADD COLUMN IF NOT EXISTS canvas_api_external_port integer,
    ADD COLUMN IF NOT EXISTS canvas_type text DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS canvas_manifest_status text DEFAULT 'missing',
    ADD COLUMN IF NOT EXISTS canvas_last_sync_at timestamp with time zone,
    ADD COLUMN IF NOT EXISTS canvas_last_reset_at timestamp with time zone;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'workspaces'
          AND column_name = 'nextjs_container_id'
          AND table_schema = ANY (current_schemas(false))
    ) THEN
        UPDATE workspaces
        SET
            canvas_container_id = COALESCE(canvas_container_id, nextjs_container_id),
            canvas_status = COALESCE(NULLIF(canvas_status, 'stopped'), nextjs_status, 'stopped'),
            canvas_created_at = COALESCE(canvas_created_at, nextjs_created_at),
            canvas_last_seen = COALESCE(canvas_last_seen, nextjs_last_seen),
            canvas_internal_url = COALESCE(canvas_internal_url, nextjs_internal_url),
            canvas_external_url = COALESCE(canvas_external_url, nextjs_external_url),
            canvas_internal_port = COALESCE(canvas_internal_port, nextjs_internal_port, 3003),
            canvas_external_port = COALESCE(canvas_external_port, nextjs_external_port),
            canvas_api_internal_port = COALESCE(canvas_api_internal_port, nextjs_api_internal_port, 3013),
            canvas_api_external_port = COALESCE(canvas_api_external_port, nextjs_api_external_port),
            canvas_type = COALESCE(canvas_type, 'default'),
            canvas_manifest_status = COALESCE(canvas_manifest_status, 'missing');
    ELSE
        UPDATE workspaces
        SET
            canvas_status = COALESCE(canvas_status, 'stopped'),
            canvas_internal_port = COALESCE(canvas_internal_port, 3003),
            canvas_api_internal_port = COALESCE(canvas_api_internal_port, 3013),
            canvas_type = COALESCE(canvas_type, 'default'),
            canvas_manifest_status = COALESCE(canvas_manifest_status, 'missing');
    END IF;
END $$;

ALTER TABLE workspaces
    DROP CONSTRAINT IF EXISTS workspaces_nextjs_status_check,
    DROP CONSTRAINT IF EXISTS workspaces_canvas_status_check,
    DROP CONSTRAINT IF EXISTS workspaces_canvas_type_check,
    DROP CONSTRAINT IF EXISTS workspaces_canvas_manifest_status_check;

ALTER TABLE workspaces
    ADD CONSTRAINT workspaces_canvas_status_check
        CHECK (canvas_status IN ('stopped', 'starting', 'running', 'error', 'restarting')),
    ADD CONSTRAINT workspaces_canvas_type_check
        CHECK (canvas_type IN ('html', 'nextjs', 'default')),
    ADD CONSTRAINT workspaces_canvas_manifest_status_check
        CHECK (canvas_manifest_status IN ('missing', 'valid', 'invalid'));

ALTER TABLE workspaces
    DROP COLUMN IF EXISTS web_preview_internal_port,
    DROP COLUMN IF EXISTS web_preview_external_port,
    DROP COLUMN IF EXISTS web_preview_internal_url,
    DROP COLUMN IF EXISTS web_preview_external_url,
    DROP COLUMN IF EXISTS nextjs_container_id,
    DROP COLUMN IF EXISTS nextjs_status,
    DROP COLUMN IF EXISTS nextjs_created_at,
    DROP COLUMN IF EXISTS nextjs_last_seen,
    DROP COLUMN IF EXISTS nextjs_internal_url,
    DROP COLUMN IF EXISTS nextjs_external_url,
    DROP COLUMN IF EXISTS nextjs_internal_port,
    DROP COLUMN IF EXISTS nextjs_external_port,
    DROP COLUMN IF EXISTS nextjs_api_internal_port,
    DROP COLUMN IF EXISTS nextjs_api_external_port;

COMMENT ON COLUMN workspaces.canvas_container_id IS 'Canvas 容器 ID';
COMMENT ON COLUMN workspaces.canvas_status IS 'Canvas 容器運行狀態';
COMMENT ON COLUMN workspaces.canvas_created_at IS 'Canvas 容器建立時間';
COMMENT ON COLUMN workspaces.canvas_last_seen IS 'Canvas 容器最後活動時間';
COMMENT ON COLUMN workspaces.canvas_internal_url IS 'Canvas 容器內部通信 URL';
COMMENT ON COLUMN workspaces.canvas_external_url IS 'Canvas 容器外部訪問 URL';
COMMENT ON COLUMN workspaces.canvas_internal_port IS 'Canvas render server 內部端口（預設 3003）';
COMMENT ON COLUMN workspaces.canvas_external_port IS 'Canvas render server 外部映射端口';
COMMENT ON COLUMN workspaces.canvas_api_internal_port IS 'Canvas 管理 API 內部端口（預設 3013）';
COMMENT ON COLUMN workspaces.canvas_api_external_port IS 'Canvas 管理 API 外部映射端口';
COMMENT ON COLUMN workspaces.canvas_type IS 'Canvas 最近偵測類型（html / nextjs / default）';
COMMENT ON COLUMN workspaces.canvas_manifest_status IS 'Canvas manifest 狀態（missing / valid / invalid）';
COMMENT ON COLUMN workspaces.canvas_last_sync_at IS 'Canvas 最近同步時間';
COMMENT ON COLUMN workspaces.canvas_last_reset_at IS 'Canvas 最近 reset 時間';
