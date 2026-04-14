/**
 * Claude Code 相關類型定義
 * 對應 workspace-runtime 的 Claude Code 模組
 */

// ============================================================================
// Scope 類型
// ============================================================================

export type ClaudeScope = 'project' | 'user' | 'local' | 'plugin';
export type ClaudeHookScope = 'project' | 'user' | 'local' | 'plugin';
export type ClaudeMdScope = 'project' | 'user' | 'plugin';

// ============================================================================
// Document 類型
// ============================================================================

export interface ClaudeDocument {
  id: string;
  workspaceId?: string;
  scope: ClaudeScope;
  title: string;
  description?: string;
  content: string;
  size?: string;
  metadata?: Record<string, unknown>;

  // Plugin 來源資訊（當 scope='plugin' 時有值）
  pluginName?: string;
  marketplaceName?: string;
}

// ============================================================================
// Permission 類型
// ============================================================================

export type PermissionAction = 'read' | 'write' | 'delete' | 'execute';
export type PermissionResource = 'file-system' | 'network' | 'settings' | 'tools';
export type PermissionPolicy = 'default' | 'restricted' | 'developer';

export interface PermissionRule {
  resource: PermissionResource;
  action: PermissionAction;
  allowed: boolean;
  description?: string;
}

export interface ClaudePermission {
  scope: ClaudeScope;
  policy: PermissionPolicy;
  allowRules: string[];
  denyRules: string[];
  rules: PermissionRule[];
}

// ============================================================================
// Hook 類型
// ============================================================================

export type HookActionType = 'command' | 'webhook' | 'mcp_call';

export interface HookAction {
  type: HookActionType;
  command?: string | null;
  timeout?: number | null;
}

export interface HookRule {
  matcher: string;
  hooks: HookAction[];

  // Plugin 來源資訊（用於顯示單一 rule 的來源）
  pluginName?: string;
  marketplaceName?: string;
}

export interface ClaudeHook {
  scope: ClaudeHookScope;
  hooks: Record<string, HookRule[]>;

  // Plugin 來源資訊（當 scope='plugin' 時有值）
  pluginName?: string;
  marketplaceName?: string;
}

// ============================================================================
// Usage Stats 類型
// ============================================================================

export interface UsageMetrics {
  totalRequests: number;
  totalTokens: number;
  monthlyQuota: number;
  quotaUsed: number;
  lastReset?: string;
}

export interface ClaudeUsageStats {
  metrics: UsageMetrics;
}

// ============================================================================
// MCP 類型
// ============================================================================

export type ClaudeMcpTransport = 'stdio' | 'sse' | 'http';

export interface ClaudeMcpServer {
  id: string;
  name: string;
  scope: ClaudeScope;
  transport: ClaudeMcpTransport;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;

  // Plugin 來源資訊（當 scope='plugin' 時有值）
  pluginName?: string;
  marketplaceName?: string;
}

// ============================================================================
// Slash Command 類型
// ============================================================================

export interface SlashCommandDocument {
  fileName: string;
  namespace?: string | null;
  description?: string | null;
  scope: ClaudeScope;
  size: string;
  content?: string;

  // Plugin 來源資訊（當 scope='plugin' 時有值）
  pluginName?: string;
  marketplaceName?: string;
}

export interface SlashCommandScopeGroup {
  scope: ClaudeScope;
  documents: SlashCommandDocument[];
}

// ============================================================================
// Subagent 類型
// ============================================================================

export interface SubagentDocument {
  fileName: string;
  description?: string | null;
  scope: ClaudeScope;
  size: string;
  content?: string;

  // Plugin 來源資訊（當 scope='plugin' 時有值）
  pluginName?: string;
  marketplaceName?: string;
}

export interface SubagentScopeGroup {
  scope: ClaudeScope;
  documents: SubagentDocument[];
}

