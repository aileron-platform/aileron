export type PromptInvocationTool = 'claude-code' | 'codex' | 'opencode';
export type PromptInvocationScope = 'project' | 'user' | 'plugin';
export type PromptInvocationKind = 'slash-command' | 'skill';
export type CatalogCompleteness = 'complete' | 'degraded';

export interface PromptInvocationItem {
  id: string;
  sourceKey: string;
  fileName: string;
  scope: PromptInvocationScope;
  kind: PromptInvocationKind;
  namespace?: string | null;
  pluginName?: string | null;
  displayName: string;
  category: string;
  description: string;
  invocation: string;
  tags: string[];
}

export interface PromptInvocationSourceError {
  source: string;
  errorCode: string;
  message: string;
}

export interface PromptInvocationCatalog {
  workspaceId: string;
  agenticTool: PromptInvocationTool;
  completeness: CatalogCompleteness;
  revision: string;
  availableScopes: PromptInvocationScope[];
  sourceErrors: PromptInvocationSourceError[];
  items: PromptInvocationItem[];
}

export const toPromptInvocationTool = (agenticTool: string): PromptInvocationTool => (
  agenticTool === 'claude' ? 'claude-code' : agenticTool as PromptInvocationTool
);
