import type { HookActionConfig } from '@/shared/components/hook-workflow';
import type { AgentScope } from './documents';

export type AgentHookScope = AgentScope;
export type AgentHookActionConfig = HookActionConfig;

export interface AgentHookRuleConfig {
  matcher: string;
  hooks: AgentHookActionConfig[];
  pluginName?: string | null;
  marketplaceName?: string | null;
}

export type AgentHookRuleMap = Record<string, AgentHookRuleConfig[]>;

export interface AgentHookScopeDocument {
  scope: AgentHookScope;
  hooks: AgentHookRuleMap;
  revision?: string;
}

export interface AgentHookScopesResponse {
  workspaceId: string;
  scopes: AgentHookScopeDocument[];
}

export interface AgentHookScopeResponse {
  workspaceId: string;
  scope: AgentHookScope;
  hooks: AgentHookRuleMap;
  revision?: string;
}

export interface AgentHookDeleteResponse {
  workspaceId: string;
  scope: AgentHookScope;
  deleted: boolean;
  deletedAt: string;
}

export type AgentHookImportMode = 'merge' | 'replace';

export interface AgentHookImportPayload {
  mode: AgentHookImportMode;
  scopes: AgentHookScopeDocument[];
}

export interface AgentHookImportResponse {
  workspaceId: string;
  mode: AgentHookImportMode;
  imported: number;
  updated: number;
  skipped: number;
}

export interface AgentHookMatcher {
  matcher: string;
  hooks: AgentHookActionConfig[];
}

export interface AgentHookWithEvent {
  id: string;
  scope: AgentHookScope;
  eventName: string;
  matchers: AgentHookMatcher[];
  pluginName?: string;
  marketplaceName?: string;
  metadata?: Record<string, unknown>;
}

export interface AgentHookExportResponse {
  workspaceId: string;
  exportedAt: string;
  scopes: AgentHookScopeDocument[];
}

export interface HookEventOption {
  value: string;
  labelKey: string;
  optionKey: string;
}
