/**
 * Agent Settings - 型別定義
 *
 * 支援多種 AI Agent 工具（Claude Code / Gemini / OpenCode / Codex）的設定系統
 */

import type { LucideIcon } from 'lucide-react';
import type { ClaudeScope } from '../claude-code/types';

/** 支援的 Agent 工具類型 */
export type AgentToolType = 'claude' | 'gemini' | 'opencode' | 'codex';

/** Scope 選項（用於指令檔案編輯器的 scope 切換） */
export interface AgentToolScopeOption {
  value: string;
  labelKey: string;
  icon: LucideIcon;
}

/** 指令檔案設定 */
export interface AgentToolMd {
  fileName: string;         // CLAUDE.md / GEMINI.md / AGENTS.md
  subViewId: string;        // claude-md / gemini-md / agents-md
  labelKey: string;
  scopes: AgentToolScopeOption[];
  apiEndpoint?: string;     // API 端點名稱，預設使用 subViewId
}

/** Hook 事件選項 */
export interface HookEventOption {
  value: string;
  labelKey: string;     // i18n key for display label
  optionKey: string;    // i18n key for dialog select option
}

/** Agent 工具設定物件 */
export interface AgentToolConfig {
  id: AgentToolType;
  navigationId: string;           // 側邊欄 feature id: 'claude-code' | 'gemini' | 'opencode' | 'codex'
  navigationLabelKey: string;
  navigationIcon: LucideIcon;
  agentsMd: AgentToolMd;
  availableSubViews: string[];
  apiPathPrefix: string;          // 'claude-code' | 'gemini' | 'opencode' | 'codex'
  availableScopes: ClaudeScope[];  // 此 Agent 工具支援的 scope 層級
  supportsToggle?: boolean;        // MCP server 啟用/停用切換，預設 true
  slashCommandFormat?: 'markdown' | 'toml';  // slash command 格式，預設 'markdown'
  i18nNamespace: string;            // 翻譯 key 前綴，如 'workspace.claudeCode' 或 'workspace.agentSettings.common'
  globalSettingsLabelKey: string;
  hookEvents?: HookEventOption[];  // 此 Agent 工具支援的 hook 事件清單
}

