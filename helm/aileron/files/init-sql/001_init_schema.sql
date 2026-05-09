-- Aileron Database Initialization Script
-- Regenerated from docs/database/schema.md

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id varchar(128) PRIMARY KEY,
    username varchar(255) UNIQUE NOT NULL,
    email varchar(255) UNIQUE,
    keycloak_id varchar(255) UNIQUE,
    first_name varchar(255),
    last_name varchar(255),
    display_name varchar(255),
    roles jsonb NOT NULL DEFAULT '[]',
    avatar_url text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS roles jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON TABLE users IS '用戶基本資料表';
COMMENT ON COLUMN users.id IS '用戶唯一識別碼';
COMMENT ON COLUMN users.username IS '用戶名稱，必須唯一';
COMMENT ON COLUMN users.email IS '電子郵件地址，唯一';
COMMENT ON COLUMN users.display_name IS '用戶顯示名稱';
COMMENT ON COLUMN users.avatar_url IS '用戶頭像圖片 URL';
COMMENT ON COLUMN users.keycloak_id IS 'Keycloak 用戶 ID (sub claim)，用於關聯 Keycloak 用戶';
COMMENT ON COLUMN users.first_name IS '用戶名字';
COMMENT ON COLUMN users.last_name IS '用戶姓氏';
COMMENT ON COLUMN users.roles IS '用戶角色列表（JSONB 格式），存儲 Keycloak roles 和系統權限';
COMMENT ON COLUMN users.is_active IS '帳號是否啟用狀態';
COMMENT ON COLUMN users.created_at IS '帳號建立時間';
COMMENT ON COLUMN users.updated_at IS '帳號最後更新時間';

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_keycloak_id
ON users(keycloak_id) WHERE keycloak_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_roles
ON users USING GIN (roles);

-- Table: user_settings
CREATE TABLE IF NOT EXISTS user_settings (
    id varchar(128) PRIMARY KEY,
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    claude_auth_key text,
    claude_selected_model varchar(64) DEFAULT 'claude-sonnet-4' NOT NULL,
    claude_selected_provider varchar(32) DEFAULT 'anthropic' NOT NULL,
    git_user_name varchar(255),
    git_user_email varchar(255),
    git_signing_key text,
    ssh_private_key text,
    ssh_public_key text,
    ssh_fingerprint varchar(128),
    ssh_last_rotated_at timestamp with time zone,
    general_settings jsonb DEFAULT '{}'::jsonb,
    additional_settings jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE user_settings IS '用戶個人設定表';
COMMENT ON COLUMN user_settings.id IS '設定唯一識別碼';
COMMENT ON COLUMN user_settings.user_id IS '所屬用戶ID';
COMMENT ON COLUMN user_settings.claude_auth_key IS 'Claude API 認證金鑰';
COMMENT ON COLUMN user_settings.claude_selected_model IS '用戶選擇的 Claude 模型';
COMMENT ON COLUMN user_settings.claude_selected_provider IS '用戶選擇的 AI 服務提供商';
COMMENT ON COLUMN user_settings.git_user_name IS 'Git 配置的用戶名稱';
COMMENT ON COLUMN user_settings.git_user_email IS 'Git 配置的用戶郵箱';
COMMENT ON COLUMN user_settings.ssh_private_key IS 'SSH 私鑰內容';
COMMENT ON COLUMN user_settings.ssh_public_key IS 'SSH 公鑰內容';
COMMENT ON COLUMN user_settings.general_settings IS '一般設定（JSON格式）';
COMMENT ON COLUMN user_settings.additional_settings IS '其他擴展設定（JSON格式，包含 Claude Code OAuth tokens）';

-- Table: model_configs
CREATE TABLE IF NOT EXISTS model_configs (
    id varchar(128) PRIMARY KEY,
    model_key varchar(64) UNIQUE NOT NULL,
    model_name varchar(255) NOT NULL,
    anthropic_model_id varchar(255),
    aws_bedrock_model_id varchar(255),
    gcp_vertex_model_id varchar(255),
    is_active boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE model_configs IS 'AI 模型配置表';
COMMENT ON COLUMN model_configs.id IS '配置唯一識別碼';
COMMENT ON COLUMN model_configs.model_key IS '模型內部鍵值';
COMMENT ON COLUMN model_configs.model_name IS '模型顯示名稱';
COMMENT ON COLUMN model_configs.anthropic_model_id IS 'Anthropic 平台的模型 ID';
COMMENT ON COLUMN model_configs.aws_bedrock_model_id IS 'AWS Bedrock 平台的模型 ID';
COMMENT ON COLUMN model_configs.gcp_vertex_model_id IS 'GCP Vertex AI 平台的模型 ID';
COMMENT ON COLUMN model_configs.is_active IS '模型是否啟用';
COMMENT ON COLUMN model_configs.sort_order IS '顯示排序順序';

-- Table: workspaces
CREATE TABLE IF NOT EXISTS workspaces (
    id varchar(64) PRIMARY KEY,
    owner_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    git_url text,
    branch text DEFAULT 'main',
    runtime text DEFAULT 'universal',
    env_vars jsonb DEFAULT '[]'::jsonb,
    runtime_resources jsonb,
    acp_cli_args jsonb DEFAULT '[]'::jsonb,
    setup_script text,
    runtime_container_id text,
    runtime_internal_url text,
    runtime_external_url text,
    runtime_internal_port integer DEFAULT 3002,
    runtime_external_port integer,
    runtime_status text DEFAULT 'stopped' CHECK (runtime_status IN ('stopped', 'starting', 'running', 'error', 'deleting', 'restarting')),
    runtime_created_at timestamp with time zone,
    runtime_last_seen timestamp with time zone,
    canvas_container_id text,
    canvas_status text DEFAULT 'stopped' CHECK (canvas_status IN ('stopped', 'starting', 'running', 'error', 'restarting')),
    canvas_created_at timestamp with time zone,
    canvas_last_seen timestamp with time zone,
    canvas_internal_url text,
    canvas_external_url text,
    canvas_internal_port integer DEFAULT 3003,
    canvas_external_port integer,
    canvas_api_internal_port integer DEFAULT 3013,
    canvas_api_external_port integer,
    canvas_type text DEFAULT 'default' CHECK (canvas_type IN ('html', 'nextjs', 'default')),
    canvas_manifest_status text DEFAULT 'missing' CHECK (canvas_manifest_status IN ('missing', 'valid', 'invalid')),
    canvas_last_sync_at timestamp with time zone,
    canvas_last_reset_at timestamp with time zone,
    terminal_external_port integer,
    terminal_external_url text,
    provisioner text DEFAULT 'docker' CHECK (provisioner IN ('docker', 'kubernetes')),
    target_namespace text,
    workspace_firewall_network_access_enabled boolean DEFAULT true,
    workspace_firewall_domain_access_mode text DEFAULT 'all' CHECK (workspace_firewall_domain_access_mode IN ('all', 'specific')),
    workspace_firewall_allowed_domains jsonb DEFAULT '[]'::jsonb,
    browser_firewall_network_access_enabled boolean DEFAULT true,
    browser_firewall_domain_access_mode text DEFAULT 'all' CHECK (browser_firewall_domain_access_mode IN ('all', 'specific')),
    browser_firewall_allowed_domains jsonb DEFAULT '[]'::jsonb,
    port_mappings jsonb DEFAULT '[]'::jsonb,
    active_claude_session_id varchar(128),
    preferred_cli varchar(32) DEFAULT 'claude-code',
    cli_type varchar(32) DEFAULT 'claude-code' NOT NULL CHECK (cli_type IN ('claude-code','codex','gemini')),

    fallback_enabled boolean DEFAULT true,
    workspace_path text DEFAULT '/workspace',
    worktree_subdir text NOT NULL DEFAULT '.worktrees',
    runtime_mounted_kb_signature text,

    -- Browser container fields
    browser_container_id text,
    browser_status text DEFAULT 'stopped' CHECK (browser_status IN ('stopped', 'starting', 'running', 'error', 'restarting')),
    browser_created_at timestamp with time zone,
    browser_last_seen timestamp with time zone,

    -- Browser WebRTC (neko) fields
    browser_webrtc_internal_url text,
    browser_webrtc_external_url text,
    browser_webrtc_internal_port integer DEFAULT 6080,
    browser_webrtc_external_port integer,

    -- Browser CDP fields
    browser_cdp_internal_port integer DEFAULT 9223,
    browser_cdp_external_port integer,

    -- Workspace settings
    language varchar(10) DEFAULT 'zh-TW' CHECK (language IN ('en', 'zh-TW')),
    timezone varchar(64) DEFAULT 'Asia/Taipei',
    default_shell varchar(32) DEFAULT 'bash',
    auto_start boolean DEFAULT true,

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS runtime_created_at timestamp with time zone,
    ADD COLUMN IF NOT EXISTS runtime_resources jsonb,
    ADD COLUMN IF NOT EXISTS runtime_mounted_kb_signature text,
    ADD COLUMN IF NOT EXISTS worktree_subdir text NOT NULL DEFAULT '.worktrees',
    ADD COLUMN IF NOT EXISTS language varchar(10) DEFAULT 'zh-TW',
    ADD COLUMN IF NOT EXISTS timezone varchar(64) DEFAULT 'Asia/Taipei',
    ADD COLUMN IF NOT EXISTS default_shell varchar(32) DEFAULT 'bash',
    ADD COLUMN IF NOT EXISTS auto_start boolean DEFAULT true;

COMMENT ON TABLE workspaces IS '開發工作區配置表';
COMMENT ON COLUMN workspaces.id IS '工作區唯一識別碼';
COMMENT ON COLUMN workspaces.owner_id IS '工作區擁有者用戶 ID';
COMMENT ON COLUMN workspaces.name IS '工作區名稱';
COMMENT ON COLUMN workspaces.description IS '工作區描述';
COMMENT ON COLUMN workspaces.git_url IS 'Git 儲存庫 URL';
COMMENT ON COLUMN workspaces.branch IS 'Git 分支名稱';
COMMENT ON COLUMN workspaces.runtime IS '運行時環境類型';
COMMENT ON COLUMN workspaces.env_vars IS '環境變數配置（JSON陣列）';
COMMENT ON COLUMN workspaces.runtime_resources IS 'Kubernetes runtime 資源覆寫配置';
COMMENT ON COLUMN workspaces.setup_script IS '工作區初始化腳本';
COMMENT ON COLUMN workspaces.runtime_container_id IS '運行時容器 ID';
COMMENT ON COLUMN workspaces.runtime_internal_url IS '容器內部通信 URL';
COMMENT ON COLUMN workspaces.runtime_external_url IS '外部訪問 URL';
COMMENT ON COLUMN workspaces.runtime_internal_port IS '容器內部監聽端口';
COMMENT ON COLUMN workspaces.runtime_external_port IS '主機映射的外部端口';
COMMENT ON COLUMN workspaces.runtime_status IS '容器運行狀態';
COMMENT ON COLUMN workspaces.runtime_created_at IS '容器建立時間';
COMMENT ON COLUMN workspaces.runtime_last_seen IS '容器最後活動時間';
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
COMMENT ON COLUMN workspaces.terminal_external_port IS 'Terminal 服務外部映射端口';
COMMENT ON COLUMN workspaces.terminal_external_url IS 'Terminal 服務外部訪問 URL';
COMMENT ON COLUMN workspaces.provisioner IS '工作區佈建模式（docker / kubernetes）';
COMMENT ON COLUMN workspaces.target_namespace IS 'Kubernetes 模式下目標部署 namespace';
COMMENT ON COLUMN workspaces.workspace_firewall_network_access_enabled IS 'workspace 組網路存取權限開關';
COMMENT ON COLUMN workspaces.workspace_firewall_domain_access_mode IS 'workspace 組允許網域模式（all: 全部, specific: 指定網域）';
COMMENT ON COLUMN workspaces.workspace_firewall_allowed_domains IS 'workspace 組允許的網域列表（JSON陣列）';
COMMENT ON COLUMN workspaces.browser_firewall_network_access_enabled IS 'browser 組網路存取權限開關';
COMMENT ON COLUMN workspaces.browser_firewall_domain_access_mode IS 'browser 組允許網域模式（all: 全部, specific: 指定網域）';
COMMENT ON COLUMN workspaces.browser_firewall_allowed_domains IS 'browser 組允許的網域列表（JSON陣列）';
COMMENT ON COLUMN workspaces.port_mappings IS '端口映射配置（JSON陣列）';
COMMENT ON COLUMN workspaces.active_claude_session_id IS '當前活躍的 Claude 對話會話 ID';
COMMENT ON COLUMN workspaces.preferred_cli IS '偏好的命令行介面';
COMMENT ON COLUMN workspaces.cli_type IS '工作區的 CLI 類型（claude-code / codex / gemini）';
COMMENT ON COLUMN workspaces.fallback_enabled IS '是否啟用 AI 模型備援機制';
COMMENT ON COLUMN workspaces.workspace_path IS '工作區在容器中的路徑';
COMMENT ON COLUMN workspaces.runtime_mounted_kb_signature IS 'Runtime mounted knowledge base signature';
COMMENT ON COLUMN workspaces.browser_container_id IS 'Browser 容器 ID';
COMMENT ON COLUMN workspaces.browser_status IS 'Browser 容器運行狀態';
COMMENT ON COLUMN workspaces.browser_created_at IS 'Browser 容器建立時間';
COMMENT ON COLUMN workspaces.browser_last_seen IS 'Browser 容器最後活動時間';
COMMENT ON COLUMN workspaces.browser_webrtc_internal_url IS 'Browser WebRTC (neko) 容器內部通信 URL';
COMMENT ON COLUMN workspaces.browser_webrtc_external_url IS 'Browser WebRTC (neko) 外部訪問 URL';
COMMENT ON COLUMN workspaces.browser_webrtc_internal_port IS 'Browser WebRTC (neko) 內部端口（預設 6080）';
COMMENT ON COLUMN workspaces.browser_webrtc_external_port IS 'Browser WebRTC (neko) 主機映射端口';
COMMENT ON COLUMN workspaces.browser_cdp_internal_port IS 'Browser CDP 內部端口（預設 9223）';
COMMENT ON COLUMN workspaces.browser_cdp_external_port IS 'Browser CDP 外部映射端口';
-- Table: workspace_shares
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

COMMENT ON TABLE workspace_shares IS '工作區分享授權表';
COMMENT ON COLUMN workspace_shares.id IS '分享授權唯一識別碼';
COMMENT ON COLUMN workspace_shares.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN workspace_shares.shared_with_user_id IS '被分享的使用者 ID';
COMMENT ON COLUMN workspace_shares.role IS '工作區分享角色（viewer / editor / manager）';
COMMENT ON COLUMN workspace_shares.granted_by_user_id IS '授權分享的使用者 ID';
COMMENT ON COLUMN workspace_shares.created_at IS '分享建立時間';
COMMENT ON COLUMN workspace_shares.updated_at IS '分享最後更新時間';

-- Table: knowledge_bases
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id varchar(64) PRIMARY KEY,
    slug varchar(255) NOT NULL,
    name varchar(255) NOT NULL,
    description text,
    template_id varchar(64) DEFAULT 'general' NOT NULL,
    owner_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_size_bytes integer NOT NULL DEFAULT 0,
    quota_bytes integer,
    version_control_enabled boolean DEFAULT false NOT NULL,
    git_lfs_enabled boolean DEFAULT false NOT NULL,
    git_default_branch varchar(255) DEFAULT 'main' NOT NULL,
    git_last_commit_sha varchar(64),
    wiki_initialized_at timestamp with time zone,
    last_indexed_at timestamp with time zone,
    last_index_status varchar(32),
    last_index_error text,
    tombstoned_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_bases_owner_slug_unique UNIQUE (owner_id, slug)
);

COMMENT ON TABLE knowledge_bases IS 'Knowledge base metadata table';
COMMENT ON COLUMN knowledge_bases.id IS 'Knowledge base unique ID';
COMMENT ON COLUMN knowledge_bases.slug IS 'Knowledge base slug';
COMMENT ON COLUMN knowledge_bases.name IS 'Knowledge base name';
COMMENT ON COLUMN knowledge_bases.description IS 'Knowledge base description';
COMMENT ON COLUMN knowledge_bases.template_id IS 'Knowledge base template ID';
COMMENT ON COLUMN knowledge_bases.owner_id IS 'Knowledge base owner user ID';
COMMENT ON COLUMN knowledge_bases.current_size_bytes IS 'Current storage usage in bytes';
COMMENT ON COLUMN knowledge_bases.quota_bytes IS 'Optional storage quota in bytes';
COMMENT ON COLUMN knowledge_bases.version_control_enabled IS 'Whether Git version control is enabled';
COMMENT ON COLUMN knowledge_bases.git_lfs_enabled IS 'Whether Git LFS is enabled';
COMMENT ON COLUMN knowledge_bases.git_default_branch IS 'Default Git branch';
COMMENT ON COLUMN knowledge_bases.git_last_commit_sha IS 'Last indexed Git commit SHA';
COMMENT ON COLUMN knowledge_bases.wiki_initialized_at IS 'Team Wiki initialization timestamp';
COMMENT ON COLUMN knowledge_bases.last_indexed_at IS 'Last indexing timestamp';
COMMENT ON COLUMN knowledge_bases.last_index_status IS 'Last indexing status';
COMMENT ON COLUMN knowledge_bases.last_index_error IS 'Last indexing error message';
COMMENT ON COLUMN knowledge_bases.tombstoned_at IS 'Tombstone timestamp for delayed cleanup';
COMMENT ON COLUMN knowledge_bases.created_at IS 'Creation time';
COMMENT ON COLUMN knowledge_bases.updated_at IS 'Last update time';

-- Table: knowledge_base_shares
CREATE TABLE IF NOT EXISTS knowledge_base_shares (
    id varchar(64) PRIMARY KEY,
    kb_id varchar(64) NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role varchar(32) NOT NULL CHECK (role IN ('viewer', 'editor', 'manager')),
    granted_by_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_base_shares_kb_user_unique UNIQUE (kb_id, user_id)
);

COMMENT ON TABLE knowledge_base_shares IS 'Knowledge base sharing authorization table';
COMMENT ON COLUMN knowledge_base_shares.id IS 'Share authorization unique ID';
COMMENT ON COLUMN knowledge_base_shares.kb_id IS 'Knowledge base ID';
COMMENT ON COLUMN knowledge_base_shares.user_id IS 'Shared user ID';
COMMENT ON COLUMN knowledge_base_shares.role IS 'Knowledge base share role';
COMMENT ON COLUMN knowledge_base_shares.granted_by_id IS 'Granting user ID';
COMMENT ON COLUMN knowledge_base_shares.created_at IS 'Share creation time';

-- Table: workspace_knowledge_base_attachments
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

COMMENT ON TABLE workspace_knowledge_base_attachments IS 'Workspace and knowledge base attachment table';
COMMENT ON COLUMN workspace_knowledge_base_attachments.id IS 'Attachment unique ID';
COMMENT ON COLUMN workspace_knowledge_base_attachments.workspace_id IS 'Workspace ID';
COMMENT ON COLUMN workspace_knowledge_base_attachments.kb_id IS 'Knowledge base ID';
COMMENT ON COLUMN workspace_knowledge_base_attachments.mount_alias IS 'Runtime mount alias';
COMMENT ON COLUMN workspace_knowledge_base_attachments.mode IS 'Mount mode';
COMMENT ON COLUMN workspace_knowledge_base_attachments.attached_by_id IS 'User ID that attached the knowledge base';
COMMENT ON COLUMN workspace_knowledge_base_attachments.created_at IS 'Attachment creation time';
COMMENT ON COLUMN workspace_knowledge_base_attachments.updated_at IS 'Attachment last update time';

-- Table: automation_jobs
CREATE TABLE IF NOT EXISTS automation_jobs (
    id varchar(64) PRIMARY KEY,
    name varchar(255) NOT NULL,
    description text,
    owner varchar(255) NOT NULL,
    creator_user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    prompt text NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'draft' CHECK (status IN ('active', 'paused', 'failed', 'draft')),
    trigger varchar(32) NOT NULL CHECK (trigger IN ('cron', 'manual', 'webhook')),
    schedule varchar(255) NOT NULL,
    tags jsonb DEFAULT '[]'::jsonb,
    notifications jsonb DEFAULT '{}'::jsonb,
    task_metadata jsonb DEFAULT '{}'::jsonb,
    webhook_api_key varchar(64),
    last_run_at timestamp with time zone,
    next_run_at timestamp with time zone,
    success_count integer DEFAULT 0 NOT NULL,
    failure_count integer DEFAULT 0 NOT NULL,
    total_duration integer DEFAULT 0 NOT NULL,
    last_duration integer,
    max_queue_size integer DEFAULT 10 NOT NULL,
    queue_timeout integer DEFAULT 3600 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE automation_jobs IS '自動化任務配置表';
COMMENT ON COLUMN automation_jobs.id IS '自動化任務唯一識別碼';
COMMENT ON COLUMN automation_jobs.name IS '自動化任務名稱';
COMMENT ON COLUMN automation_jobs.description IS '自動化任務描述';
COMMENT ON COLUMN automation_jobs.owner IS '負責人';
COMMENT ON COLUMN automation_jobs.creator_user_id IS '任務建立者用戶 ID';
COMMENT ON COLUMN automation_jobs.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN automation_jobs.prompt IS '任務提示或內容';
COMMENT ON COLUMN automation_jobs.status IS '任務狀態（active, paused, failed, draft）';
COMMENT ON COLUMN automation_jobs.trigger IS '觸發條件（cron, manual, webhook）';
COMMENT ON COLUMN automation_jobs.schedule IS '排程表達式（使用系統時區）';
COMMENT ON COLUMN automation_jobs.tags IS '任務標籤（JSON陣列）';
COMMENT ON COLUMN automation_jobs.notifications IS '通知設定（JSON物件）';
COMMENT ON COLUMN automation_jobs.task_metadata IS '任務額外設定（JSON物件）';
COMMENT ON COLUMN automation_jobs.webhook_api_key IS 'Webhook API Key';
COMMENT ON COLUMN automation_jobs.last_run_at IS '最後一次執行時間';
COMMENT ON COLUMN automation_jobs.next_run_at IS '下次計劃執行時間';
COMMENT ON COLUMN automation_jobs.success_count IS '成功執行次數';
COMMENT ON COLUMN automation_jobs.failure_count IS '失敗執行次數';
COMMENT ON COLUMN automation_jobs.total_duration IS '總執行時間（秒）';
COMMENT ON COLUMN automation_jobs.last_duration IS '最近一次執行時間（秒）';

-- Table: job_executions
CREATE TABLE IF NOT EXISTS job_executions (
    id varchar(64) PRIMARY KEY,
    job_id varchar(64) NOT NULL REFERENCES automation_jobs(id) ON DELETE CASCADE,
    status varchar(32) DEFAULT 'queued' CHECK (status IN ('queued', 'waiting', 'running', 'success', 'failed', 'cancelled', 'timeout')),
    trigger varchar(32) NOT NULL CHECK (trigger IN ('cron', 'manual', 'webhook')),
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    duration integer,
    session_id varchar(64),
    error_message text,
    summary text,
    execution_metadata jsonb DEFAULT '{}',
    queue_position integer,
    queued_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE job_executions IS '任務執行記錄表';
COMMENT ON COLUMN job_executions.id IS '執行記錄唯一識別碼';
COMMENT ON COLUMN job_executions.job_id IS '所屬自動化任務 ID';
COMMENT ON COLUMN job_executions.status IS '執行狀態（queued, waiting, running, success, failed, cancelled, timeout）';
COMMENT ON COLUMN job_executions.trigger IS '觸發方式（cron, manual, webhook）';
COMMENT ON COLUMN job_executions.started_at IS '實際開始執行時間';
COMMENT ON COLUMN job_executions.finished_at IS '任務完成時間';
COMMENT ON COLUMN job_executions.duration IS '任務執行時間（秒）';
COMMENT ON COLUMN job_executions.session_id IS '關聯的 AI 對話會話 ID';
COMMENT ON COLUMN job_executions.error_message IS '執行失敗時的錯誤訊息';
COMMENT ON COLUMN job_executions.summary IS '執行摘要';
COMMENT ON COLUMN job_executions.execution_metadata IS '執行元數據（JSON 格式）';
COMMENT ON COLUMN job_executions.created_at IS '記錄建立時間';
COMMENT ON COLUMN job_executions.queue_position IS '排隊位置（1-based），只有 waiting 狀態時有值';
COMMENT ON COLUMN job_executions.queued_at IS '加入佇列的時間，用於計算等待時長和超時清理';
COMMENT ON COLUMN job_executions.updated_at IS '記錄更新時間';

CREATE INDEX IF NOT EXISTS idx_job_executions_workspace_waiting
ON job_executions(job_id, status, queued_at)
WHERE status = 'waiting';

CREATE INDEX IF NOT EXISTS idx_job_executions_workspace_running
ON job_executions(job_id, status, started_at)
WHERE status = 'running';

CREATE INDEX IF NOT EXISTS idx_job_executions_timeout_cleanup
ON job_executions(status, queued_at)
WHERE status = 'waiting';

-- Table: workspace_runtime_logs
CREATE TABLE IF NOT EXISTS workspace_runtime_logs (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    stage varchar(64) NOT NULL,
    message text NOT NULL,
    log_metadata json DEFAULT '{}'::json,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE workspace_runtime_logs IS '工作區 Runtime 佈建日誌';
COMMENT ON COLUMN workspace_runtime_logs.id IS '日誌唯一識別碼';
COMMENT ON COLUMN workspace_runtime_logs.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN workspace_runtime_logs.stage IS '佈建階段';
COMMENT ON COLUMN workspace_runtime_logs.message IS '日誌訊息';
COMMENT ON COLUMN workspace_runtime_logs.log_metadata IS '日誌元數據（JSON格式）';
COMMENT ON COLUMN workspace_runtime_logs.created_at IS '日誌建立時間';

-- Table: workspace_runtime_jobs
CREATE TABLE IF NOT EXISTS workspace_runtime_jobs (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    operation varchar(32) NOT NULL,
    strategy varchar(32) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'queued',
    retries integer DEFAULT 0 NOT NULL,
    scheduled_at timestamp with time zone NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    error_message text
);

COMMENT ON TABLE workspace_runtime_jobs IS '工作區 Runtime 背景任務排程';
COMMENT ON COLUMN workspace_runtime_jobs.id IS '任務唯一識別碼';
COMMENT ON COLUMN workspace_runtime_jobs.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN workspace_runtime_jobs.operation IS '操作類型';
COMMENT ON COLUMN workspace_runtime_jobs.strategy IS '執行策略';
COMMENT ON COLUMN workspace_runtime_jobs.status IS '任務狀態';
COMMENT ON COLUMN workspace_runtime_jobs.retries IS '重試次數';
COMMENT ON COLUMN workspace_runtime_jobs.scheduled_at IS '計劃執行時間';
COMMENT ON COLUMN workspace_runtime_jobs.started_at IS '實際開始時間';
COMMENT ON COLUMN workspace_runtime_jobs.finished_at IS '完成時間';
COMMENT ON COLUMN workspace_runtime_jobs.error_message IS '錯誤訊息';

-- =====================================================
-- Multi-Agent Session Tables (Session-Task-Message Architecture)
-- =====================================================

-- Table: agent_sessions (Multi-Agent 會話表)
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'idle',
    agentic_tool VARCHAR(32) NOT NULL DEFAULT 'claude-code',
    workspace_id VARCHAR(64) NOT NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'user',
    ready_for_prompt BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    archived_reason VARCHAR(32),
    data TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS agent_sessions_status_idx ON agent_sessions(status);
CREATE INDEX IF NOT EXISTS agent_sessions_agentic_tool_idx ON agent_sessions(agentic_tool);
CREATE INDEX IF NOT EXISTS agent_sessions_workspace_idx ON agent_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS agent_sessions_workspace_status_idx ON agent_sessions(workspace_id, status);
CREATE INDEX IF NOT EXISTS agent_sessions_source_idx ON agent_sessions(source);
CREATE INDEX IF NOT EXISTS agent_sessions_created_idx ON agent_sessions(created_at);

COMMENT ON TABLE agent_sessions IS 'Multi-Agent AI 對話會話表，支援多種 Agentic 工具';
COMMENT ON COLUMN agent_sessions.session_id IS '會話唯一識別碼';
COMMENT ON COLUMN agent_sessions.status IS '會話狀態: idle, running, error';
COMMENT ON COLUMN agent_sessions.agentic_tool IS 'Agentic CLI 工具: claude-code, codex, gemini, opencode';
COMMENT ON COLUMN agent_sessions.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN agent_sessions.source IS '來源: user(使用者建立), automation(排程自動化建立)';
COMMENT ON COLUMN agent_sessions.ready_for_prompt IS '是否準備好接收新 prompt';
COMMENT ON COLUMN agent_sessions.archived IS '是否已封存';
COMMENT ON COLUMN agent_sessions.archived_reason IS '封存原因';
COMMENT ON COLUMN agent_sessions.data IS 'JSON blob 包含: model, title, instruction, permission_config, context_window_limit/used, message_count, token_usage 等';

-- Table: agent_tasks (Multi-Agent 任務表)
CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_by VARCHAR(255),
    data TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS agent_tasks_session_idx ON agent_tasks(session_id);
CREATE INDEX IF NOT EXISTS agent_tasks_status_idx ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS agent_tasks_session_status_idx ON agent_tasks(session_id, status);
CREATE INDEX IF NOT EXISTS agent_tasks_created_idx ON agent_tasks(created_at);

COMMENT ON TABLE agent_tasks IS 'Multi-Agent 任務表，代表一次 Prompt → Response 循環';
COMMENT ON COLUMN agent_tasks.task_id IS '任務唯一識別碼';
COMMENT ON COLUMN agent_tasks.session_id IS '所屬會話 ID';
COMMENT ON COLUMN agent_tasks.status IS '任務狀態: created, running, stopping, awaiting_permission, completed, failed, stopped';
COMMENT ON COLUMN agent_tasks.data IS 'JSON blob 包含: full_prompt, model, tool_use_count, error_message, stopped_reason, raw_sdk_response, token_usage, message_start/end_index 等';

-- Table: agent_messages (Multi-Agent 訊息表)
CREATE TABLE IF NOT EXISTS agent_messages (
    message_id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    session_id VARCHAR(36) NOT NULL REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
    task_id VARCHAR(36) REFERENCES agent_tasks(task_id) ON DELETE SET NULL,
    type VARCHAR(32) NOT NULL DEFAULT 'user',
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    index INTEGER NOT NULL DEFAULT 0,
    timestamp TIMESTAMP WITH TIME ZONE,
    content_preview VARCHAR(500),
    parent_tool_use_id VARCHAR(64),
    status VARCHAR(32),
    queue_position INTEGER,
    data TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS agent_messages_session_idx ON agent_messages(session_id);
CREATE INDEX IF NOT EXISTS agent_messages_task_idx ON agent_messages(task_id);
CREATE INDEX IF NOT EXISTS agent_messages_session_index_idx ON agent_messages(session_id, index);
CREATE INDEX IF NOT EXISTS agent_messages_queue_idx ON agent_messages(session_id, status, queue_position);

COMMENT ON TABLE agent_messages IS 'Multi-Agent 訊息表，支援多種內容區塊類型';
COMMENT ON COLUMN agent_messages.message_id IS '訊息唯一識別碼';
COMMENT ON COLUMN agent_messages.session_id IS '所屬會話 ID';
COMMENT ON COLUMN agent_messages.task_id IS '所屬任務 ID (可為空)';
COMMENT ON COLUMN agent_messages.type IS '訊息類型: user, assistant, system, file-history-snapshot, permission_request';
COMMENT ON COLUMN agent_messages.role IS '訊息角色: user, assistant, system';
COMMENT ON COLUMN agent_messages.index IS '訊息在會話中的序號';
COMMENT ON COLUMN agent_messages.content_preview IS '內容預覽 (前 500 字)';
COMMENT ON COLUMN agent_messages.parent_tool_use_id IS '巢狀工具呼叫的父 tool_use ID';
COMMENT ON COLUMN agent_messages.status IS '訊息狀態: NULL 為正常, queued 為佇列中';
COMMENT ON COLUMN agent_messages.queue_position IS '佇列位置';
COMMENT ON COLUMN agent_messages.data IS 'JSON blob 包含: content_blocks, token_usage, in_context, is_compacted 等';

-- Trigger: 自動更新 agent_sessions.updated_at
CREATE OR REPLACE FUNCTION update_agent_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_agent_sessions_updated_at ON agent_sessions;
CREATE TRIGGER trigger_update_agent_sessions_updated_at
    BEFORE UPDATE ON agent_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_sessions_updated_at();

-- =====================================================
-- End of Multi-Agent Session Tables
-- =====================================================

-- Database level comment
-- Note: Removing problematic current_database() function call

-- ========================================
-- Default Data Initialization
-- ========================================

-- Default Admin User
INSERT INTO users (id, username, email, keycloak_id, display_name, avatar_url, is_active, created_at, updated_at)
VALUES (
    'admin-user-default',
    'admin',
    'admin@aileron.com',
    '9cd556e6-6d41-41a0-9662-053f0f400a3b',
    'Aileron Administrator',
    'https://avatars.githubusercontent.com/u/1?v=4',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE
SET
    username = EXCLUDED.username,
    email = EXCLUDED.email,
    display_name = 'Aileron Administrator',
    is_active = EXCLUDED.is_active,
    updated_at = CURRENT_TIMESTAMP;

-- Default Team
DO $$
BEGIN
    IF to_regclass('public.teams') IS NOT NULL
       AND EXISTS (SELECT 1 FROM users WHERE id = 'admin-user-default') THEN
        INSERT INTO teams (id, name, description, owner_id, is_active, created_at, updated_at)
        VALUES (
            'default-team',
            'Default Team',
            'Aileron 預設開發團隊',
            'admin-user-default',
            true,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        ) ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Default Team Members
DO $$
BEGIN
    IF to_regclass('public.team_members') IS NOT NULL
       AND EXISTS (SELECT 1 FROM users WHERE id = 'admin-user-default') THEN
        INSERT INTO team_members (id, team_id, user_id, role, joined_at)
        VALUES
            ('team-member-admin', 'default-team', 'admin-user-default', 'owner', CURRENT_TIMESTAMP)
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Default User Settings
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE id = 'admin-user-default') THEN
        INSERT INTO user_settings (
            id,
            user_id,
            claude_selected_model,
            claude_selected_provider,
            general_settings,
            additional_settings,
            created_at,
            updated_at
        )
        VALUES
            (
                'settings-admin',
                'admin-user-default',
                'claude-sonnet-4-20250514',
                'anthropic',
                '{
                    "theme": "system",
                    "language": "zh-TW",
                    "timezone": "Asia/Taipei",
                    "notifications": {
                        "desktop": true,
                        "email": false,
                        "updates": true
                    },
                    "performance": {
                        "autoSave": true,
                        "animationsEnabled": true
                    },
                    "privacy": {
                        "analytics": false,
                        "crashReports": true,
                        "usageData": false
                    }
                }'::jsonb,
                '{
                    "ssh": {
                        "publicKey": "",
                        "privateKey": "",
                        "fingerprint": null,
                        "lastRotatedAt": null
                    },
                    "claudeCode": {
                        "authMethod": "subscription",
                        "subscriptionAuthCode": "",
                        "subscriptionAccessToken": "",
                        "subscriptionRefreshToken": "",
                        "subscriptionExpiresAt": "",
                        "authKey": "",
                        "apiProvider": "anthropic",
                        "selectedModel": "claude-sonnet-4-20250514",
                        "selectedProvider": "anthropic",
                        "environmentVariables": [],
                        "availableModels": [],
                        "availableProviders": []
                    },
                    "git": {
                        "userName": "",
                        "userEmail": "",
                        "signingKey": null
                    }
                }'::jsonb,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Default Model Configs
INSERT INTO model_configs (id, model_key, model_name, anthropic_model_id, is_active, sort_order, created_at, updated_at)
VALUES
    ('model-claude-sonnet-4', 'claude-sonnet-4-20250514', 'Claude 3.5 Sonnet (Latest)', 'claude-3-5-sonnet-20241022', true, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('model-claude-haiku', 'claude-haiku-20240307', 'Claude 3 Haiku', 'claude-3-haiku-20240307', true, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('model-claude-opus', 'claude-opus-20240229', 'Claude 3 Opus', 'claude-3-opus-20240229', true, 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;
