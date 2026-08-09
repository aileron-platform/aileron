import type {
  DocumentResourceItem,
  DocumentResourceScope,
} from '@/shared/components/document-resource';

export type AgentDocument = DocumentResourceItem;
export type AgentScope = DocumentResourceScope;
export type AgentDocumentFormat = 'markdown' | 'toml' | 'yaml';

export type AgentFileCollection = 'skills';

export interface AgentFileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: AgentFileNode[];
  size?: number;
  modified?: string;
  content?: string;
  scope?: AgentScope;
  metadata?: Record<string, unknown>;
  pluginId?: string;
  pluginName?: string;
  marketplaceName?: string;
}

export interface AgentFileCollectionResponse {
  workspaceId?: string;
  scope?: AgentScope;
  nodes?: AgentFileNode[];
  tree?: AgentFileNode[];
}

export interface AgentFileResponse {
  data?: {
    content?: string;
    path?: string;
    scope?: AgentScope;
  };
  content?: string;
  path?: string;
  scope?: AgentScope;
}

export interface AgentFileCreatePayload {
  path: string;
  content?: string;
  type?: 'file' | 'directory';
  scope?: AgentScope;
}

export interface AgentFileUpdatePayload {
  content: string;
}

export interface AgentFileDeleteResponse {
  deleted: boolean;
  path?: string;
}

export interface AgentPluginSkillSummary {
  pluginName: string;
  marketplaceName: string;
  skillName: string;
}

export interface AgentPluginSkillsResponse {
  plugins: AgentPluginSkillSummary[];
}

export interface AgentSelectedFile {
  path: string;
  scope: Extract<AgentScope, 'project' | 'user' | 'plugin'>;
  pluginId?: string;
  pluginName?: string;
  marketplaceName?: string;
}
