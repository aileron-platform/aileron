import React, { useCallback, useMemo, useState } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryKey,
} from '@tanstack/react-query';
import { AlertTriangle, Edit, FolderGit, HardDrive, Layers, Plus, Puzzle, RefreshCw, Search, Trash2, User, Zap } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import {
  SettingsListWorkbench,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
  useSettingsListController,
} from '@/shared/components/settings-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  HOOK_EVENTS,
  HOOK_EVENT_MATCHER_HINTS,
  HOOK_TYPES,
  HookCard,
  HookDialog,
  getHookDefaults,
  getHookDialogScopeValues,
  getHookEventI18nKey,
  getHookFieldSupport,
  type EventOption,
  type HookDialogData,
  type HookDialogLabels,
  type HookDialogOptions,
  type HookProvider,
  type HookScope,
} from '@/shared/components/hook-workflow';
import {
  DocumentSourceBadge,
  getDocumentSourceBadgeClassName,
  type DocumentSourceType,
} from '@/shared/components/document-resource';
import { sortAgentSettingsScopeValues } from '../../components/AgentSettingsSourceControls';
import {
  getWritableAgentScopes,
  isReadOnlyAgentScope,
  resolveAgentSettingsSelectedScope,
} from '../../agentSettingsScopeModel';
import type { AgentScope } from '../../model/documents';
import type { HookSource } from '../../model/hookSource';
import { getCodexPluginControlErrorKey } from '../../model/pluginResources';
import CodexPluginHookTrustControl from './CodexPluginHookTrustControl';
import { useAgentSettingsAuthorization } from '../../AgentSettingsAuthorizationContext';

const SCOPE_FILTER_ICONS: Record<string, React.ReactNode> = {
  all: <Layers className="h-3 w-3" />,
  project: <FolderGit className="h-3 w-3" />,
  user: <User className="h-3 w-3" />,
  local: <HardDrive className="h-3 w-3" />,
  plugin: <Puzzle className="h-3 w-3" />,
  built_in: <Puzzle className="h-3 w-3" />,
};

const commonHookEventLabelKey = (eventName: string) => getHookEventI18nKey(eventName, 'label');
const commonHookEventDescriptionKey = (eventName: string) => getHookEventI18nKey(eventName, 'description');
type HookDialogTranslator = (key: string) => string;

const createWorkspaceHookDialogLabels = (
  t: HookDialogTranslator,
  provider: HookProvider,
  mode: 'create' | 'edit',
  i18nNamespace: string,
): HookDialogLabels => {
  const fieldSupport = getHookFieldSupport(provider);
  const defaults = getHookDefaults(provider);
  const providerNamespace = provider === 'claude-code'
    ? 'workspace.agentSettings.claude'
    : i18nNamespace;

  return {
    title: t(`${i18nNamespace}.hooks.dialog.title.${mode}`),
    description: t(`${i18nNamespace}.hooks.dialog.description`),
    cancel: t(`${i18nNamespace}.hooks.dialog.actions.cancel`),
    submit: t(`${i18nNamespace}.hooks.dialog.actions.${mode === 'edit' ? 'save' : 'create'}`),
    name: {
      label: t(`${i18nNamespace}.hooks.dialog.name.label`),
      placeholder: t(`${i18nNamespace}.hooks.dialog.name.placeholder`),
    },
    scope: {
      label: t(`${i18nNamespace}.hooks.dialog.scope.label`),
      requiredLabel: t(`${i18nNamespace}.hooks.dialog.scope.labelWithAsterisk`),
      placeholder: t(`${i18nNamespace}.hooks.dialog.scope.placeholder`),
    },
    event: {
      label: t(`${i18nNamespace}.hooks.dialog.event.label`),
      placeholder: t(`${i18nNamespace}.hooks.dialog.event.placeholder`),
    },
    duplicateEventWarning: t(`${i18nNamespace}.hooks.dialog.validation.duplicateEventWarning`),
    duplicateEventSuggestion: t(`${i18nNamespace}.hooks.dialog.validation.duplicateEventSuggestion`),
    matcherActions: {
      matcherSectionTitle: t(`${i18nNamespace}.hooks.dialog.matcher.sectionTitle`),
      matcherAdd: t(`${i18nNamespace}.hooks.dialog.matcher.add`),
      matcherPatternLabel: t(`${i18nNamespace}.hooks.dialog.matcher.patternLabel`),
      matcherPatternPlaceholder: t(`${i18nNamespace}.hooks.dialog.matcher.patternPlaceholder`),
      matcherPatternHelp: (eventName) => {
        if (provider !== 'claude-code') {
          return [
            t(`${i18nNamespace}.hooks.dialog.matcher.helper.intro`),
            t(`${i18nNamespace}.hooks.dialog.matcher.helper.simple`),
            t(`${i18nNamespace}.hooks.dialog.matcher.helper.regex`),
            t(`${i18nNamespace}.hooks.dialog.matcher.helper.wildcard`),
          ];
        }

        const matcherHint = HOOK_EVENT_MATCHER_HINTS[eventName];
        return [
          t(`${providerNamespace}.hooks.dialog.matcherHints.${matcherHint?.helpKey ?? 'generic'}.help`),
          `- ${t(`${providerNamespace}.hooks.dialog.matcherHints.${matcherHint?.examplesKey ?? 'generic'}.example`)}`,
        ];
      },
      matcherUnsupportedMessage: t(`${i18nNamespace}.hooks.dialog.matcher.unsupported`),
      matcherSequentialLabel: fieldSupport.sequential
        ? t(`${i18nNamespace}.hooks.dialog.matcher.sequentialLabel`)
        : undefined,
      matcherSequentialHelp: fieldSupport.sequential
        ? t(`${i18nNamespace}.hooks.dialog.matcher.sequentialHelp`)
        : undefined,
      matcherRemove: t(`${i18nNamespace}.hooks.dialog.matcher.remove`),
      executionSectionTitle: t(`${i18nNamespace}.hooks.dialog.execution.sectionTitle`),
      executionAdd: t(`${i18nNamespace}.hooks.dialog.execution.add`),
      executionTypeLabel: t(`${i18nNamespace}.hooks.dialog.execution.typeLabel`),
      ...(fieldSupport.actionMetadata ? {
        executionNameLabel: t(`${i18nNamespace}.hooks.dialog.execution.nameLabel`),
        executionNamePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.namePlaceholder`),
        executionNameHelp: t(`${i18nNamespace}.hooks.dialog.execution.nameHelp`),
        executionDescriptionLabel: t(`${i18nNamespace}.hooks.dialog.execution.descriptionLabel`),
        executionDescriptionPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.descriptionPlaceholder`),
        executionDescriptionHelp: t(`${i18nNamespace}.hooks.dialog.execution.descriptionHelp`),
      } : {}),
      executionTimeoutLabel: t(`${i18nNamespace}.hooks.dialog.execution.timeoutLabel`),
      executionTimeoutPlaceholder: String(defaults.timeout),
      executionTimeoutHelp: t(`${i18nNamespace}.hooks.dialog.execution.timeoutHelp`),
      executionCommandLabel: t(`${i18nNamespace}.hooks.dialog.execution.commandLabel`),
      executionCommandPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.commandPlaceholder`),
      executionCommandHelp: t(`${i18nNamespace}.hooks.dialog.execution.commandHelp`),
      executionArgsLabel: fieldSupport.args
        ? t(`${providerNamespace}.hooks.dialog.execution.args.label`)
        : undefined,
      executionArgsPlaceholder: fieldSupport.args
        ? t(`${providerNamespace}.hooks.dialog.execution.args.placeholder`)
        : undefined,
      executionArgsHelp: fieldSupport.args
        ? t(`${providerNamespace}.hooks.dialog.execution.args.help`)
        : undefined,
      executionAdditionalContextLimitLabel: fieldSupport.additionalContextLimit
        ? t(`${providerNamespace}.hooks.dialog.execution.additionalContextLimit.label`)
        : undefined,
      executionAdditionalContextLimitPlaceholder: fieldSupport.additionalContextLimit
        ? t(`${providerNamespace}.hooks.dialog.execution.additionalContextLimit.placeholder`)
        : undefined,
      executionAdditionalContextLimitHelp: fieldSupport.additionalContextLimit
        ? t(`${providerNamespace}.hooks.dialog.execution.additionalContextLimit.help`)
        : undefined,
      executionCommandWindowsLabel: fieldSupport.commandWindows
        ? t(`${providerNamespace}.hooks.dialog.execution.commandWindows.label`)
        : undefined,
      executionCommandWindowsPlaceholder: fieldSupport.commandWindows
        ? t(`${providerNamespace}.hooks.dialog.execution.commandWindows.placeholder`)
        : undefined,
      executionCommandWindowsHelp: fieldSupport.commandWindows
        ? t(`${providerNamespace}.hooks.dialog.execution.commandWindows.help`)
        : undefined,
      ...(fieldSupport.statusMessage ? {
        executionStatusMessageLabel: t(`${i18nNamespace}.hooks.dialog.execution.statusMessageLabel`),
        executionStatusMessagePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.statusMessagePlaceholder`),
        executionStatusMessageHelp: t(`${i18nNamespace}.hooks.dialog.execution.statusMessageHelp`),
      } : {}),
      executionUrlLabel: t(`${i18nNamespace}.hooks.dialog.execution.url.label`),
      executionUrlPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.url.placeholder`),
      executionUrlHelp: t(`${i18nNamespace}.hooks.dialog.execution.url.help`),
      executionHeadersLabel: t(`${i18nNamespace}.hooks.dialog.execution.headers.label`),
      executionHeadersHelp: t(`${i18nNamespace}.hooks.dialog.execution.headers.help`),
      executionHeaderKeyPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.headers.keyPlaceholder`),
      executionHeaderValuePlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.headers.valuePlaceholder`),
      executionHeadersAdd: t(`${i18nNamespace}.hooks.dialog.execution.headers.add`),
      executionHeadersRemove: t(`${i18nNamespace}.hooks.dialog.execution.headers.remove`),
      executionAllowedEnvVarsLabel: t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.label`),
      executionAllowedEnvVarsPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.placeholder`),
      executionAllowedEnvVarsHelp: t(`${i18nNamespace}.hooks.dialog.execution.allowedEnvVars.help`),
      executionServerLabel: t(`${i18nNamespace}.hooks.dialog.execution.server.label`),
      executionServerPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.server.placeholder`),
      executionServerHelp: t(`${i18nNamespace}.hooks.dialog.execution.server.help`),
      executionToolLabel: t(`${i18nNamespace}.hooks.dialog.execution.tool.label`),
      executionToolPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.tool.placeholder`),
      executionToolHelp: t(`${i18nNamespace}.hooks.dialog.execution.tool.help`),
      executionInputLabel: t(`${i18nNamespace}.hooks.dialog.execution.input.label`),
      executionInputPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.input.placeholder`),
      executionInputHelp: t(`${i18nNamespace}.hooks.dialog.execution.input.help`),
      executionPromptLabel: t(`${i18nNamespace}.hooks.dialog.execution.promptField.label`),
      executionPromptPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.promptField.placeholder`),
      executionPromptHelp: t(`${i18nNamespace}.hooks.dialog.execution.promptField.help`),
      executionModelLabel: t(`${i18nNamespace}.hooks.dialog.execution.model.label`),
      executionModelPlaceholder: t(`${i18nNamespace}.hooks.dialog.execution.model.placeholder`),
      executionModelHelp: t(`${i18nNamespace}.hooks.dialog.execution.model.help`),
      executionConditionLabel: fieldSupport.condition
        ? t(`${providerNamespace}.hooks.dialog.execution.if.label`)
        : undefined,
      executionConditionPlaceholder: fieldSupport.condition
        ? t(`${providerNamespace}.hooks.dialog.execution.if.placeholder`)
        : undefined,
      executionConditionHelp: fieldSupport.condition
        ? t(`${providerNamespace}.hooks.dialog.execution.if.help`)
        : undefined,
      executionAsyncLabel: fieldSupport.async
        ? t(`${providerNamespace}.hooks.dialog.execution.async.label`)
        : undefined,
      executionAsyncRewakeLabel: fieldSupport.async
        ? t(`${providerNamespace}.hooks.dialog.execution.asyncRewake.label`)
        : undefined,
      executionOnceLabel: fieldSupport.once
        ? t(`${providerNamespace}.hooks.dialog.execution.once.label`)
        : undefined,
      executionOnceHelp: fieldSupport.once
        ? t(`${providerNamespace}.hooks.dialog.execution.once.help`)
        : undefined,
      executionShellLabel: fieldSupport.shell
        ? t(`${providerNamespace}.hooks.dialog.execution.shell.label`)
        : undefined,
      executionShellPlaceholder: fieldSupport.shell
        ? t(`${providerNamespace}.hooks.dialog.execution.shell.placeholder`)
        : undefined,
      executionShellHelp: fieldSupport.shell
        ? t(`${providerNamespace}.hooks.dialog.execution.shell.help`)
        : undefined,
      executionRemove: t(`${i18nNamespace}.hooks.dialog.execution.remove`),
    },
  };
};

const createWorkspaceHookDialogOptions = (
  t: HookDialogTranslator,
  provider: HookProvider,
  i18nNamespace: string,
  availableScopes: HookScope[],
  events: EventOption[],
): HookDialogOptions => {
  const fieldSupport = getHookFieldSupport(provider);
  const providerNamespace = provider === 'claude-code'
    ? 'workspace.agentSettings.claude'
    : i18nNamespace;
  const hookTypeI18nPath = provider === 'claude-code'
    ? `${providerNamespace}.hooks.dialog.types`
    : `${i18nNamespace}.hooks.dialog.execution.types`;

  return {
    events,
    scopes: getHookDialogScopeValues(availableScopes).map((scope) => ({
      value: scope,
      label: t(`${i18nNamespace}.hooks.dialog.scope.options.${scope}`),
    })),
    executionTypes: HOOK_TYPES[provider].map((hookType) => ({
      value: hookType,
      label: t(`${hookTypeI18nPath}.${hookType}.label`),
      description: t(`${hookTypeI18nPath}.${hookType}.description`),
    })),
    executionShells: fieldSupport.shell ? [
      {
        value: 'bash',
        label: t(`${providerNamespace}.hooks.dialog.execution.shell.options.bash`),
      },
      {
        value: 'powershell',
        label: t(`${providerNamespace}.hooks.dialog.execution.shell.options.powershell`),
      },
    ] : undefined,
  };
};

interface HooksPageProps {
  queryKey: QueryKey;
  source: HookSource;
  provider: HookProvider;
  availableScopes: AgentScope[];
  eventOptions?: EventOption[];
  i18nNamespace: string;
  isEnabled?: boolean;
  disabledMessage?: string | null;
  onProviderResourceMutation?: () => Promise<void>;
  readOnly?: boolean;
}

const sourceLabelKey = (namespace: string, source: string | undefined): string | null => {
  if (!source) return null;
  return `${namespace}.hooks.sources.${source}`;
};

const isAgentScope = (scope: HookScope): scope is AgentScope => (
  scope === 'project' || scope === 'user' || scope === 'local' || scope === 'plugin'
);

const commandOf = (action: HookDialogData['matchers'][number]['hooks'][number]): string =>
  action.type === 'command' ? action.command : '';

const hasCodexPluginHookTrust = (
  hook: HookDialogData,
): hook is HookDialogData & {
  pluginId: string;
  trustState: 'trusted' | 'untrusted' | 'modified' | 'mixed';
  trusted: boolean;
  effective: boolean;
  trustRevision: string;
} => (
  hook.scope === 'plugin'
  && Boolean(hook.pluginId && hook.trustState && hook.trustRevision)
  && typeof hook.trusted === 'boolean'
  && typeof hook.effective === 'boolean'
);

const HooksPage: React.FC<HooksPageProps> = ({
  queryKey,
  source,
  provider,
  availableScopes,
  eventOptions,
  i18nNamespace,
  isEnabled = true,
  disabledMessage = null,
  onProviderResourceMutation,
  readOnly: readOnlyProp,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { readOnly: contextReadOnly } = useAgentSettingsAuthorization();
  const readOnly = readOnlyProp ?? contextReadOnly;
  const [scopeFilter, setScopeFilter] = useState<'all' | HookScope>('all');
  const [featureEnabled, setFeatureEnabled] = useState<boolean>(true);
  const featureScope = scopeFilter === 'project' || scopeFilter === 'user'
    ? scopeFilter
    : undefined;

  const hooksQuery = useQuery({
    queryKey: [...queryKey, featureScope ?? 'effective'],
    queryFn: async () => {
      const [items, enabled] = await Promise.all([
        source.list(),
        source.featureEnablement?.isEnabled(featureScope) ?? Promise.resolve(true),
      ]);
      setFeatureEnabled(enabled);
      return items.sort((a, b) => a.eventName.localeCompare(b.eventName));
    },
    enabled: isEnabled,
  });

  const invalidate = useCallback(async () => {
    if (!isEnabled) {
      return;
    }
    await queryClient.invalidateQueries({ queryKey });
  }, [isEnabled, queryClient, queryKey]);

  const saveMutation = useMutation({
    mutationFn: ({ entry, previous }: { entry: HookDialogData; previous?: HookDialogData | null }) =>
      source.save(entry, previous),
    onSuccess: async () => {
      await invalidate();
    },
  });

  const removeMutation = useMutation({
    mutationFn: (entry: HookDialogData) => source.remove(entry),
    onSuccess: async () => {
      await invalidate();
    },
  });

  const enableMutation = useMutation({
    mutationFn: async () => {
      await source.featureEnablement?.enable(featureScope);
    },
    onSuccess: async () => {
      setFeatureEnabled(true);
      await invalidate();
    },
  });

  const disableMutation = useMutation({
    mutationFn: async () => {
      await source.featureEnablement?.disable?.(featureScope);
    },
    onSuccess: async () => {
      setFeatureEnabled(false);
      await invalidate();
    },
  });

  const trustMutation = useMutation({
    mutationFn: ({ entry, trusted }: { entry: HookDialogData; trusted: boolean }) => {
      if (!source.pluginTrust) {
        throw Object.assign(
          new Error('marketplace.settings.plugin_hook_trust_not_supported'),
          {
            errorCode:
              'marketplace.settings.plugin_hook_trust_not_supported',
          },
        );
      }
      return source.pluginTrust.update(entry, trusted);
    },
    onSuccess: async () => {
      toast({
        title: t(`${i18nNamespace}.hooks.pluginTrust.messages.updateSuccess`),
      });
      if (onProviderResourceMutation) {
        await onProviderResourceMutation();
        return;
      }
      await invalidate();
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: t(`${i18nNamespace}.hooks.pluginTrust.messages.updateFailed`),
        description: t(getCodexPluginControlErrorKey('hook-trust', error)),
      });
    },
  });

  const hooks = useMemo(() => hooksQuery.data ?? [], [hooksQuery.data]);

  const eventLabels = useMemo<Record<string, string>>(() => {
    if (eventOptions) {
      return Object.fromEntries(eventOptions.map((event) => [event.value, event.label]));
    }
    return Object.fromEntries(HOOK_EVENTS[provider].map((eventName) => [
      eventName,
      t(commonHookEventLabelKey(eventName)),
    ]));
  }, [eventOptions, provider, t]);

  const getHookSearchText = useCallback((hook: HookDialogData) => [
    hook.scope,
    hook.eventName,
    eventLabels[hook.eventName] ?? hook.eventName,
    hook.source ?? '',
    ...hook.matchers.flatMap((matcher) => [
      matcher.matcher,
      ...matcher.hooks.flatMap((action) => [
        commandOf(action),
        action.statusMessage ?? '',
      ]),
    ]),
  ], [eventLabels]);

  const {
    filteredItems: filteredHooks,
    selectedItem: activeHook,
    query: search,
    setQuery: setSearch,
    editorMode: dialogMode,
    editorOpen: dialogOpen,
    openCreate,
    openEdit,
    closeEditor,
  } = useSettingsListController<HookDialogData>(hooks, {
    getScope: (hook) => hook.scope,
    getSearchText: getHookSearchText,
  });

  const allScopeValues = useMemo(() => {
    const loadedScopes = hooks.map((hook) => hook.scope).filter(isAgentScope);
    return sortAgentSettingsScopeValues(Array.from(new Set([...availableScopes, ...loadedScopes])) as AgentScope[]);
  }, [availableScopes, hooks]);

  React.useEffect(() => {
    const nextScope = scopeFilter !== 'all' && isAgentScope(scopeFilter)
      ? resolveAgentSettingsSelectedScope(scopeFilter, allScopeValues)
      : 'all';
    if (nextScope !== scopeFilter) setScopeFilter(nextScope as typeof scopeFilter);
  }, [allScopeValues, scopeFilter]);

  const visibleHooks = useMemo(() => {
    if (scopeFilter === 'all') return filteredHooks;
    return filteredHooks.filter((hook) => hook.scope === scopeFilter);
  }, [filteredHooks, scopeFilter]);

  const writableScopes = useMemo(
    () => getWritableAgentScopes(sortAgentSettingsScopeValues(availableScopes)) as HookScope[],
    [availableScopes],
  );

  const dialogEventOptions = useMemo<EventOption[]>(() => {
    if (eventOptions) return eventOptions;
    const providerNamespace = provider === 'claude-code' ? 'workspace.agentSettings.claude' : i18nNamespace;
    return HOOK_EVENTS[provider].map((eventName) => ({
      value: eventName,
      label: t(`${providerNamespace}.hooks.events.${eventName}.option`),
    }));
  }, [eventOptions, i18nNamespace, provider, t]);
  const dialogLabels = useMemo(
    () => createWorkspaceHookDialogLabels(t, provider, dialogMode, i18nNamespace),
    [dialogMode, i18nNamespace, provider, t],
  );
  const dialogOptions = useMemo(
    () => createWorkspaceHookDialogOptions(
      t,
      provider,
      i18nNamespace,
      writableScopes,
      dialogEventOptions,
    ),
    [dialogEventOptions, i18nNamespace, provider, t, writableScopes],
  );

  const scopeFilterOptions = useMemo(() => {
    const options: Record<string, string> = {
      all: t(`${i18nNamespace}.hooks.filters.scope.options.all`),
    };
    for (const scope of allScopeValues) {
      options[scope] = t(`${i18nNamespace}.hooks.filters.scope.options.${scope}`);
    }
    return options;
  }, [allScopeValues, i18nNamespace, t]);

  const isBusy = (
    !isEnabled
    || hooksQuery.isFetching
    || saveMutation.isPending
    || removeMutation.isPending
    || enableMutation.isPending
    || disableMutation.isPending
    || trustMutation.isPending
  );
  const hookCardI18nNamespace = provider === 'claude-code' ? 'workspace.agentSettings.claude' : i18nNamespace;

  const canEdit = (hook: HookDialogData): boolean => (
    !readOnly
    && !hook.readOnly
    && isAgentScope(hook.scope)
    && !isReadOnlyAgentScope(hook.scope)
  );
  const canDelete = canEdit;

  const handleSubmit = async (entry: HookDialogData) => {
    if (!isEnabled || readOnly) {
      return;
    }
    await saveMutation.mutateAsync({
      entry,
      previous: dialogMode === 'edit' ? activeHook : null,
    });
    closeEditor();
  };

  return (
    <SettingsWorkflowShell
      title={t(`${i18nNamespace}.hooks.header.title`)}
      icon={Zap}
      headerActions={(
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
            <span className="text-xs text-muted-foreground">{t(`${i18nNamespace}.hooks.filters.scope.label`)}</span>
            <Select value={scopeFilter} onValueChange={(value) => setScopeFilter(value as typeof scopeFilter)}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SelectValue placeholder={t(`${i18nNamespace}.hooks.filters.scope.placeholder`)} />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(scopeFilterOptions).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    <div className="flex items-center gap-2">
                      {SCOPE_FILTER_ICONS[value]}
                      {label}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => void invalidate()} disabled={isBusy}>
            <RefreshCw className={`mr-1 h-3 w-3 ${hooksQuery.isFetching ? 'animate-spin' : ''}`} aria-hidden="true" />
            {t(`${i18nNamespace}.hooks.actions.refresh`)}
          </Button>
          {featureEnabled && featureScope && source.featureEnablement?.disable && !readOnly ? (
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => disableMutation.mutate()} disabled={isBusy}>
              {t(`${i18nNamespace}.hooks.actions.disableFeature`)}
            </Button>
          ) : null}
          {!readOnly ? (
          <Button size="sm" className="h-7 px-2 text-xs" onClick={() => openCreate()} disabled={isBusy}>
            <Plus className="mr-1 h-3 w-3" />
            {t(`${i18nNamespace}.hooks.actions.create`)}
          </Button>
          ) : null}
        </div>
      )}
      error={disabledMessage ?? (
        hooksQuery.error
          ? provider === 'codex'
            ? t(getCodexPluginControlErrorKey('hook-trust', hooksQuery.error))
            : t(`${i18nNamespace}.hooks.messages.loadFailed`)
          : null
      )}
      isLoading={hooksQuery.isFetching && hooks.length === 0}
      loadingLabel={t(`${i18nNamespace}.hooks.loading`)}
      hasItems
      summary={<SettingsWorkflowCountBadge label={t(`${i18nNamespace}.hooks.stats.hooks`, { count: visibleHooks.length })} />}
      controls={(
        <div className="relative w-full max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transform text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t(`${i18nNamespace}.hooks.search.placeholder`)}
            className="h-7 pl-9 text-xs"
          />
        </div>
      )}
      emptyTitle={t(`${i18nNamespace}.hooks.header.title`)}
      emptyDescription={t(`${i18nNamespace}.hooks.list.empty`)}
      contentClassName="h-full overflow-y-auto"
    >
      <div className="space-y-4 p-6">
        {!featureEnabled && source.featureEnablement ? (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>{t(`${i18nNamespace}.hooks.featureWarning.title`)}</AlertTitle>
            <AlertDescription className="flex items-center justify-between gap-3">
              <span>{t(`${i18nNamespace}.hooks.featureWarning.description`)}</span>
              {!readOnly ? (
              <Button size="sm" onClick={() => enableMutation.mutate()} disabled={enableMutation.isPending}>
                {t(`${i18nNamespace}.hooks.actions.enableFeature`)}
              </Button>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}

        <SettingsListWorkbench
          items={visibleHooks}
          getItemKey={(hook) => hook.id}
          i18nKeys={{
            emptyTitle: `${i18nNamespace}.hooks.header.title`,
            emptyDescription: `${i18nNamespace}.hooks.list.empty`,
          }}
          card={(hook) => {
            const sourceKey = sourceLabelKey(i18nNamespace, hook.source);
            return (
              <div key={hook.id} className="relative rounded-lg border border-border bg-background p-6">
                <div className="flex items-start">
                  <div className="min-w-0 flex-1 pr-16">
                    <div className="mb-3 flex flex-wrap items-center gap-3">
                      <Badge
                        variant="outline"
                        className={`text-xs ${getDocumentSourceBadgeClassName(hook.scope)}`}
                      >
                        {t(`${i18nNamespace}.hooks.scope.badge.${hook.scope}`)}
                      </Badge>
                      {hook.pluginName && (
                        <Badge variant="outline" className="flex items-center gap-1 text-xs">
                          <Puzzle className="h-3 w-3" />
                          {hook.pluginName}@{hook.marketplaceName}
                        </Badge>
                      )}
                      {sourceKey && (
                        <DocumentSourceBadge
                          source={{ type: (hook.source ?? 'unknown') as DocumentSourceType, label: t(sourceKey) }}
                          className="text-xs"
                        />
                      )}
                    </div>
                    <HookCard
                      provider={provider}
                      hook={{
                        event: eventLabels[hook.eventName] ?? hook.eventName,
                        description: t(commonHookEventDescriptionKey(hook.eventName)),
                        matchers: hook.matchers,
                      }}
                      i18nKeyPrefix={`${hookCardI18nNamespace}.hooks.card`}
                    />
                    {hook.readOnly && hook.rawContent ? (
                      <pre className="mb-4 max-h-28 overflow-auto rounded bg-muted/40 p-3 text-xs">{hook.rawContent}</pre>
                    ) : null}
                    {!readOnly
                      && provider === 'codex'
                      && source.pluginTrust
                      && hasCodexPluginHookTrust(hook) ? (
                        <CodexPluginHookTrustControl
                          hook={hook}
                          disabled={isBusy}
                          i18nNamespace={i18nNamespace}
                          onTrustedChange={(entry, trusted) => {
                            trustMutation.mutate({ entry, trusted });
                          }}
                        />
                      ) : null}
                  </div>
                </div>
                <div className="absolute top-4 right-4 flex items-center gap-2">
                  {canEdit(hook) && (
                    <button
                      type="button"
                      className="rounded-md p-2 transition-colors hover:bg-muted disabled:opacity-50"
                      onClick={() => openEdit(hook)}
                      disabled={isBusy}
                      aria-label={t(`${i18nNamespace}.hooks.actions.edit`)}
                    >
                      <Edit className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <span className="sr-only">{t(`${i18nNamespace}.hooks.actions.edit`)}</span>
                    </button>
                  )}
                  {canDelete(hook) && (
                    <button
                      type="button"
                      className="rounded-md p-2 transition-colors hover:bg-muted disabled:opacity-50"
                      onClick={() => void removeMutation.mutate(hook)}
                      disabled={isBusy}
                      aria-label={t(`${i18nNamespace}.hooks.actions.delete`)}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <span className="sr-only">{t(`${i18nNamespace}.hooks.actions.delete`)}</span>
                    </button>
                  )}
                </div>
              </div>
            );
          }}
          dialog={(
            <HookDialog
              provider={provider}
              open={dialogOpen}
              mode={dialogMode}
              hook={activeHook}
              existingHooks={hooks.filter((hook) => !hook.readOnly)}
              labels={dialogLabels}
              options={dialogOptions}
              onClose={closeEditor}
              onSubmit={(hook) => {
                void handleSubmit(hook);
              }}
              submitDisabled={readOnly}
            />
          )}
        />
      </div>
    </SettingsWorkflowShell>
  );
};

export default HooksPage;
