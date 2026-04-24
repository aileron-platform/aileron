/**
 * Template 相關類型定義
 */

export type TemplateFeatureKey =
  | 'mcp'
  | 'commands'
  | 'hooks'
  | 'agentsMd'
  | 'agents'
  | 'outputStyle'
  | 'skills'
  | 'scripts';

export type CliType = 'claude-code' | 'codex' | 'gemini' | 'opencode';

export type TemplateStatus = 'draft' | 'released';


export interface TemplateAuthor {
  name: string;
  email?: string;
  url?: string;
}



// 功能與 CLI 類型的關聯（多對多）：集中管理，供前端 UI 與邏輯使用
export const FEATURE_DISPLAY_ORDER: TemplateFeatureKey[] = [
  'mcp',
  'commands',
  'hooks',
  'agentsMd',
  'agents',
  'outputStyle',
  'skills',
  'scripts',
];

export const FEATURE_CLI_MAP: Record<TemplateFeatureKey, CliType[]> = {
  mcp: ['claude-code', 'codex', 'gemini', 'opencode'],
  commands: ['claude-code', 'codex', 'gemini', 'opencode'],
  hooks: ['claude-code', 'codex', 'gemini', 'opencode'],
  agentsMd: ['claude-code', 'codex', 'gemini', 'opencode'],
  agents: ['claude-code', 'codex', 'gemini', 'opencode'],
  outputStyle: ['claude-code', 'codex', 'gemini', 'opencode'],
  skills: ['claude-code', 'codex', 'gemini', 'opencode'],
  scripts: ['claude-code', 'codex', 'gemini', 'opencode'],
};

export function listFeaturesForCli(cli: 'all' | CliType): TemplateFeatureKey[] {
  if (cli === 'all') return FEATURE_DISPLAY_ORDER;
  return FEATURE_DISPLAY_ORDER.filter(key => FEATURE_CLI_MAP[key].includes(cli));
}

export interface TemplateCategory {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  sortOrder?: number;
  isActive?: boolean;
}

export interface TemplateFileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  content?: string;
  children?: TemplateFileNode[];
}

export interface TemplateMcpServer {
  id: string;
  name: string;
  type: 'stdio' | 'http' | 'sse';
  command?: string;
  args?: string[];
  url?: string;
  description?: string;
  env?: Record<string, string>;
  headers?: Record<string, string>; // HTTP 標頭，僅在 HTTP/SSE 類型時使用
}

export interface TemplateCommand {
  id: string;
  fileName: string;
  content: string;
  description?: string;
}

export interface TemplateHook {
  id: string;
  name: string;
  event: string;
  matcher?: string;
  action: 'command' | 'script';
  command?: string;
  script?: string;
  timeout?: number;
}

export interface TemplateAgent {
  id: string;
  fileName: string;
  content: string;
  description?: string;
}

export interface TemplateOutputStyle {
  id: string;
  fileName: string;
  content: string;
  description?: string;
}

export interface TemplateFeatureFlags {
  hasMcp: boolean;
  hasCommands: boolean;
  hasHooks: boolean;
  hasAgentsMd: boolean;
  hasAgents: boolean;
  hasOutputStyle: boolean;
  hasSkills: boolean;
  hasScripts: boolean;
}

export interface Template {
  id: string;
  name: string;
  description?: string;
  author: TemplateAuthor;
  keywords: string[];
  version: string;
  cliType?: CliType;
  status: TemplateStatus;
  createdAt: string;
  updatedAt?: string;
  documentation?: string;
  agentsMd?: string;
  isActive?: boolean;
  initCommands?: string;
  mcpServers: TemplateMcpServer[];
  commands: TemplateCommand[];
  hooks: TemplateHook[];
  agents: TemplateAgent[];
  outputStyle: TemplateOutputStyle[];
  skills: TemplateFileNode[];
  scripts: TemplateFileNode[];
  categoryId?: string;
  categoryName?: string;
  // Feature 索引相關
  indexedFeatures?: TemplateFeatureKey[];
  featuresIndexedAt?: string;
}

export interface TemplateInstallOptions {
  mcp: boolean;
  commands: boolean;
  hooks: boolean;
  agentsMd: boolean;
  agents: boolean;
  outputStyle: boolean;
  skills: boolean;
  scripts: boolean;
}

export const TEMPLATE_INSTALLABLE_FEATURE_KEYS: TemplateFeatureKey[] = [
  'mcp',
  'commands',
  'hooks',
  'agentsMd',
  'agents',
  'outputStyle',
  'skills',
  'scripts',
];

export function listEnabledTemplateFeatures(options: TemplateInstallOptions): TemplateFeatureKey[] {
  return TEMPLATE_INSTALLABLE_FEATURE_KEYS.filter((key) => options[key]);
}

export interface TemplateSearchFilters {
  search?: string;
  categoryId?: string;
  feature?: TemplateFeatureKey | 'all';
  cliType?: CliType | 'all';
  keywords?: string[];
  page?: number;
  pageSize?: number;
}

export interface TemplateListResult {
  items: Template[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface TemplateWorkspaceTarget {
  id: string;
  name: string;
  description?: string;
  updatedAt: string;
  cliType?: CliType;
}

export interface ImportTemplateResult {
  template: Template;
  message?: string;
}
