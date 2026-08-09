-- Aileron Database Initialization Script
-- Regenerated from docs/database/schema.md

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Runtime roles must never inherit CREATE on the shared public schema.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id varchar(128) PRIMARY KEY,
    username varchar(255) NOT NULL,
    email varchar(255),
    oidc_issuer varchar(2048),
    oidc_subject varchar(255),
    first_name varchar(255),
    last_name varchar(255),
    display_name varchar(255),
    avatar_url text,
    is_active boolean DEFAULT true NOT NULL,
    identity_enabled boolean DEFAULT true NOT NULL,
    sync_status varchar(64) DEFAULT 'synced' NOT NULL CHECK (sync_status IN ('synced', 'local_shadow_imported', 'local_shadow_missing', 'identity_sync_failed')),
    platform_role varchar(64) CHECK (platform_role IS NULL OR platform_role IN ('admin', 'member')),
    role_status varchar(64) DEFAULT 'missing' NOT NULL CHECK (role_status IN ('valid', 'missing', 'multiple')),
    role_issues jsonb NOT NULL DEFAULT '[]'::jsonb,
    recent_workspace_id varchar(64),
    last_synced_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE users IS '用戶基本資料表';
COMMENT ON COLUMN users.id IS '用戶唯一識別碼';
COMMENT ON COLUMN users.username IS 'Provider profile display identifier';
COMMENT ON COLUMN users.email IS 'Provider profile email snapshot';
COMMENT ON COLUMN users.oidc_issuer IS 'Canonical OIDC issuer';
COMMENT ON COLUMN users.oidc_subject IS 'Canonical OIDC subject';
COMMENT ON COLUMN users.display_name IS '用戶顯示名稱';
COMMENT ON COLUMN users.avatar_url IS '用戶頭像圖片 URL';
COMMENT ON COLUMN users.first_name IS '用戶名字';
COMMENT ON COLUMN users.last_name IS '用戶姓氏';
COMMENT ON COLUMN users.is_active IS '帳號是否啟用狀態';
COMMENT ON COLUMN users.identity_enabled IS 'Identity provider enabled snapshot';
COMMENT ON COLUMN users.sync_status IS 'Local identity snapshot sync status';
COMMENT ON COLUMN users.platform_role IS 'Single Aileron platform role';
COMMENT ON COLUMN users.role_status IS 'Platform role validation status';
COMMENT ON COLUMN users.role_issues IS 'Canonical platform role validation issues';
COMMENT ON COLUMN users.recent_workspace_id IS 'Most recently selected workspace ID';
COMMENT ON COLUMN users.last_synced_at IS 'Latest identity snapshot sync time';
COMMENT ON COLUMN users.created_at IS '帳號建立時間';
COMMENT ON COLUMN users.updated_at IS '帳號最後更新時間';

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_oidc_principal
ON users(oidc_issuer, oidc_subject)
WHERE oidc_issuer IS NOT NULL AND oidc_subject IS NOT NULL;

-- Table: user_settings
CREATE TABLE IF NOT EXISTS user_settings (
    id varchar(128) PRIMARY KEY,
    user_id varchar(128) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    claude_auth_key text,
    claude_selected_model varchar(64) DEFAULT 'claude-opus-4-8' NOT NULL,
    git_user_name varchar(255),
    git_user_email varchar(255),
    git_signing_key text,
    ssh_private_key text,
    ssh_public_key text,
    ssh_fingerprint varchar(128),
    ssh_last_rotated_at timestamp with time zone,
    general_settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    additional_settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE user_settings IS '用戶個人設定表';
COMMENT ON COLUMN user_settings.id IS '設定唯一識別碼';
COMMENT ON COLUMN user_settings.user_id IS '所屬用戶ID';
COMMENT ON COLUMN user_settings.claude_auth_key IS 'Claude API 認證金鑰';
COMMENT ON COLUMN user_settings.claude_selected_model IS '用戶選擇的 Claude 模型';
COMMENT ON COLUMN user_settings.git_user_name IS 'Git 配置的用戶名稱';
COMMENT ON COLUMN user_settings.git_user_email IS 'Git 配置的用戶郵箱';
COMMENT ON COLUMN user_settings.ssh_private_key IS 'SSH 私鑰內容';
COMMENT ON COLUMN user_settings.ssh_public_key IS 'SSH 公鑰內容';
COMMENT ON COLUMN user_settings.general_settings IS '一般設定（JSON格式）';
COMMENT ON COLUMN user_settings.additional_settings IS '其他擴展設定（JSON格式，包含 Claude Code OAuth tokens）';

-- Table: workspaces
CREATE TABLE IF NOT EXISTS workspaces (
    id varchar(64) PRIMARY KEY,
    owner_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    git_url text,
    branch text DEFAULT 'main' NOT NULL,
    runtime text DEFAULT 'universal' NOT NULL,
    env_vars jsonb DEFAULT '[]'::jsonb NOT NULL,
    acp_cli_args jsonb DEFAULT '[]'::jsonb NOT NULL,
    setup_script text,
    bootstrap_revision bigint DEFAULT 1 NOT NULL CHECK (bootstrap_revision >= 1),
    bootstrap_observed_revision bigint DEFAULT 0 NOT NULL,
    bootstrap_status varchar(32) DEFAULT 'pending' NOT NULL CHECK (bootstrap_status IN ('pending', 'running', 'succeeded', 'error')),
    bootstrap_error_code varchar(64),
    bootstrap_last_transition_at timestamp with time zone,
    runtime_container_id text,
    runtime_desired_state varchar(16) DEFAULT 'stopped' NOT NULL CHECK (runtime_desired_state IN ('running', 'stopped')),
    runtime_desired_revision bigint DEFAULT 1 NOT NULL CHECK (runtime_desired_revision >= 1),
    runtime_observed_revision bigint DEFAULT 0 NOT NULL,
    runtime_reason varchar(64),
    runtime_error_code varchar(64),
    runtime_last_transition_at timestamp with time zone,
    runtime_internal_url text,
    runtime_internal_port integer DEFAULT 3002 NOT NULL,
    runtime_status text DEFAULT 'stopped' NOT NULL CHECK (runtime_status IN ('starting', 'running', 'stopping', 'stopped', 'restarting', 'error', 'deleting')),
    runtime_last_seen timestamp with time zone,
    knowledge_base_mount_active_revision bigint DEFAULT 0 NOT NULL,
    knowledge_base_mount_desired_revision bigint DEFAULT 0 NOT NULL,
    knowledge_base_mount_observed_revision bigint DEFAULT 0 NOT NULL,
    knowledge_base_mount_sync_status varchar(32) DEFAULT 'ready' NOT NULL CHECK (
        knowledge_base_mount_sync_status IN (
            'ready',
            'preflighting',
            'applying',
            'compensating',
            'degraded'
        )
    ),
    knowledge_base_mount_error_code varchar(64),
    knowledge_base_mount_active_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL,
    knowledge_base_mount_candidate_snapshot jsonb,
    knowledge_base_mount_failed_snapshot jsonb,
    runtime_access_revision bigint DEFAULT 0 NOT NULL,
    runtime_access_observed_revision bigint DEFAULT 0 NOT NULL,
    runtime_instance_id uuid,
    browser_instance_id uuid,
    canvas_instance_id uuid,
    runtime_control_instance_id uuid,
    runtime_control_token_hash varchar(64),
    canvas_container_id text,
    canvas_desired_state varchar(16) DEFAULT 'stopped' NOT NULL CHECK (canvas_desired_state IN ('running', 'stopped')),
    canvas_desired_revision bigint DEFAULT 1 NOT NULL CHECK (canvas_desired_revision >= 1),
    canvas_observed_revision bigint DEFAULT 0 NOT NULL,
    canvas_reason varchar(64),
    canvas_error_code varchar(64),
    canvas_last_transition_at timestamp with time zone,
    canvas_status text DEFAULT 'stopped' NOT NULL CHECK (canvas_status IN ('stopped', 'starting', 'running', 'error', 'restarting')),
    canvas_created_at timestamp with time zone,
    canvas_last_seen timestamp with time zone,
    canvas_internal_url text,
    canvas_internal_port integer DEFAULT 3003 NOT NULL,
    canvas_api_internal_port integer DEFAULT 3013 NOT NULL,
    canvas_type text DEFAULT 'default' NOT NULL CHECK (canvas_type IN ('html', 'nextjs', 'default')),
    canvas_manifest_status text DEFAULT 'missing' NOT NULL CHECK (canvas_manifest_status IN ('missing', 'valid', 'invalid')),
    canvas_last_sync_at timestamp with time zone,
    canvas_last_reset_at timestamp with time zone,
    terminal_internal_url varchar(512),
    provisioner text DEFAULT 'docker' NOT NULL CHECK (provisioner IN ('docker', 'kubernetes')),
    target_namespace varchar(253),
    workspace_firewall_egress_mode text DEFAULT 'unrestricted' NOT NULL CHECK (workspace_firewall_egress_mode IN ('blocked', 'allowlist', 'unrestricted')),
    workspace_firewall_allowed_domains jsonb DEFAULT '[]'::jsonb NOT NULL,
    browser_firewall_egress_mode text DEFAULT 'unrestricted' NOT NULL CHECK (browser_firewall_egress_mode IN ('blocked', 'allowlist', 'unrestricted')),
    browser_firewall_allowed_domains jsonb DEFAULT '[]'::jsonb NOT NULL,
    CONSTRAINT workspace_firewall_allowed_domains_match_egress_mode CHECK (
        (
            workspace_firewall_egress_mode = 'allowlist'
            AND jsonb_typeof(workspace_firewall_allowed_domains) = 'array'
            AND jsonb_array_length(workspace_firewall_allowed_domains) > 0
        )
        OR (
            workspace_firewall_egress_mode <> 'allowlist'
            AND workspace_firewall_allowed_domains = '[]'::jsonb
        )
    ),
    CONSTRAINT browser_firewall_allowed_domains_match_egress_mode CHECK (
        (
            browser_firewall_egress_mode = 'allowlist'
            AND jsonb_typeof(browser_firewall_allowed_domains) = 'array'
            AND jsonb_array_length(browser_firewall_allowed_domains) > 0
        )
        OR (
            browser_firewall_egress_mode <> 'allowlist'
            AND browser_firewall_allowed_domains = '[]'::jsonb
        )
    ),
    firewall_revision bigint DEFAULT 1 NOT NULL CHECK (firewall_revision >= 1),
    firewall_observed_revision bigint DEFAULT 0 NOT NULL CHECK (
        firewall_observed_revision >= 0 AND firewall_observed_revision <= firewall_revision
    ),
    firewall_sync_status varchar(32) DEFAULT 'pending' NOT NULL CHECK (
        firewall_sync_status IN ('pending', 'applying', 'applied', 'error', 'unavailable')
    ),
    firewall_error_code varchar(64),
    firewall_target_delivery_id varchar(64),
    preferred_cli text DEFAULT 'claude-code' NOT NULL,
    agentic_tools jsonb DEFAULT '["claude-code"]'::jsonb NOT NULL,
    agentic_capabilities jsonb,

    fallback_enabled boolean DEFAULT true NOT NULL,
    workspace_path text DEFAULT '/workspace' NOT NULL,
    worktree_subdir text NOT NULL DEFAULT '.worktrees',

    -- Browser container fields
    browser_container_id text,
    browser_desired_state varchar(16) DEFAULT 'stopped' NOT NULL CHECK (browser_desired_state IN ('running', 'stopped')),
    browser_desired_revision bigint DEFAULT 1 NOT NULL CHECK (browser_desired_revision >= 1),
    browser_observed_revision bigint DEFAULT 0 NOT NULL,
    browser_reason varchar(64),
    browser_error_code varchar(64),
    browser_last_transition_at timestamp with time zone,
    browser_credential_revision bigint DEFAULT 1 NOT NULL,
    browser_credential_observed_revision bigint DEFAULT 0 NOT NULL,
    browser_credential_key_id text DEFAULT '' NOT NULL,
    browser_credential_observed_key_id text,
    browser_credential_algorithm varchar(32) DEFAULT 'hkdf-sha256-v1' NOT NULL,
    browser_credential_observed_algorithm varchar(32),
    browser_status text DEFAULT 'stopped' NOT NULL CHECK (browser_status IN ('stopped', 'starting', 'running', 'error', 'restarting')),
    browser_connectivity_state varchar(32) DEFAULT 'pending' NOT NULL,
    browser_connectivity_contract_version text DEFAULT 'browser-connectivity/v1' NOT NULL,
    browser_connectivity_admission varchar(16) DEFAULT 'denied' NOT NULL,
    browser_connectivity_browser_generation text,
    browser_connectivity_profile_revision text,
    browser_connectivity_credential_revision text,
    browser_connectivity_accepted_at timestamp with time zone,
    browser_connectivity_expires_at timestamp with time zone,
    browser_connectivity_reason varchar(64) DEFAULT 'BrowserConnectivityPending' NOT NULL,
    browser_connectivity_error_code varchar(64),
    browser_connectivity_last_transition_at timestamp with time zone,
    browser_connectivity_backend_state varchar(32) DEFAULT 'pending' NOT NULL,
    browser_connectivity_backend_accepted_at timestamp with time zone,
    browser_connectivity_backend_expires_at timestamp with time zone,
    browser_connectivity_backend_reason varchar(64),
    browser_connectivity_backend_error_code varchar(64),
    browser_connectivity_frontend_state varchar(32) DEFAULT 'pending' NOT NULL,
    browser_connectivity_frontend_accepted_at timestamp with time zone,
    browser_connectivity_frontend_expires_at timestamp with time zone,
    browser_connectivity_frontend_reason varchar(64),
    browser_connectivity_frontend_error_code varchar(64),
    browser_created_at timestamp with time zone,
    browser_last_seen timestamp with time zone,

    -- Browser WebRTC (neko) fields
    browser_webrtc_internal_url text,
    browser_webrtc_internal_port integer DEFAULT 6080 NOT NULL,

    -- Browser CDP fields
    browser_cdp_internal_port integer DEFAULT 9223 NOT NULL,

    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT workspaces_runtime_control_pair_check CHECK (
        (runtime_control_instance_id IS NULL) = (runtime_control_token_hash IS NULL)
    ),
    CONSTRAINT workspaces_runtime_control_generation_check CHECK (
        (runtime_instance_id IS NULL AND runtime_control_instance_id IS NULL)
        OR runtime_instance_id = runtime_control_instance_id
    ),
    CONSTRAINT workspaces_runtime_control_token_hash_check CHECK (
        runtime_control_token_hash IS NULL OR runtime_control_token_hash ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT workspaces_bootstrap_observed_revision_check CHECK (
        bootstrap_observed_revision >= 0 AND bootstrap_observed_revision <= bootstrap_revision
    ),
    CONSTRAINT workspaces_runtime_observed_revision_check CHECK (
        runtime_observed_revision >= 0 AND runtime_observed_revision <= runtime_desired_revision
    ),
    CONSTRAINT workspaces_knowledge_base_mount_revision_check CHECK (
        knowledge_base_mount_active_revision >= 0
        AND knowledge_base_mount_desired_revision >= knowledge_base_mount_active_revision
        AND knowledge_base_mount_observed_revision >= 0
        AND knowledge_base_mount_observed_revision <= knowledge_base_mount_desired_revision
    ),
    CONSTRAINT workspaces_browser_observed_revision_check CHECK (
        browser_observed_revision >= 0 AND browser_observed_revision <= browser_desired_revision
    ),
    CONSTRAINT workspaces_canvas_observed_revision_check CHECK (
        canvas_observed_revision >= 0 AND canvas_observed_revision <= canvas_desired_revision
    ),
    CONSTRAINT workspaces_browser_credential_revision_check CHECK (
        browser_credential_revision >= 1
        AND browser_credential_observed_revision >= 0
        AND browser_credential_observed_revision <= browser_credential_revision
    ),
    CONSTRAINT workspaces_browser_credential_algorithm_check CHECK (
        browser_credential_algorithm = 'hkdf-sha256-v1'
        AND (
            browser_credential_observed_algorithm IS NULL
            OR browser_credential_observed_algorithm = 'hkdf-sha256-v1'
        )
    ),
    CONSTRAINT workspaces_browser_connectivity_state_check CHECK (
        browser_connectivity_state IN ('pending', 'ready', 'degraded', 'not_ready', 'unavailable')
    ),
    CONSTRAINT workspaces_browser_connectivity_admission_check CHECK (
        browser_connectivity_admission IN ('allowed', 'denied')
    ),
    CONSTRAINT workspaces_browser_connectivity_backend_state_check CHECK (
        browser_connectivity_backend_state IN ('pending', 'ready', 'degraded', 'not_ready', 'unavailable')
    ),
    CONSTRAINT workspaces_browser_connectivity_frontend_state_check CHECK (
        browser_connectivity_frontend_state IN ('pending', 'ready', 'degraded', 'not_ready', 'unavailable')
    )
);

COMMENT ON TABLE workspaces IS '開發工作區配置表';
COMMENT ON COLUMN workspaces.id IS '工作區唯一識別碼';
COMMENT ON COLUMN workspaces.owner_id IS '工作區擁有者用戶 ID';
COMMENT ON COLUMN workspaces.name IS '工作區名稱';
COMMENT ON COLUMN workspaces.description IS '工作區描述';
COMMENT ON COLUMN workspaces.git_url IS 'Git 儲存庫 URL';
COMMENT ON COLUMN workspaces.branch IS 'Git 分支名稱';
COMMENT ON COLUMN workspaces.runtime IS '運行時環境類型';
COMMENT ON COLUMN workspaces.env_vars IS '環境變數配置（JSON陣列）';
COMMENT ON COLUMN workspaces.setup_script IS '工作區初始化腳本';
COMMENT ON COLUMN workspaces.runtime_container_id IS '運行時容器 ID';
COMMENT ON COLUMN workspaces.runtime_internal_url IS '容器內部通信 URL';
COMMENT ON COLUMN workspaces.runtime_internal_port IS '容器內部監聽端口';
COMMENT ON COLUMN workspaces.runtime_status IS '容器運行狀態';
COMMENT ON COLUMN workspaces.runtime_last_seen IS '容器最後活動時間';
COMMENT ON COLUMN workspaces.knowledge_base_mount_active_revision IS 'Last-known-good knowledge base mount revision';
COMMENT ON COLUMN workspaces.knowledge_base_mount_desired_revision IS 'Desired knowledge base mount revision';
COMMENT ON COLUMN workspaces.knowledge_base_mount_observed_revision IS 'Observed knowledge base mount revision';
COMMENT ON COLUMN workspaces.knowledge_base_mount_sync_status IS 'Knowledge base mount synchronization status';
COMMENT ON COLUMN workspaces.knowledge_base_mount_error_code IS 'Stable knowledge base mount error code';
COMMENT ON COLUMN workspaces.knowledge_base_mount_active_snapshot IS 'Last-known-good canonical knowledge base mount snapshot';
COMMENT ON COLUMN workspaces.knowledge_base_mount_candidate_snapshot IS 'Canonical knowledge base mount candidate';
COMMENT ON COLUMN workspaces.knowledge_base_mount_failed_snapshot IS 'Most recent failed canonical knowledge base mount candidate';
COMMENT ON COLUMN workspaces.runtime_access_revision IS 'Desired runtime access revision';
COMMENT ON COLUMN workspaces.runtime_access_observed_revision IS 'Observed runtime access revision';
COMMENT ON COLUMN workspaces.runtime_instance_id IS 'Runtime workload generation ID';
COMMENT ON COLUMN workspaces.browser_instance_id IS 'Browser workload generation ID';
COMMENT ON COLUMN workspaces.canvas_instance_id IS 'Canvas workload generation ID';
COMMENT ON COLUMN workspaces.runtime_control_instance_id IS 'Generation authorized for Runtime control requests';
COMMENT ON COLUMN workspaces.runtime_control_token_hash IS 'SHA-256 digest of the generation-scoped Runtime control token';
COMMENT ON COLUMN workspaces.canvas_container_id IS 'Canvas 容器 ID';
COMMENT ON COLUMN workspaces.canvas_status IS 'Canvas 容器運行狀態';
COMMENT ON COLUMN workspaces.canvas_created_at IS 'Canvas 容器建立時間';
COMMENT ON COLUMN workspaces.canvas_last_seen IS 'Canvas 容器最後活動時間';
COMMENT ON COLUMN workspaces.canvas_internal_url IS 'Canvas 容器內部通信 URL';
COMMENT ON COLUMN workspaces.canvas_internal_port IS 'Canvas render server 內部端口（預設 3003）';
COMMENT ON COLUMN workspaces.canvas_api_internal_port IS 'Canvas 管理 API 內部端口（預設 3013）';
COMMENT ON COLUMN workspaces.canvas_type IS 'Canvas 最近偵測類型（html / nextjs / default）';
COMMENT ON COLUMN workspaces.canvas_manifest_status IS 'Canvas manifest 狀態（missing / valid / invalid）';
COMMENT ON COLUMN workspaces.canvas_last_sync_at IS 'Canvas 最近同步時間';
COMMENT ON COLUMN workspaces.canvas_last_reset_at IS 'Canvas 最近 reset 時間';
COMMENT ON COLUMN workspaces.terminal_internal_url IS 'Manager-only Terminal drain URL';
COMMENT ON COLUMN workspaces.provisioner IS '工作區佈建模式（docker / kubernetes）';
COMMENT ON COLUMN workspaces.target_namespace IS 'Kubernetes 模式下目標部署 namespace';
COMMENT ON COLUMN workspaces.workspace_firewall_egress_mode IS 'Workspace external egress mode';
COMMENT ON COLUMN workspaces.workspace_firewall_allowed_domains IS 'Workspace exact hostname allowlist';
COMMENT ON COLUMN workspaces.browser_firewall_egress_mode IS 'Browser external egress mode';
COMMENT ON COLUMN workspaces.browser_firewall_allowed_domains IS 'Browser exact hostname allowlist';
COMMENT ON COLUMN workspaces.preferred_cli IS '偏好的命令行介面';
COMMENT ON COLUMN workspaces.agentic_tools IS '工作區啟用的 Agentic CLI 工具清單（claude-code / codex / opencode）';
COMMENT ON COLUMN workspaces.fallback_enabled IS '是否啟用 AI 模型備援機制';
COMMENT ON COLUMN workspaces.workspace_path IS '工作區在容器中的路徑';
COMMENT ON COLUMN workspaces.browser_container_id IS 'Browser 容器 ID';
COMMENT ON COLUMN workspaces.browser_status IS 'Browser 容器運行狀態';
COMMENT ON COLUMN workspaces.browser_created_at IS 'Browser 容器建立時間';
COMMENT ON COLUMN workspaces.browser_last_seen IS 'Browser 容器最後活動時間';
COMMENT ON COLUMN workspaces.browser_webrtc_internal_url IS 'Browser WebRTC (neko) 容器內部通信 URL';
COMMENT ON COLUMN workspaces.browser_webrtc_internal_port IS 'Browser WebRTC (neko) 內部端口（預設 6080）';
COMMENT ON COLUMN workspaces.browser_cdp_internal_port IS 'Browser CDP 內部端口（預設 9223）';
-- Table: workspace_shares
CREATE TABLE IF NOT EXISTS workspace_shares (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    target_type varchar(64) NOT NULL CHECK (target_type IN ('user', 'user_group')),
    target_id varchar(128) NOT NULL,
    role varchar(32) NOT NULL CHECK (role IN ('reader', 'manager')),
    granted_by_user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT workspace_shares_workspace_target_unique UNIQUE (workspace_id, target_type, target_id)
);

COMMENT ON TABLE workspace_shares IS 'Workspace share authorization records';
COMMENT ON COLUMN workspace_shares.id IS 'Unique workspace share identifier';
COMMENT ON COLUMN workspace_shares.workspace_id IS 'Shared workspace identifier';
COMMENT ON COLUMN workspace_shares.target_type IS 'Workspace share target type';
COMMENT ON COLUMN workspace_shares.target_id IS 'Workspace share target identifier';
COMMENT ON COLUMN workspace_shares.role IS 'Workspace resource role (reader / manager)';
COMMENT ON COLUMN workspace_shares.granted_by_user_id IS 'User granting workspace access';
COMMENT ON COLUMN workspace_shares.created_at IS 'Workspace share creation time';
COMMENT ON COLUMN workspace_shares.updated_at IS 'Workspace share last update time';

-- Table: knowledge_bases
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id varchar(64) PRIMARY KEY,
    slug varchar(255) NOT NULL,
    name varchar(255) NOT NULL,
    description text,
    owner_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_size_bytes integer NOT NULL DEFAULT 0,
    quota_bytes integer,
    version_control_enabled boolean DEFAULT false NOT NULL,
    last_indexed_at timestamp with time zone,
    last_index_status varchar(32),
    last_index_error text,
    visibility varchar(16) DEFAULT 'private' NOT NULL CHECK (visibility IN ('private', 'public')),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_bases_owner_slug_unique UNIQUE (owner_id, slug)
);

COMMENT ON TABLE knowledge_bases IS 'Knowledge base metadata table';
COMMENT ON COLUMN knowledge_bases.id IS 'Knowledge base unique ID';
COMMENT ON COLUMN knowledge_bases.slug IS 'Knowledge base slug';
COMMENT ON COLUMN knowledge_bases.name IS 'Knowledge base name';
COMMENT ON COLUMN knowledge_bases.description IS 'Knowledge base description';
COMMENT ON COLUMN knowledge_bases.owner_id IS 'Knowledge base owner user ID';
COMMENT ON COLUMN knowledge_bases.current_size_bytes IS 'Current storage usage in bytes';
COMMENT ON COLUMN knowledge_bases.quota_bytes IS 'Optional storage quota in bytes';
COMMENT ON COLUMN knowledge_bases.version_control_enabled IS 'Whether Git version control is enabled';
COMMENT ON COLUMN knowledge_bases.last_indexed_at IS 'Last indexing timestamp';
COMMENT ON COLUMN knowledge_bases.last_index_status IS 'Last indexing status';
COMMENT ON COLUMN knowledge_bases.last_index_error IS 'Last indexing error message';
COMMENT ON COLUMN knowledge_bases.visibility IS 'Platform visibility (private / public)';
COMMENT ON COLUMN knowledge_bases.created_at IS 'Creation time';
COMMENT ON COLUMN knowledge_bases.updated_at IS 'Last update time';

-- Table: knowledge_base_shares
CREATE TABLE IF NOT EXISTS knowledge_base_shares (
    id varchar(64) PRIMARY KEY,
    kb_id varchar(64) NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    target_type varchar(64) NOT NULL CHECK (target_type IN ('user', 'user_group')),
    target_id varchar(128) NOT NULL,
    role varchar(32) NOT NULL CHECK (role IN ('reader', 'manager')),
    granted_by_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_base_shares_kb_target_unique UNIQUE (kb_id, target_type, target_id)
);

COMMENT ON TABLE knowledge_base_shares IS 'Knowledge base sharing authorization table';
COMMENT ON COLUMN knowledge_base_shares.id IS 'Share authorization unique ID';
COMMENT ON COLUMN knowledge_base_shares.kb_id IS 'Knowledge base ID';
COMMENT ON COLUMN knowledge_base_shares.target_type IS 'Share target type';
COMMENT ON COLUMN knowledge_base_shares.target_id IS 'Share target ID';
COMMENT ON COLUMN knowledge_base_shares.role IS 'Knowledge base share role';
COMMENT ON COLUMN knowledge_base_shares.granted_by_id IS 'Granting user ID';
COMMENT ON COLUMN knowledge_base_shares.created_at IS 'Share creation time';

-- Table: user_groups
CREATE TABLE IF NOT EXISTS user_groups (
    id varchar(64) PRIMARY KEY,
    name varchar(255) UNIQUE NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- Table: user_group_members
CREATE TABLE IF NOT EXISTS user_group_members (
    id varchar(64) PRIMARY KEY,
    group_id varchar(64) NOT NULL REFERENCES user_groups(id) ON DELETE CASCADE,
    user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_by_id varchar(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_group_members_group_user_unique UNIQUE (group_id, user_id)
);

-- Table: audit_events
CREATE TABLE IF NOT EXISTS audit_events (
    id varchar(64) PRIMARY KEY,
    event_type varchar(128) NOT NULL,
    actor_type varchar(32) NOT NULL CHECK (actor_type IN ('user', 'service')),
    actor_id text NOT NULL,
    actor_user_id varchar(128) REFERENCES users(id) ON DELETE SET NULL,
    target_type varchar(128) NOT NULL,
    target_id varchar(128) NOT NULL,
    action varchar(128) NOT NULL,
    result varchar(32) NOT NULL CHECK (result IN ('success', 'failure', 'compensation_required')),
    error_code varchar(64),
    correlation_id varchar(64) NOT NULL,
    root_correlation_id varchar(64) NOT NULL,
    event_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT audit_events_service_actor_user_check CHECK (
        actor_type = 'user' OR actor_user_id IS NULL
    ),
    CONSTRAINT audit_events_result_error_check CHECK (
        (result = 'success' AND error_code IS NULL)
        OR (
            result IN ('failure', 'compensation_required')
            AND error_code IS NOT NULL
            AND length(error_code) > 0
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_audit_events_correlation_created
    ON audit_events(correlation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_audit_events_root_correlation_created
    ON audit_events(root_correlation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_audit_events_target_created
    ON audit_events(target_type, target_id, created_at);

-- Table: workspace_knowledge_base_attachments
CREATE TABLE IF NOT EXISTS workspace_knowledge_base_attachments (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kb_id varchar(64) NOT NULL REFERENCES knowledge_bases(id) ON DELETE RESTRICT,
    mount_alias varchar(255) NOT NULL,
    attached_by_id varchar(128) REFERENCES users(id) ON DELETE SET NULL,
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
COMMENT ON COLUMN workspace_knowledge_base_attachments.attached_by_id IS 'User ID that attached the knowledge base';
COMMENT ON COLUMN workspace_knowledge_base_attachments.created_at IS 'Attachment creation time';
COMMENT ON COLUMN workspace_knowledge_base_attachments.updated_at IS 'Attachment last update time';

-- Table: automation_jobs
CREATE TABLE IF NOT EXISTS automation_jobs (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    creator_user_id varchar(128) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name varchar(255) NOT NULL,
    description text,
    prompt text NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    trigger varchar(32) NOT NULL CHECK (trigger IN ('cron', 'manual', 'webhook', 'at', 'every')),
    schedule varchar(255) NOT NULL,
    exact boolean DEFAULT false NOT NULL,
    agentic_tool varchar(32) NOT NULL,
    model varchar(128) NOT NULL,
    agent_config jsonb NOT NULL,
    worktree_key text NOT NULL,
    worktree_branch text NOT NULL,
    notification_config jsonb NOT NULL,
    next_run_at timestamp with time zone,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE automation_jobs IS '自動化任務配置表';
COMMENT ON COLUMN automation_jobs.id IS '自動化任務唯一識別碼';
COMMENT ON COLUMN automation_jobs.name IS '自動化任務名稱';
COMMENT ON COLUMN automation_jobs.description IS '自動化任務描述';
COMMENT ON COLUMN automation_jobs.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN automation_jobs.creator_user_id IS '任務建立者用戶 ID';
COMMENT ON COLUMN automation_jobs.prompt IS '任務提示或內容';
COMMENT ON COLUMN automation_jobs.status IS '任務狀態（active, paused, completed）';
COMMENT ON COLUMN automation_jobs.trigger IS '觸發條件（cron, manual, webhook, at, every）';
COMMENT ON COLUMN automation_jobs.schedule IS '排程表達式（使用系統時區）';
COMMENT ON COLUMN automation_jobs.exact IS '是否精準依排程執行，不套用分散抖動';
COMMENT ON COLUMN automation_jobs.agentic_tool IS 'Agentic tool ID';
COMMENT ON COLUMN automation_jobs.model IS 'Agent model ID';
COMMENT ON COLUMN automation_jobs.agent_config IS 'Typed agent configuration';
COMMENT ON COLUMN automation_jobs.worktree_key IS 'Deterministic worktree identity';
COMMENT ON COLUMN automation_jobs.worktree_branch IS 'Deterministic worktree branch';
COMMENT ON COLUMN automation_jobs.notification_config IS 'Typed notification configuration';
COMMENT ON COLUMN automation_jobs.next_run_at IS '下次計劃執行時間';
COMMENT ON COLUMN automation_jobs.deleted_at IS 'Soft deletion time';

-- Table: automation_executions
CREATE TABLE IF NOT EXISTS automation_executions (
    id varchar(64) PRIMARY KEY,
    job_id varchar(64) NOT NULL REFERENCES automation_jobs(id) ON DELETE CASCADE,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    status varchar(16) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'success', 'failed', 'cancelled')),
    trigger varchar(32) NOT NULL CHECK (trigger IN ('cron', 'manual', 'webhook', 'at', 'every')),
    scheduled_for timestamp with time zone NOT NULL,
    queued_at timestamp with time zone,
    runner_instance_id varchar(128),
    claim_request_id varchar(128),
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    cancel_requested_at timestamp with time zone,
    principal_user_id_snapshot varchar(128) NOT NULL,
    prompt_snapshot text NOT NULL,
    agentic_tool_snapshot varchar(32) NOT NULL,
    model_snapshot varchar(128) NOT NULL,
    agent_config_snapshot jsonb NOT NULL,
    worktree_key_snapshot text NOT NULL,
    error_code varchar(128),
    error_message text,
    notification_status varchar(16) CHECK (notification_status IN ('delivered', 'failed')),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE automation_executions IS 'Automation execution lifecycle and immutable snapshots';

CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_executions_running_job
    ON automation_executions (job_id)
    WHERE status = 'running';
CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_executions_claim_request
    ON automation_executions (workspace_id, claim_request_id)
    WHERE claim_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_automation_executions_workspace_claim
    ON automation_executions (workspace_id, status, scheduled_for, id);
CREATE INDEX IF NOT EXISTS ix_automation_executions_job_fifo
    ON automation_executions (job_id, status, scheduled_for, id);

-- Table: workspace_runtime_logs
CREATE TABLE IF NOT EXISTS workspace_runtime_logs (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    stage varchar(64) NOT NULL,
    message text NOT NULL,
    log_metadata json DEFAULT '{}'::json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE workspace_runtime_logs IS '工作區 Runtime 佈建日誌';
COMMENT ON COLUMN workspace_runtime_logs.id IS '日誌唯一識別碼';
COMMENT ON COLUMN workspace_runtime_logs.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN workspace_runtime_logs.stage IS '佈建階段';
COMMENT ON COLUMN workspace_runtime_logs.message IS '日誌訊息';
COMMENT ON COLUMN workspace_runtime_logs.log_metadata IS '日誌元數據（JSON格式）';
COMMENT ON COLUMN workspace_runtime_logs.created_at IS '日誌建立時間';

-- Table: workspace_firewall_sync_commands
CREATE TABLE IF NOT EXISTS workspace_firewall_sync_commands (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    firewall_revision bigint NOT NULL CHECK (firewall_revision >= 1),
    retry_of_command_id varchar(64) REFERENCES workspace_firewall_sync_commands(id) ON DELETE SET NULL,
    root_command_id varchar(64) NOT NULL REFERENCES workspace_firewall_sync_commands(id) ON DELETE CASCADE,
    status varchar(32) DEFAULT 'pending' NOT NULL CHECK (
        status IN ('pending', 'processing', 'delivered', 'superseded', 'failed')
    ),
    attempt_count integer DEFAULT 0 NOT NULL CHECK (attempt_count >= 0),
    next_attempt_at timestamp with time zone NOT NULL,
    lease_owner varchar(128),
    lease_expires_at timestamp with time zone,
    last_error_code varchar(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT workspace_firewall_sync_commands_lease_check CHECK (
        (status = 'processing' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (status <> 'processing' AND lease_owner IS NULL AND lease_expires_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_workspace_firewall_sync_commands_claim
    ON workspace_firewall_sync_commands (status, next_attempt_at, lease_expires_at);
CREATE INDEX IF NOT EXISTS ix_workspace_firewall_sync_commands_lineage
    ON workspace_firewall_sync_commands (
        workspace_id,
        firewall_revision,
        root_command_id,
        created_at
    );

COMMENT ON TABLE workspace_firewall_sync_commands IS 'Durable Workspace firewall desired-state delivery commands';

-- Table: workspace_runtime_jobs
CREATE TABLE IF NOT EXISTS workspace_runtime_jobs (
    id varchar(64) PRIMARY KEY,
    workspace_id varchar(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    operation varchar(32) NOT NULL,
    target_component varchar(16),
    strategy varchar(32) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'queued',
    retries integer DEFAULT 0 NOT NULL,
    target_revision bigint,
    target_runtime_instance_id uuid,
    correlation_id varchar(64) NOT NULL,
    root_correlation_id varchar(64) NOT NULL,
    job_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    lifecycle_job_id varchar(64) REFERENCES workspace_runtime_jobs(id) ON DELETE SET NULL,
    retry_of_job_id varchar(64) REFERENCES workspace_runtime_jobs(id) ON DELETE SET NULL,
    claim_token varchar(64),
    claim_expires_at timestamp with time zone,
    last_heartbeat_at timestamp with time zone,
    dispatch_attempts integer DEFAULT 0 NOT NULL,
    scheduled_at timestamp with time zone NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    error_code varchar(64),
    CONSTRAINT workspace_runtime_jobs_operation_check CHECK (
        operation IN (
            'knowledge_base_mount_reconcile',
            'workspace_access_recycle',
            'workspace_start',
            'workspace_stop',
            'workspace_delete',
            'runtime_restart',
            'browser_restart',
            'canvas_restart',
            'browser_credential_rotate'
        )
    ),
    CONSTRAINT workspace_runtime_jobs_target_component_check CHECK (
        target_component IS NULL OR target_component IN ('runtime', 'browser', 'canvas')
    ),
    CONSTRAINT workspace_runtime_jobs_operation_component_check CHECK (
        (operation = 'runtime_restart' AND target_component = 'runtime')
        OR (operation IN ('browser_restart', 'browser_credential_rotate')
            AND target_component = 'browser')
        OR (operation = 'canvas_restart' AND target_component = 'canvas')
        OR (operation NOT IN ('runtime_restart', 'browser_restart',
            'canvas_restart', 'browser_credential_rotate')
            AND target_component IS NULL)
    ),
    CONSTRAINT workspace_runtime_jobs_status_check CHECK (
        status IN ('queued', 'running', 'succeeded', 'failed', 'superseded')
    ),
    CONSTRAINT workspace_runtime_jobs_strategy_check CHECK (
        strategy IN ('docker', 'kubernetes')
    ),
    CONSTRAINT workspace_runtime_jobs_attempts_check CHECK (
        retries >= 0 AND dispatch_attempts >= 0
    ),
    CONSTRAINT workspace_runtime_jobs_target_revision_check CHECK (
        (operation IN ('knowledge_base_mount_reconcile', 'workspace_access_recycle')
            AND target_component IS NULL
            AND target_revision IS NOT NULL AND target_revision >= 0)
        OR (operation IN ('workspace_start', 'workspace_stop',
            'workspace_delete') AND target_component IS NULL
            AND target_revision IS NULL)
        OR (operation IN ('runtime_restart', 'browser_restart',
            'canvas_restart', 'browser_credential_rotate')
            AND target_component IS NOT NULL
            AND target_revision IS NOT NULL AND target_revision >= 1)
    ),
    CONSTRAINT workspace_runtime_jobs_state_fields_check CHECK (
        (status = 'queued' AND claim_token IS NULL
            AND claim_expires_at IS NULL AND last_heartbeat_at IS NULL
            AND started_at IS NULL AND finished_at IS NULL
            AND error_code IS NULL)
        OR (status = 'running' AND claim_token IS NOT NULL
            AND claim_expires_at IS NOT NULL AND last_heartbeat_at IS NOT NULL
            AND started_at IS NOT NULL AND finished_at IS NULL
            AND error_code IS NULL)
        OR (status IN ('succeeded', 'superseded') AND claim_token IS NULL
            AND claim_expires_at IS NULL AND finished_at IS NOT NULL
            AND error_code IS NULL)
        OR (status = 'failed' AND claim_token IS NULL
            AND claim_expires_at IS NULL AND finished_at IS NOT NULL
            AND error_code IS NOT NULL AND length(error_code) > 0)
    ),
    CONSTRAINT workspace_runtime_jobs_lifecycle_self_check CHECK (
        lifecycle_job_id IS NULL OR lifecycle_job_id <> id
    ),
    CONSTRAINT workspace_runtime_jobs_retry_self_check CHECK (
        retry_of_job_id IS NULL OR retry_of_job_id <> id
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_runtime_jobs_queued_workspace_operation
    ON workspace_runtime_jobs (workspace_id)
    WHERE status = 'queued'
      AND operation IN ('workspace_start', 'workspace_stop', 'workspace_delete');

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_runtime_jobs_running_workspace_operation
    ON workspace_runtime_jobs (workspace_id)
    WHERE status = 'running'
      AND operation IN ('workspace_start', 'workspace_stop', 'workspace_delete');

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_runtime_jobs_queued_component_operation
    ON workspace_runtime_jobs (workspace_id, target_component)
    WHERE status = 'queued' AND target_component IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_runtime_jobs_running_component_operation
    ON workspace_runtime_jobs (workspace_id, target_component)
    WHERE status = 'running' AND target_component IS NOT NULL;

COMMENT ON TABLE workspace_runtime_jobs IS '工作區 Runtime 背景任務排程';
COMMENT ON COLUMN workspace_runtime_jobs.id IS '任務唯一識別碼';
COMMENT ON COLUMN workspace_runtime_jobs.workspace_id IS '所屬工作區 ID';
COMMENT ON COLUMN workspace_runtime_jobs.operation IS '操作類型';
COMMENT ON COLUMN workspace_runtime_jobs.target_component IS 'Target component for component-scoped reconciliation';
COMMENT ON COLUMN workspace_runtime_jobs.strategy IS '執行策略';
COMMENT ON COLUMN workspace_runtime_jobs.status IS '任務狀態';
COMMENT ON COLUMN workspace_runtime_jobs.retries IS '重試次數';
COMMENT ON COLUMN workspace_runtime_jobs.target_revision IS 'Desired revision fenced by this job';
COMMENT ON COLUMN workspace_runtime_jobs.target_runtime_instance_id IS 'Execution-plane generation fenced by this job';
COMMENT ON COLUMN workspace_runtime_jobs.correlation_id IS 'Current attempt correlation ID';
COMMENT ON COLUMN workspace_runtime_jobs.root_correlation_id IS 'Root mutation correlation ID';
COMMENT ON COLUMN workspace_runtime_jobs.job_metadata IS 'Allowlisted job metadata';
COMMENT ON COLUMN workspace_runtime_jobs.lifecycle_job_id IS 'Durable lifecycle parent job ID';
COMMENT ON COLUMN workspace_runtime_jobs.retry_of_job_id IS 'Previous failed attempt job ID';
COMMENT ON COLUMN workspace_runtime_jobs.claim_token IS 'Current worker fencing token';
COMMENT ON COLUMN workspace_runtime_jobs.claim_expires_at IS 'Worker claim lease expiry';
COMMENT ON COLUMN workspace_runtime_jobs.last_heartbeat_at IS 'Most recent claim heartbeat';
COMMENT ON COLUMN workspace_runtime_jobs.dispatch_attempts IS 'Broker dispatch attempt count';
COMMENT ON COLUMN workspace_runtime_jobs.scheduled_at IS '計劃執行時間';
COMMENT ON COLUMN workspace_runtime_jobs.started_at IS '實際開始時間';
COMMENT ON COLUMN workspace_runtime_jobs.finished_at IS '完成時間';
COMMENT ON COLUMN workspace_runtime_jobs.error_code IS 'Stable failure code';

-- Table: marketplace_activities
CREATE TABLE IF NOT EXISTS marketplace_activities (
    id varchar(64) PRIMARY KEY,
    actor_user_id varchar(128) NOT NULL,
    operation_id varchar(64),
    workspace_id varchar(64) REFERENCES workspaces(id) ON DELETE SET NULL,
    provider varchar(32) CHECK (
        provider IS NULL OR provider IN ('claude-code', 'codex')
    ),
    package_id varchar(255),
    action varchar(32) NOT NULL CHECK (
        action IN ('install', 'copy', 'import', 'delete')
    ),
    status varchar(16) NOT NULL CHECK (
        status IN ('succeeded', 'failed')
    ),
    marketplace_id varchar(64),
    error_code varchar(128),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_marketplace_activities_workspace_created
    ON marketplace_activities (workspace_id, created_at, id);
CREATE INDEX IF NOT EXISTS ix_marketplace_activities_actor_created
    ON marketplace_activities (actor_user_id, created_at, id);

-- =====================================================
-- AI Chat Thread Tables
-- =====================================================

CREATE TABLE IF NOT EXISTS threads (
    id VARCHAR(36) PRIMARY KEY,
    workspace_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    origin VARCHAR(16) NOT NULL DEFAULT 'user',
    automation_job_id VARCHAR(36),
    automation_execution_id VARCHAR(36),
    title TEXT NOT NULL DEFAULT '',
    agentic_tool VARCHAR(32) NOT NULL,
    model VARCHAR(64) NOT NULL,
    claude_mode VARCHAR(16),
    status VARCHAR(16) NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    queued_messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    draft_message JSONB,
    active_turn_id VARCHAR(36),
    active_turn_execution_id VARCHAR(64),
    git_context_id VARCHAR(64),
    context_tokens INTEGER,
    context_window INTEGER,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    error_code VARCHAR(64),
    error_info JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_threads_workspace_id ON threads(workspace_id);
CREATE INDEX IF NOT EXISTS ix_threads_user_id ON threads(user_id);
CREATE INDEX IF NOT EXISTS ix_threads_origin ON threads(origin);
CREATE INDEX IF NOT EXISTS ix_threads_automation_job_id ON threads(automation_job_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_threads_automation_execution_id
    ON threads(automation_execution_id);
CREATE INDEX IF NOT EXISTS ix_threads_status ON threads(status);
CREATE INDEX IF NOT EXISTS ix_threads_archived ON threads(archived);

CREATE TABLE IF NOT EXISTS thread_turns (
    id VARCHAR(36) PRIMARY KEY,
    thread_id VARCHAR(36) NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    status VARCHAR(24) NOT NULL,
    error_code VARCHAR(64),
    error_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_thread_turns_sequence UNIQUE (thread_id, sequence)
);

CREATE INDEX IF NOT EXISTS ix_thread_turns_thread_sequence_desc
    ON thread_turns(thread_id, sequence DESC);

CREATE TABLE IF NOT EXISTS thread_turn_executions (
    id VARCHAR(64) PRIMARY KEY,
    turn_id VARCHAR(36) NOT NULL REFERENCES thread_turns(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    agentic_tool VARCHAR(32) NOT NULL,
    agent_resume_id VARCHAR(255),
    version BIGINT NOT NULL DEFAULT 1,
    status VARCHAR(24) NOT NULL,
    error_code VARCHAR(64),
    error_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_thread_turn_executions_sequence UNIQUE (turn_id, sequence)
);

CREATE INDEX IF NOT EXISTS ix_thread_turn_executions_turn_id
    ON thread_turn_executions(turn_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_threads_active_turn') THEN
        ALTER TABLE threads ADD CONSTRAINT fk_threads_active_turn
            FOREIGN KEY (active_turn_id) REFERENCES thread_turns(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_threads_active_turn_execution') THEN
        ALTER TABLE threads ADD CONSTRAINT fk_threads_active_turn_execution
            FOREIGN KEY (active_turn_execution_id) REFERENCES thread_turn_executions(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS thread_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id VARCHAR(36) NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    turn_id VARCHAR(36) NOT NULL REFERENCES thread_turns(id) ON DELETE CASCADE,
    turn_execution_id VARCHAR(64) NOT NULL REFERENCES thread_turn_executions(id) ON DELETE CASCADE,
    message_sequence BIGINT NOT NULL,
    type VARCHAR(16) NOT NULL,
    parent_tool_use_id BIGINT REFERENCES thread_messages(id) ON DELETE CASCADE,
    tool_call_key VARCHAR(255),
    source_event_key VARCHAR(255) NOT NULL,
    result_kind VARCHAR(32),
    content JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_thread_messages_sequence UNIQUE (thread_id, message_sequence),
    CONSTRAINT uq_thread_messages_execution_tool_call UNIQUE (turn_execution_id, tool_call_key),
    CONSTRAINT uq_thread_messages_execution_source_event UNIQUE (turn_execution_id, source_event_key),
    CONSTRAINT ck_thread_messages_result_kind CHECK (
        (type = 'tool_result' AND result_kind IN ('provider_result', 'interaction_answer'))
        OR (type <> 'tool_result' AND result_kind IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_thread_messages_thread_id
    ON thread_messages(thread_id);
CREATE INDEX IF NOT EXISTS ix_thread_messages_turn_sequence
    ON thread_messages(turn_id, message_sequence);
CREATE INDEX IF NOT EXISTS ix_thread_messages_execution_sequence
    ON thread_messages(turn_execution_id, message_sequence);
CREATE INDEX IF NOT EXISTS ix_thread_messages_timeline_anchors
    ON thread_messages(thread_id, message_sequence DESC)
    WHERE type IN (
        'user', 'agent_text', 'thinking', 'tool_call',
        'system', 'system_init', 'git_diff', 'error'
    );
CREATE UNIQUE INDEX IF NOT EXISTS uq_thread_messages_tool_result_kind
    ON thread_messages(parent_tool_use_id, result_kind)
    WHERE type = 'tool_result';

CREATE TABLE IF NOT EXISTS thread_tool_result_contents (
    message_id BIGINT PRIMARY KEY REFERENCES thread_messages(id) ON DELETE CASCADE,
    media_type VARCHAR(128) NOT NULL,
    payload BYTEA NOT NULL,
    byte_length BIGINT NOT NULL,
    line_count BIGINT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Platform resource observability and capacity governance
CREATE TABLE IF NOT EXISTS platform_resource_activity_events (
    event_id VARCHAR(128) PRIMARY KEY,
    resource_type VARCHAR(32) NOT NULL CHECK (resource_type IN ('workspace', 'knowledge_base')),
    resource_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    source VARCHAR(16) NOT NULL CHECK (source IN ('manager', 'runtime')),
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_platform_resource_activity_type_occurred
    ON platform_resource_activity_events(resource_type, occurred_at);
CREATE INDEX IF NOT EXISTS ix_platform_resource_activity_resource_occurred
    ON platform_resource_activity_events(resource_type, resource_id, occurred_at);

CREATE TABLE IF NOT EXISTS platform_resource_daily_active_resources (
    id BIGSERIAL PRIMARY KEY,
    local_date VARCHAR(10) NOT NULL,
    time_zone VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    first_occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT platform_resource_daily_active_unique
        UNIQUE (local_date, time_zone, resource_type, resource_id)
);
CREATE INDEX IF NOT EXISTS ix_platform_resource_daily_active_lookup
    ON platform_resource_daily_active_resources(resource_type, local_date);

CREATE TABLE IF NOT EXISTS platform_resource_daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    local_date VARCHAR(10) NOT NULL,
    time_zone VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    end_of_day_total INTEGER NOT NULL DEFAULT 0,
    created_count INTEGER NOT NULL DEFAULT 0,
    deleted_count INTEGER NOT NULL DEFAULT 0,
    active_count INTEGER NOT NULL DEFAULT 0,
    collection_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT platform_resource_daily_metric_unique
        UNIQUE (local_date, time_zone, resource_type)
);

CREATE TABLE IF NOT EXISTS resource_capacity_observations (
    id BIGSERIAL PRIMARY KEY,
    resource_type VARCHAR(32) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    storage_kind VARCHAR(32) NOT NULL CHECK (storage_kind IN ('workspace_data', 'runtime_home', 'knowledge_base')),
    used_bytes BIGINT NOT NULL,
    allocated_bytes BIGINT,
    host_available_bytes BIGINT,
    provisioner VARCHAR(32) NOT NULL,
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    measurement_source VARCHAR(32) NOT NULL,
    CONSTRAINT resource_capacity_observation_unique
        UNIQUE (resource_type, resource_id, storage_kind)
);
CREATE INDEX IF NOT EXISTS ix_resource_capacity_observation_resource
    ON resource_capacity_observations(resource_type, resource_id);

CREATE TABLE IF NOT EXISTS resource_capacity_daily_snapshots (
    id BIGSERIAL PRIMARY KEY,
    local_date VARCHAR(10) NOT NULL,
    time_zone VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    storage_kind VARCHAR(32) NOT NULL,
    used_bytes BIGINT NOT NULL,
    allocated_bytes BIGINT,
    host_available_bytes BIGINT,
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT resource_capacity_daily_snapshot_unique
        UNIQUE (local_date, time_zone, resource_type, resource_id, storage_kind)
);

CREATE TABLE IF NOT EXISTS platform_resource_capacity_daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    local_date VARCHAR(10) NOT NULL,
    time_zone VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    storage_kind VARCHAR(32) NOT NULL,
    used_bytes BIGINT NOT NULL DEFAULT 0,
    allocated_bytes BIGINT,
    unknown_count INTEGER NOT NULL DEFAULT 0,
    stale_count INTEGER NOT NULL DEFAULT 0,
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT platform_resource_capacity_daily_metric_unique
        UNIQUE (local_date, time_zone, resource_type, storage_kind)
);

CREATE TABLE IF NOT EXISTS workspace_storage_allocations (
    id BIGSERIAL PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    storage_kind VARCHAR(32) NOT NULL,
    desired_bytes BIGINT NOT NULL,
    observed_bytes BIGINT,
    revision BIGINT NOT NULL DEFAULT 1,
    observed_revision BIGINT NOT NULL DEFAULT 0,
    expansion_supported BOOLEAN,
    phase VARCHAR(16) NOT NULL DEFAULT 'completed',
    operator_error_code VARCHAR(64),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT workspace_storage_allocation_unique UNIQUE (workspace_id, storage_kind)
);

CREATE TABLE IF NOT EXISTS workspace_capacity_expansion_requests (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    storage_kind VARCHAR(32) NOT NULL,
    previous_bytes BIGINT NOT NULL,
    requested_bytes BIGINT NOT NULL,
    target_revision BIGINT NOT NULL,
    requested_by_user_id VARCHAR(128) NOT NULL,
    phase VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (phase IN ('pending', 'applying', 'completed', 'failed')),
    error_code VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_capacity_expansion_active
    ON workspace_capacity_expansion_requests(workspace_id, storage_kind)
    WHERE phase IN ('pending', 'applying');

-- Database level comment
-- Note: Removing problematic current_database() function call
