export type HookType = 'command' | 'http' | 'mcp_tool' | 'prompt' | 'agent';

export interface BaseHookAction {
  type: HookType;
  name?: string | null;
  description?: string | null;
  timeout?: number;
  statusMessage?: string | null;
  if?: string | null;
  once?: boolean;
  raw?: Record<string, unknown>;
}

export interface CommandHookAction extends BaseHookAction {
  type: 'command';
  command: string;
  args?: string[];
  async?: boolean;
  asyncRewake?: boolean;
  shell?: 'bash' | 'powershell' | null;
  commandWindows?: string | null;
  additionalContextLimit?: number | null;
}

export interface HttpHookAction extends BaseHookAction {
  type: 'http';
  url: string;
  headers?: Record<string, string>;
  allowedEnvVars?: string[];
}

export interface McpToolHookAction extends BaseHookAction {
  type: 'mcp_tool';
  server: string;
  tool: string;
  input?: Record<string, unknown>;
}

export interface PromptHookAction extends BaseHookAction {
  type: 'prompt';
  prompt: string;
  model?: string | null;
}

export interface AgentHookAction extends BaseHookAction {
  type: 'agent';
  prompt: string;
  model?: string | null;
}

export type HookActionConfig =
  | CommandHookAction
  | HttpHookAction
  | McpToolHookAction
  | PromptHookAction
  | AgentHookAction;

export interface HookMatcher {
  matcher: string;
  sequential?: boolean;
  hooks: HookActionConfig[];
  raw?: Record<string, unknown>;
}
