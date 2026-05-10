import type { HookActionConfig, HookMatcher } from '@/shared/components/hook-workflow';
import type { MarketplaceProvider } from '@/shared/types/marketplace';

export type HookEventValue = string;
export type HookType = 'command' | 'http' | 'mcp_tool' | 'prompt' | 'agent';
export type HookEventI18nKind = 'label' | 'description';

export interface HookTypeFieldSupport {
  command: boolean;
  shell: boolean;
  async: boolean;
  url: boolean;
  headers: boolean;
  allowedEnvVars: boolean;
  server: boolean;
  tool: boolean;
  input: boolean;
  prompt: boolean;
  model: boolean;
}

export interface HookTimeoutDefault {
  default: number;
  max: number;
  unit: 's' | 'ms';
}

export interface HookFieldSupport {
  sequential: boolean;
  actionMetadata: boolean;
  condition: boolean;
  async: boolean;
  shell: boolean;
  statusMessage: boolean;
  once: boolean;
}

export interface HookDefaults {
  timeout: number;
  timeoutUnit: 's' | 'ms';
  timeoutMax: number;
  shell?: 'bash' | 'powershell';
}

export const HOOK_EVENTS: Record<MarketplaceProvider, readonly HookEventValue[]> = {
  'claude-code': [
    'SessionStart',
    'Setup',
    'SessionEnd',
    'UserPromptSubmit',
    'UserPromptExpansion',
    'PreToolUse',
    'PostToolUse',
    'PostToolUseFailure',
    'PostToolBatch',
    'PermissionRequest',
    'PermissionDenied',
    'Stop',
    'StopFailure',
    'SubagentStart',
    'SubagentStop',
    'TeammateIdle',
    'TaskCreated',
    'TaskCompleted',
    'ConfigChange',
    'CwdChanged',
    'FileChanged',
    'InstructionsLoaded',
    'PreCompact',
    'PostCompact',
    'WorktreeCreate',
    'WorktreeRemove',
    'Notification',
    'Elicitation',
    'ElicitationResult',
  ],
  gemini: [
    'BeforeTool',
    'AfterTool',
    'BeforeAgent',
    'AfterAgent',
    'BeforeModel',
    'AfterModel',
    'BeforeToolSelection',
    'SessionStart',
    'SessionEnd',
    'PreCompress',
    'Notification',
  ],
  codex: [
    'SessionStart',
    'PreToolUse',
    'PostToolUse',
    'PermissionRequest',
    'UserPromptSubmit',
    'Stop',
  ],
};

export const HOOK_TYPES: Record<MarketplaceProvider, readonly HookType[]> = {
  'claude-code': ['command', 'http', 'mcp_tool', 'prompt', 'agent'],
  gemini: ['command'],
  codex: ['command'],
};

export const HOOK_TYPE_FIELDS: Record<HookType, HookTypeFieldSupport> = {
  command: { command: true, shell: true, async: true, url: false, headers: false, allowedEnvVars: false, server: false, tool: false, input: false, prompt: false, model: false },
  http: { command: false, shell: false, async: false, url: true, headers: true, allowedEnvVars: true, server: false, tool: false, input: false, prompt: false, model: false },
  mcp_tool: { command: false, shell: false, async: false, url: false, headers: false, allowedEnvVars: false, server: true, tool: true, input: true, prompt: false, model: false },
  prompt: { command: false, shell: false, async: false, url: false, headers: false, allowedEnvVars: false, server: false, tool: false, input: false, prompt: true, model: true },
  agent: { command: false, shell: false, async: false, url: false, headers: false, allowedEnvVars: false, server: false, tool: false, input: false, prompt: true, model: true },
};

export const HOOK_TIMEOUT_DEFAULTS: Record<MarketplaceProvider, Partial<Record<HookType, HookTimeoutDefault>>> = {
  'claude-code': {
    command: { default: 600, max: 3600, unit: 's' },
    http: { default: 30, max: 600, unit: 's' },
    mcp_tool: { default: 60, max: 600, unit: 's' },
    prompt: { default: 30, max: 600, unit: 's' },
    agent: { default: 60, max: 1800, unit: 's' },
  },
  gemini: { command: { default: 60000, max: 600000, unit: 'ms' } },
  codex: { command: { default: 60, max: 3600, unit: 's' } },
};

export const HOOK_FIELD_SUPPORT: Record<MarketplaceProvider, HookFieldSupport> = {
  'claude-code': { sequential: false, actionMetadata: false, condition: true, async: true, shell: true, statusMessage: true, once: false },
  gemini: { sequential: true, actionMetadata: true, condition: false, async: false, shell: false, statusMessage: false, once: false },
  codex: { sequential: false, actionMetadata: false, condition: false, async: false, shell: false, statusMessage: true, once: false },
};

export const HOOK_DEFAULTS: Record<MarketplaceProvider, HookDefaults> = {
  'claude-code': { timeout: 600, timeoutUnit: 's', timeoutMax: 3600, shell: 'bash' },
  gemini: { timeout: 60000, timeoutUnit: 'ms', timeoutMax: 600000 },
  codex: { timeout: 60, timeoutUnit: 's', timeoutMax: 3600 },
};

export const HOOK_EVENT_GROUPS: Record<MarketplaceProvider, Array<{ groupKey: string; events: readonly string[] }>> = {
  'claude-code': [
    { groupKey: 'session-lifecycle', events: ['SessionStart', 'Setup', 'SessionEnd'] },
    { groupKey: 'user-input', events: ['UserPromptSubmit', 'UserPromptExpansion'] },
    { groupKey: 'tool-loop', events: ['PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'PostToolBatch', 'PermissionRequest', 'PermissionDenied'] },
    { groupKey: 'permission-planning', events: ['Stop', 'StopFailure'] },
    { groupKey: 'agent-teams', events: ['SubagentStart', 'SubagentStop', 'TeammateIdle'] },
    { groupKey: 'task-management', events: ['TaskCreated', 'TaskCompleted'] },
    { groupKey: 'config-environment', events: ['ConfigChange', 'CwdChanged', 'FileChanged', 'InstructionsLoaded'] },
    { groupKey: 'context-compaction', events: ['PreCompact', 'PostCompact'] },
    { groupKey: 'worktrees', events: ['WorktreeCreate', 'WorktreeRemove'] },
    { groupKey: 'notifications-mcp', events: ['Notification', 'Elicitation', 'ElicitationResult'] },
  ],
  gemini: [{ groupKey: 'generic', events: HOOK_EVENTS.gemini }],
  codex: [{ groupKey: 'generic', events: HOOK_EVENTS.codex }],
};

export interface HookEventMatcherHint {
  supportsMatcher: boolean;
  examplesKey?: string;
  helpKey?: string;
}

const matcherlessEvents = new Set(['UserPromptSubmit', 'PostToolBatch', 'Stop', 'TeammateIdle', 'TaskCreated', 'TaskCompleted', 'WorktreeCreate', 'WorktreeRemove', 'CwdChanged']);
const toolMatcherEvents = new Set(['PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'PermissionRequest', 'PermissionDenied']);

export const EVENTS_WITH_CONDITION_SUPPORT = new Set(['PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'PermissionRequest', 'PermissionDenied']);

export const isConditionSupportedForEvent = (event: string): boolean => EVENTS_WITH_CONDITION_SUPPORT.has(event);

export const HOOK_EVENT_MATCHER_HINTS: Record<string, HookEventMatcherHint> = Object.fromEntries(
  HOOK_EVENTS['claude-code'].map(event => [
    event,
    matcherlessEvents.has(event)
      ? { supportsMatcher: false, helpKey: 'unsupported' }
      : { supportsMatcher: true, examplesKey: toolMatcherEvents.has(event) ? 'tool' : event, helpKey: toolMatcherEvents.has(event) ? 'tool' : 'generic' },
  ]),
);

export const getHookFieldSupport = (provider: MarketplaceProvider): HookFieldSupport => HOOK_FIELD_SUPPORT[provider];

export const getHookDefaults = (provider: MarketplaceProvider): HookDefaults => HOOK_DEFAULTS[provider];

export const getHookTimeoutDefault = (provider: MarketplaceProvider, type: HookType = 'command'): HookTimeoutDefault => (
  HOOK_TIMEOUT_DEFAULTS[provider][type] ?? HOOK_TIMEOUT_DEFAULTS[provider].command ?? { default: HOOK_DEFAULTS[provider].timeout, max: HOOK_DEFAULTS[provider].timeoutMax, unit: HOOK_DEFAULTS[provider].timeoutUnit }
);

export const isValidEventForProvider = (provider: MarketplaceProvider, event: string): boolean => (
  HOOK_EVENTS[provider].includes(event)
);

export const getHookEventI18nKey = (eventName: string, kind: HookEventI18nKind): string => (
  `common.hookEvents.${eventName}.${kind}`
);

export const createEmptyExecution = (provider: MarketplaceProvider, type: HookType = 'command'): HookActionConfig => {
  const timeout = getHookTimeoutDefault(provider, type);
  if (type === 'http') return { type, url: '', headers: {}, allowedEnvVars: [], timeout: timeout.default };
  if (type === 'mcp_tool') return { type, server: '', tool: '', input: {}, timeout: timeout.default };
  if (type === 'prompt') return { type, prompt: '', model: '', timeout: timeout.default };
  if (type === 'agent') return { type, prompt: '', model: '', timeout: timeout.default };
  return { type: 'command', command: '', timeout: timeout.default, shell: getHookDefaults(provider).shell };
};

export const migrateActionToType = (action: HookActionConfig, newType: HookType, provider: MarketplaceProvider): HookActionConfig => ({
  ...createEmptyExecution(provider, newType),
  name: action.name ?? undefined,
  description: action.description ?? undefined,
  if: action.if ?? undefined,
  statusMessage: action.statusMessage ?? undefined,
  once: action.once,
} as HookActionConfig);

export const createEmptyMatcher = (provider: MarketplaceProvider): HookMatcher => {
  const matcher: HookMatcher = { matcher: '', hooks: [createEmptyExecution(provider)] };
  if (getHookFieldSupport(provider).sequential) matcher.sequential = true;
  return matcher;
};

export const createEmptyHookValue = (provider: MarketplaceProvider): { name: string; event: string; matchers: HookMatcher[] } => ({
  name: '',
  event: HOOK_EVENTS[provider][0],
  matchers: [createEmptyMatcher(provider)],
});
