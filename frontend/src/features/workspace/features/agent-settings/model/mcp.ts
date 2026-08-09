import type { AgentScope } from './documents';

export type AgentMcpTransport = 'stdio' | 'sse' | 'http';

export type CodexPluginMcpApprovalMode = 'auto' | 'prompt' | 'writes' | 'approve';

export interface CodexPluginMcpPolicy {
  enabled: boolean;
  defaultToolsApprovalMode: CodexPluginMcpApprovalMode | null;
  enabledTools: string[] | null;
  disabledTools: string[] | null;
  tools: Record<string, {
    approvalMode: CodexPluginMcpApprovalMode | null;
  }>;
}

export interface AgentMcpServer {
  id: string;
  name: string;
  scope: AgentScope;
  transport: AgentMcpTransport;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
  revision?: string;
  pluginName?: string;
  marketplaceName?: string;
  serverId?: string;
  pluginId?: string;
  relativeSourcePath?: string;
  generation?: number;
  readOnly?: boolean;
  editable?: boolean;
  effective?: boolean;
  policy?: CodexPluginMcpPolicy;
  policyRevision?: string;
}
