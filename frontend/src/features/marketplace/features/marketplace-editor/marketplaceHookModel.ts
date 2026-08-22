import {
  HOOK_EVENTS,
  HOOK_EVENT_MATCHER_HINTS,
  HOOK_TYPES,
  createEmptyMatcher,
  getHookDefaults,
  getHookDialogScopeValues,
  getHookFieldSupport,
  isValidEventForProvider as isValidEventForTargetClient,
  type HookActionConfig,
  type HookDialogLabels,
  type HookDialogOptions,
  type HookMatcher,
} from '@/shared/components/hook-workflow';
import type { MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';

import {
  marketplaceEditorItemTitle,
  type MarketplaceEditorResourceItem,
} from './marketplaceEditorResourceItems';

type HookDialogTranslator = (key: string) => string;

export interface MarketplaceHookDialogValue {
  name: string;
  event: string;
  matchers: HookMatcher[];
}

export const MARKETPLACE_HOOK_SOURCE_ID = '__marketplaceSourceId';
export const MARKETPLACE_HOOK_SOURCE_PATH = '__marketplaceSourcePath';
export const MARKETPLACE_HOOK_SOURCE_POINTER = '__marketplaceSourcePointer';
export const MARKETPLACE_HOOK_SOURCE_EVENT = '__marketplaceSourceEvent';

export const createMarketplaceHookDialogLabels = (
  t: HookDialogTranslator,
  targetClient: MarketplaceTargetClient,
  mode: 'create' | 'edit',
): HookDialogLabels => {
  const fieldSupport = getHookFieldSupport(targetClient);
  const defaults = getHookDefaults(targetClient);

  return {
    title: t(`marketplace.editor.hooks.dialog.${mode === 'edit' ? 'title' : 'titleCreate'}`),
    description: t(`marketplace.editor.hooks.dialog.description.${targetClient}`),
    cancel: t('marketplace.common.actions.cancel'),
    submit: t('marketplace.editor.hooks.dialog.actions.save'),
    name: {
      label: t('marketplace.editor.hooks.dialog.fields.name.label'),
      placeholder: t('marketplace.editor.hooks.dialog.fields.name.placeholder'),
    },
    scope: {
      label: t('marketplace.editor.hooks.dialog.scope.label'),
      requiredLabel: t('marketplace.editor.hooks.dialog.fields.scope.label'),
      placeholder: t('marketplace.editor.hooks.dialog.scope.placeholder'),
    },
    event: {
      label: t('marketplace.editor.hooks.dialog.fields.event.label'),
      placeholder: t('marketplace.editor.hooks.dialog.fields.event.placeholder'),
    },
    invalidActionWarning: t('marketplace.editor.hooks.dialog.validation.commandRequired'),
    matcherActions: {
      matcherSectionTitle: t('marketplace.editor.hooks.dialog.matchers.title'),
      matcherAdd: t('marketplace.editor.hooks.dialog.matchers.add'),
      matcherPatternLabel: t('marketplace.editor.hooks.dialog.matchers.patternLabel'),
      matcherPatternPlaceholder: t('marketplace.editor.hooks.dialog.matchers.patternPlaceholder'),
      matcherPatternHelp: (eventName) => {
        const matcherHint = HOOK_EVENT_MATCHER_HINTS[eventName];
        return [
          t(`marketplace.editor.hooks.dialog.matcherHints.${matcherHint?.helpKey ?? 'generic'}.help`),
          `- ${t(`marketplace.editor.hooks.dialog.matcherHints.${matcherHint?.examplesKey ?? 'generic'}.example`)}`,
        ];
      },
      matcherUnsupportedMessage: t('marketplace.editor.hooks.dialog.matchers.unsupported'),
      matcherSequentialLabel: fieldSupport.sequential
        ? t('marketplace.editor.hooks.dialog.matchers.sequentialLabel')
        : undefined,
      matcherSequentialHelp: fieldSupport.sequential
        ? t('marketplace.editor.hooks.dialog.matchers.sequentialHelp')
        : undefined,
      matcherRemove: t('marketplace.common.actions.remove'),
      executionSectionTitle: t('marketplace.editor.hooks.dialog.executions.title'),
      executionAdd: t('marketplace.editor.hooks.dialog.executions.add'),
      executionTypeLabel: t('marketplace.editor.hooks.dialog.executions.typeLabel'),
      ...(fieldSupport.actionMetadata ? {
        executionNameLabel: t('marketplace.editor.hooks.dialog.executions.nameLabel'),
        executionNamePlaceholder: t('marketplace.editor.hooks.dialog.executions.namePlaceholder'),
        executionNameHelp: t('marketplace.editor.hooks.dialog.executions.nameHelp'),
        executionDescriptionLabel: t('marketplace.editor.hooks.dialog.executions.descriptionLabel'),
        executionDescriptionPlaceholder: t('marketplace.editor.hooks.dialog.executions.descriptionPlaceholder'),
        executionDescriptionHelp: t('marketplace.editor.hooks.dialog.executions.descriptionHelp'),
      } : {}),
      executionTimeoutLabel: t(`marketplace.editor.hooks.dialog.executions.timeoutLabel.${targetClient}`),
      executionTimeoutPlaceholder: String(defaults.timeout),
      executionTimeoutHelp: t(`marketplace.editor.hooks.dialog.executions.timeoutHelp.${targetClient}`),
      executionCommandLabel: t(`marketplace.editor.hooks.dialog.executions.commandLabel.${targetClient}`),
      executionCommandPlaceholder: t(`marketplace.editor.hooks.dialog.executions.commandPlaceholder.${targetClient}`),
      executionCommandHelp: t(`marketplace.editor.hooks.dialog.executions.commandHelp.${targetClient}`),
      executionAdditionalContextLimitLabel: fieldSupport.additionalContextLimit
        ? t('marketplace.editor.hooks.dialog.executions.additionalContextLimit.label')
        : undefined,
      executionAdditionalContextLimitPlaceholder: fieldSupport.additionalContextLimit
        ? t('marketplace.editor.hooks.dialog.executions.additionalContextLimit.placeholder')
        : undefined,
      executionAdditionalContextLimitHelp: fieldSupport.additionalContextLimit
        ? t('marketplace.editor.hooks.dialog.executions.additionalContextLimit.help')
        : undefined,
      executionCommandWindowsLabel: fieldSupport.commandWindows
        ? t('marketplace.editor.hooks.dialog.executions.commandWindows.label')
        : undefined,
      executionCommandWindowsPlaceholder: fieldSupport.commandWindows
        ? t('marketplace.editor.hooks.dialog.executions.commandWindows.placeholder')
        : undefined,
      executionCommandWindowsHelp: fieldSupport.commandWindows
        ? t('marketplace.editor.hooks.dialog.executions.commandWindows.help')
        : undefined,
      ...(fieldSupport.statusMessage ? {
        executionStatusMessageLabel: t('marketplace.editor.hooks.dialog.executions.statusMessageLabel'),
        executionStatusMessagePlaceholder: t('marketplace.editor.hooks.dialog.executions.statusMessagePlaceholder'),
        executionStatusMessageHelp: t('marketplace.editor.hooks.dialog.executions.statusMessageHelp'),
      } : {}),
      executionUrlLabel: t('marketplace.editor.hooks.dialog.executions.url.label'),
      executionUrlPlaceholder: t('marketplace.editor.hooks.dialog.executions.url.placeholder'),
      executionUrlHelp: t('marketplace.editor.hooks.dialog.executions.url.help'),
      executionHeadersLabel: t('marketplace.editor.hooks.dialog.executions.headers.label'),
      executionHeadersHelp: t('marketplace.editor.hooks.dialog.executions.headers.help'),
      executionHeaderKeyPlaceholder: t('marketplace.editor.hooks.dialog.executions.headers.keyPlaceholder'),
      executionHeaderValuePlaceholder: t('marketplace.editor.hooks.dialog.executions.headers.valuePlaceholder'),
      executionHeadersAdd: t('marketplace.editor.hooks.dialog.executions.headers.add'),
      executionHeadersRemove: t('marketplace.editor.hooks.dialog.executions.headers.remove'),
      executionAllowedEnvVarsLabel: t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.label'),
      executionAllowedEnvVarsPlaceholder: t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.placeholder'),
      executionAllowedEnvVarsHelp: t('marketplace.editor.hooks.dialog.executions.allowedEnvVars.help'),
      executionServerLabel: t('marketplace.editor.hooks.dialog.executions.server.label'),
      executionServerPlaceholder: t('marketplace.editor.hooks.dialog.executions.server.placeholder'),
      executionServerHelp: t('marketplace.editor.hooks.dialog.executions.server.help'),
      executionToolLabel: t('marketplace.editor.hooks.dialog.executions.tool.label'),
      executionToolPlaceholder: t('marketplace.editor.hooks.dialog.executions.tool.placeholder'),
      executionToolHelp: t('marketplace.editor.hooks.dialog.executions.tool.help'),
      executionInputLabel: t('marketplace.editor.hooks.dialog.executions.input.label'),
      executionInputPlaceholder: t('marketplace.editor.hooks.dialog.executions.input.placeholder'),
      executionInputHelp: t('marketplace.editor.hooks.dialog.executions.input.help'),
      executionPromptLabel: t('marketplace.editor.hooks.dialog.executions.promptField.label'),
      executionPromptPlaceholder: t('marketplace.editor.hooks.dialog.executions.promptField.placeholder'),
      executionPromptHelp: t('marketplace.editor.hooks.dialog.executions.promptField.help'),
      executionModelLabel: t('marketplace.editor.hooks.dialog.executions.model.label'),
      executionModelPlaceholder: t('marketplace.editor.hooks.dialog.executions.model.placeholder'),
      executionModelHelp: t('marketplace.editor.hooks.dialog.executions.model.help'),
      executionConditionLabel: fieldSupport.condition
        ? t('marketplace.editor.hooks.dialog.executions.conditionLabel')
        : undefined,
      executionConditionPlaceholder: fieldSupport.condition
        ? t('marketplace.editor.hooks.dialog.executions.conditionPlaceholder')
        : undefined,
      executionConditionHelp: fieldSupport.condition
        ? t('marketplace.editor.hooks.dialog.executions.conditionHelp')
        : undefined,
      executionAsyncLabel: fieldSupport.async
        ? t('marketplace.editor.hooks.dialog.executions.asyncLabel')
        : undefined,
      executionAsyncRewakeLabel: fieldSupport.async
        ? t('marketplace.editor.hooks.dialog.executions.asyncRewakeLabel')
        : undefined,
      executionOnceLabel: undefined,
      executionOnceHelp: undefined,
      executionShellLabel: fieldSupport.shell
        ? t('marketplace.editor.hooks.dialog.executions.shellLabel')
        : undefined,
      executionShellPlaceholder: fieldSupport.shell
        ? t('marketplace.editor.hooks.dialog.executions.shellPlaceholder')
        : undefined,
      executionShellHelp: fieldSupport.shell
        ? t('marketplace.editor.hooks.dialog.executions.shellHelp')
        : undefined,
      executionRemove: t('marketplace.editor.hooks.dialog.executions.remove'),
    },
  };
};

export const createMarketplaceHookDialogOptions = (
  t: HookDialogTranslator,
  targetClient: MarketplaceTargetClient,
  events: HookDialogOptions['events'],
): HookDialogOptions => {
  const fieldSupport = getHookFieldSupport(targetClient);

  return {
    events,
    scopes: getHookDialogScopeValues().map((scope) => ({
      value: scope,
      label: t(`marketplace.editor.hooks.dialog.scope.options.${scope}`),
    })),
    executionTypes: HOOK_TYPES[targetClient].map((hookType) => ({
      value: hookType,
      label: t(`marketplace.editor.hooks.dialog.executions.types.${hookType}.label`),
      description: t(`marketplace.editor.hooks.dialog.executions.types.${hookType}.description`),
    })),
    executionShells: fieldSupport.shell ? [
      {
        value: 'bash',
        label: t('marketplace.editor.hooks.dialog.executions.shellOptions.bash'),
      },
      {
        value: 'powershell',
        label: t('marketplace.editor.hooks.dialog.executions.shellOptions.powershell'),
      },
    ] : undefined,
    showInvalidActionWarning: true,
  };
};

export const formatMarketplaceHookTimeout = (targetClient: MarketplaceTargetClient, timeout?: number): string => (
  getHookDefaults(targetClient).timeoutUnit === 'ms'
    ? `${timeout ?? getHookDefaults(targetClient).timeout}ms`
    : `${timeout ?? getHookDefaults(targetClient).timeout}s`
);

export const marketplaceHookDataFromValue = (
  value: MarketplaceHookDialogValue,
  source?: { sourceId: string; path: string; manifestPointer: string },
): Record<string, unknown> => ({
  name: value.name,
  event: value.event,
  matchers: value.matchers,
  ...(source ? {
    [MARKETPLACE_HOOK_SOURCE_ID]: source.sourceId,
    [MARKETPLACE_HOOK_SOURCE_PATH]: source.path,
    [MARKETPLACE_HOOK_SOURCE_POINTER]: source.manifestPointer,
  } : {}),
});

export const marketplaceHookNativeContent = (value: MarketplaceHookDialogValue): string => (
  JSON.stringify({ hooks: { [value.event]: value.matchers } }, null, 2)
);

export const marketplaceHookDialogValueFromItem = (
  item: MarketplaceEditorResourceItem,
  targetClient: MarketplaceTargetClient,
  t: (key: string) => string,
): MarketplaceHookDialogValue => {
  const data = item.data;
  const nativeContent = marketplaceHookDialogValueFromNativeContent(item.content, targetClient);
  const event = typeof data?.event === 'string' && isValidEventForTargetClient(targetClient, data.event)
    ? data.event
    : nativeContent?.event ?? HOOK_EVENTS[targetClient][0];
  const matchers = Array.isArray(data?.matchers)
    ? data.matchers as HookMatcher[]
    : nativeContent?.matchers ?? [createEmptyMatcher(targetClient)];

  return {
    name: typeof data?.name === 'string' ? data.name : marketplaceEditorItemTitle(item, t),
    event,
    matchers,
  };
};

const marketplaceHookDialogValueFromNativeContent = (
  content: string,
  targetClient: MarketplaceTargetClient,
): Pick<MarketplaceHookDialogValue, 'event' | 'matchers'> | null => {
  try {
    const parsed = JSON.parse(content) as unknown;
    if (!isMarketplaceRecord(parsed) || !isMarketplaceRecord(parsed.hooks)) return null;

    const hookEntry = Object.entries(parsed.hooks)
      .find(([event, value]) => isValidEventForTargetClient(targetClient, event) && Array.isArray(value));
    if (!hookEntry) return null;

    const [event, rawMatchers] = hookEntry;
    const matchers = (rawMatchers as unknown[])
      .map(rawMatcher => marketplaceHookMatcherFromNativeValue(rawMatcher, targetClient))
      .filter((matcher): matcher is HookMatcher => Boolean(matcher));

    return {
      event,
      matchers: matchers.length > 0 ? matchers : [createEmptyMatcher(targetClient)],
    };
  } catch {
    return null;
  }
};

const marketplaceHookMatcherFromNativeValue = (
  rawMatcher: unknown,
  targetClient: MarketplaceTargetClient,
): HookMatcher | null => {
  if (!isMarketplaceRecord(rawMatcher) || !Array.isArray(rawMatcher.hooks)) return null;

  const hooks = rawMatcher.hooks
    .map(rawAction => marketplaceHookActionFromNativeValue(rawAction, targetClient))
    .filter((action): action is HookActionConfig => Boolean(action));
  if (hooks.length === 0) return null;

  return {
    matcher: typeof rawMatcher.matcher === 'string' ? rawMatcher.matcher : '*',
    sequential: typeof rawMatcher.sequential === 'boolean' ? rawMatcher.sequential : undefined,
    hooks,
  };
};

const marketplaceHookActionFromNativeValue = (
  rawAction: unknown,
  targetClient: MarketplaceTargetClient,
): HookActionConfig | null => {
  if (!isMarketplaceRecord(rawAction)) return null;

  const actionType = typeof rawAction.type === 'string' && HOOK_TYPES[targetClient].includes(rawAction.type as HookActionConfig['type'])
    ? rawAction.type as HookActionConfig['type']
    : 'command';
  const timeout = typeof rawAction.timeout === 'number' ? rawAction.timeout : undefined;
  const common = {
    timeout,
    name: typeof rawAction.name === 'string' ? rawAction.name : undefined,
    description: typeof rawAction.description === 'string' ? rawAction.description : undefined,
    statusMessage: typeof rawAction.statusMessage === 'string' ? rawAction.statusMessage : undefined,
    if: typeof rawAction.if === 'string' ? rawAction.if : undefined,
    once: typeof rawAction.once === 'boolean' ? rawAction.once : undefined,
  };

  if (actionType === 'http') {
    return {
      ...common,
      type: 'http',
      url: typeof rawAction.url === 'string' ? rawAction.url : '',
      headers: marketplaceStringRecordFromValue(rawAction.headers),
      allowedEnvVars: Array.isArray(rawAction.allowedEnvVars)
        ? rawAction.allowedEnvVars.filter((value): value is string => typeof value === 'string')
        : undefined,
    };
  }
  if (actionType === 'mcp_tool') {
    return {
      ...common,
      type: 'mcp_tool',
      server: typeof rawAction.server === 'string' ? rawAction.server : '',
      tool: typeof rawAction.tool === 'string' ? rawAction.tool : '',
      input: isMarketplaceRecord(rawAction.input) ? rawAction.input : undefined,
    };
  }
  if (actionType === 'prompt' || actionType === 'agent') {
    return {
      ...common,
      type: actionType,
      prompt: typeof rawAction.prompt === 'string' ? rawAction.prompt : '',
      model: typeof rawAction.model === 'string' ? rawAction.model : undefined,
    };
  }

  return {
    ...common,
    type: 'command',
    command: typeof rawAction.command === 'string' ? rawAction.command : '',
    shell: rawAction.shell === 'bash' || rawAction.shell === 'powershell' ? rawAction.shell : undefined,
    async: typeof rawAction.async === 'boolean' ? rawAction.async : undefined,
    asyncRewake: typeof rawAction.asyncRewake === 'boolean' ? rawAction.asyncRewake : undefined,
  };
};

const isMarketplaceRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const marketplaceStringRecordFromValue = (value: unknown): Record<string, string> | undefined => {
  if (!isMarketplaceRecord(value)) return undefined;
  const entries = Object.entries(value).filter((entry): entry is [string, string] => typeof entry[1] === 'string');
  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
};

export const marketplaceHookResourceItemFromValue = (
  item: MarketplaceEditorResourceItem,
  targetClient: MarketplaceTargetClient,
  value: MarketplaceHookDialogValue,
  t: (key: string) => string,
): MarketplaceEditorResourceItem => {
  const firstMatcher = value.matchers[0];
  const firstAction = firstMatcher?.hooks[0];
  const name = value.name.trim() || value.event;

  return {
    ...item,
    title: name,
    description: value.event,
    path: item.path,
    content: marketplaceHookNativeContent(value),
    data: {
      ...item.data,
      ...marketplaceHookDataFromValue(value),
      [MARKETPLACE_HOOK_SOURCE_EVENT]: value.event,
    },
    badge: value.event,
    code: marketplaceHookActionSummary(firstAction),
    meta: [
      { labelKey: 'marketplace.editor.featureMeta.labels.type', value: firstAction?.type ?? 'command' },
      { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: firstMatcher?.matcher ?? '*' },
      { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: formatMarketplaceHookTimeout(targetClient, firstAction?.timeout) },
      ...(firstMatcher?.sequential ? [{ labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: t('marketplace.common.labels.enabled') }] : []),
    ],
  };
};

export const marketplaceHookActionSummary = (action?: HookMatcher['hooks'][number]): string => {
  if (!action) return '';
  if (action.type === 'http') return action.url;
  if (action.type === 'mcp_tool') return [action.server, action.tool].filter(Boolean).join('.');
  if (action.type === 'prompt' || action.type === 'agent') return action.prompt;
  return action.command;
};
