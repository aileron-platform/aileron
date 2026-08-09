import type { HookMatcher } from './hookTypes';
import {
  HOOK_EVENTS,
  createEmptyMatcher,
  getHookDefaults,
  getHookFieldSupport,
  type HookProvider,
} from './providerHookSpec';

export type HookScope = 'project' | 'user' | 'local' | 'plugin' | 'built_in' | 'session';

export interface HookDialogData {
  id: string;
  name?: string;
  scope: HookScope;
  eventName: string;
  matchers: HookMatcher[];
  pluginName?: string;
  marketplaceName?: string;
  pluginId?: string;
  trustState?: 'trusted' | 'untrusted' | 'modified' | 'mixed';
  trusted?: boolean;
  effective?: boolean;
  trustRevision?: string;
  generation?: number;
  readOnly?: boolean;
  source?: string;
  sourcePath?: string | null;
  rawContent?: string;
  metadata?: Record<string, unknown>;
}

export interface EventOption {
  value: string;
  label: string;
  description?: string;
}

export interface HookFormValues {
  id: string;
  name: string;
  scope: HookScope;
  eventName: string;
  matchers: HookMatcher[];
}

const DEFAULT_HOOK_SCOPES: HookScope[] = ['project', 'user', 'local'];

export const createHookDialogDefaultForm = (
  provider: HookProvider,
  eventName = HOOK_EVENTS[provider][0],
  scope: HookScope = 'project',
  name = '',
): HookFormValues => ({
  id: '',
  name,
  scope,
  eventName,
  matchers: [createEmptyMatcher(provider)],
});

export const getHookDialogScopeValues = (availableScopes?: HookScope[]): HookScope[] => {
  if (!availableScopes) {
    return DEFAULT_HOOK_SCOPES;
  }
  return DEFAULT_HOOK_SCOPES.filter((scope) => availableScopes.includes(scope));
};

export const hydrateHookDialogForm = (
  hook: HookDialogData,
  provider: HookProvider,
): HookFormValues => {
  const fieldSupport = getHookFieldSupport(provider);
  return {
    id: hook.id,
    name: hook.name ?? '',
    scope: hook.scope,
    eventName: hook.eventName,
    matchers: hook.matchers.map((matcher) => ({
      matcher: matcher.matcher,
      sequential: fieldSupport.sequential ? matcher.sequential : undefined,
      hooks: matcher.hooks.map((exec) => {
        const {
          name: _name,
          description: _description,
          statusMessage: _statusMessage,
          ...base
        } = exec;
        return {
          ...base,
          timeout: exec.timeout,
          ...(fieldSupport.actionMetadata ? {
            name: exec.name ?? '',
            description: exec.description ?? '',
          } : {}),
          ...(fieldSupport.statusMessage ? { statusMessage: exec.statusMessage ?? '' } : {}),
        };
      }),
    })),
  };
};

export const hasDuplicateHookDialogEvent = (
  existingHooks: HookDialogData[],
  eventName: string,
  scope: HookScope,
  isEdit: boolean,
): boolean => {
  if (isEdit) {
    return false;
  }
  return existingHooks.some(
    (existingHook) => existingHook.eventName === eventName && existingHook.scope === scope,
  );
};

export const isHookDialogActionValid = (action: HookMatcher['hooks'][number]): boolean => {
  if (action.type === 'http') {
    return Boolean(action.url.trim());
  }
  if (action.type === 'mcp_tool') {
    return Boolean(action.server.trim() && action.tool.trim());
  }
  if (action.type === 'prompt' || action.type === 'agent') {
    return Boolean(action.prompt.trim());
  }
  return Boolean(action.command.trim());
};

export const sanitizeHookDialogAction = (
  action: HookMatcher['hooks'][number],
  provider: HookProvider,
): HookMatcher['hooks'][number] => {
  const support = getHookFieldSupport(provider);
  const common = {
    ...(action.raw ?? {}),
    type: action.type,
    timeout: action.timeout,
    name: support.actionMetadata ? (action.name?.trim() || undefined) : undefined,
    description: support.actionMetadata ? (action.description?.trim() || undefined) : undefined,
    statusMessage: support.statusMessage ? (action.statusMessage?.trim() || undefined) : undefined,
    if: support.condition ? (action.if?.trim() || undefined) : undefined,
    once: support.once ? Boolean(action.once) : undefined,
    additionalContextLimit: support.additionalContextLimit && action.type === 'command'
      ? action.additionalContextLimit
      : undefined,
    commandWindows: support.commandWindows && action.type === 'command'
      ? action.commandWindows === null
        ? null
        : action.commandWindows?.trim() || undefined
      : undefined,
  };
  if (action.type === 'http') {
    return {
      ...common,
      type: 'http',
      url: action.url.trim(),
      headers: action.headers,
      allowedEnvVars: action.allowedEnvVars,
    };
  }
  if (action.type === 'mcp_tool') {
    return {
      ...common,
      type: 'mcp_tool',
      server: action.server.trim(),
      tool: action.tool.trim(),
      input: action.input,
    };
  }
  if (action.type === 'prompt') {
    return {
      ...common,
      type: 'prompt',
      prompt: action.prompt.trim(),
      model: action.model?.trim() || undefined,
    };
  }
  if (action.type === 'agent') {
    return {
      ...common,
      type: 'agent',
      prompt: action.prompt.trim(),
      model: action.model?.trim() || undefined,
    };
  }
  return {
    ...common,
    type: 'command',
    command: action.command.trim(),
    args: support.args ? action.args?.map((arg) => arg.trim()).filter(Boolean) : undefined,
    shell: support.shell ? (action.shell ?? getHookDefaults(provider).shell) : undefined,
    async: support.async ? Boolean(action.async) : undefined,
    asyncRewake: support.async ? Boolean(action.asyncRewake) : undefined,
  };
};

export const buildHookDialogSubmitPayload = (
  form: HookFormValues,
  provider: HookProvider,
  showNameField: boolean,
): HookDialogData => ({
  id: form.id,
  ...(showNameField ? { name: form.name.trim() } : {}),
  scope: form.scope,
  eventName: form.eventName,
  matchers: form.matchers
    .map((matcher) => ({
      matcher: matcher.matcher.trim() || '*',
      sequential: getHookFieldSupport(provider).sequential ? Boolean(matcher.sequential) : undefined,
      hooks: matcher.hooks
        .filter(isHookDialogActionValid)
        .map((hookAction) => sanitizeHookDialogAction(hookAction, provider)),
    }))
    .filter((matcher) => matcher.hooks.length > 0),
});
