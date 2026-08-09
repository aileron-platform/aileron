export type AgenticToolId = 'claude' | 'codex' | 'opencode';
export type AgentMode = 'execute' | 'plan';

export interface ToolCapability {
  id: AgenticToolId;
  models: string[];
  defaultModel: string;
  modes: AgentMode[] | null;
  defaultMode: AgentMode | null;
  contextWindow: number;
}

export interface WorkspaceCapabilities {
  tools: ToolCapability[];
  defaultTool: AgenticToolId;
}
