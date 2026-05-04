import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Edit,
  FolderGit,
  Layers,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Terminal,
  Trash2,
  User,
  Webhook,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import {
  WorkspaceHookDialog,
  type EventOption,
  type WorkspaceHookData,
} from './dialogs/WorkspaceHookDialog';
import {
  AgentSettingsSourceBadge,
  getAgentSettingsSourceBadgeClassName,
} from '../components/SettingsSourcePrimitives';
import {
  createAgentSettingsApi,
  type CodexHookEntry,
  type CodexHookEventMetadata,
  type CodexHookSource,
} from '../services/agentSettingsApi';

type CodexLayer = 'user' | 'project';
type CodexHookScope = CodexLayer | 'plugin' | 'built_in';
type CodexHookAction = { type: 'command'; command?: string; timeout?: number | null; statusMessage?: string | null; raw?: Record<string, unknown> };

const hookEvents = ['SessionStart', 'PreToolUse', 'PostToolUse', 'PermissionRequest', 'UserPromptSubmit', 'Stop'] as const;

const editableLayers: CodexLayer[] = ['project', 'user'];
const matcherEvents = new Set<string>(['PreToolUse', 'PostToolUse', 'PermissionRequest']);

interface CodexHookListItem {
  id: string;
  scope: CodexHookScope;
  eventName: string;
  matchers: WorkspaceHookData['matchers'];
  pluginName?: string;
  marketplaceName?: string;
  source: CodexHookSource;
  layer: CodexHookScope;
  readOnly: boolean;
  rawContent?: string;
  sourcePath?: string | null;
  entryIndexes?: number[];
}

const emptyHooksJson = '{}';

const parseHooksContent = (content: string): Record<string, unknown[]> => {
  const parsed = JSON.parse(content || emptyHooksJson) as Record<string, unknown>;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
  return Object.fromEntries(
    Object.entries(parsed).map(([event, value]) => [event, Array.isArray(value) ? value : []]),
  );
};

const sourceToScope = (entry: CodexHookEntry): CodexHookScope => {
  if (
    (entry.source === 'hooks_json'
      || entry.source === 'inline_config'
      || entry.source === 'project'
      || entry.source === 'user')
    && (entry.layer === 'project' || entry.layer === 'user')
  ) return entry.layer;
  if (entry.source === 'built_in') return 'built_in';
  return 'plugin';
};

const mapEntryAction = (action: CodexHookEntry['actions'][number]): CodexHookAction => ({
  type: 'command',
  command: action.command ?? '',
  timeout: typeof action.timeout === 'number' ? action.timeout : undefined,
  statusMessage: action.statusMessage ?? undefined,
  raw: action.raw,
});

const mapHookEntriesToItems = (entries: CodexHookEntry[]): CodexHookListItem[] => {
  const grouped = new Map<string, CodexHookListItem>();
  for (const entry of entries) {
    const scope = sourceToScope(entry);
    const layer = entry.layer === 'project' || entry.layer === 'user' ? entry.layer : scope;
    const key = `${entry.source}:${layer}:${entry.event}:${entry.pluginId ?? ''}:${entry.sourcePath ?? ''}`;
    const item = grouped.get(key) ?? {
      id: key,
      scope,
      layer,
      source: entry.source,
      eventName: entry.event,
      matchers: [],
      pluginName: entry.pluginName ?? undefined,
      marketplaceName: entry.marketplaceName ?? undefined,
      readOnly: entry.readOnly,
      sourcePath: entry.sourcePath,
      rawContent: entry.raw ? JSON.stringify(entry.raw, null, 2) : undefined,
      entryIndexes: [],
    };
    item.matchers.push({
      matcher: entry.matcher || '*',
      hooks: entry.actions.map(mapEntryAction),
      raw: entry.raw,
    });
    item.entryIndexes?.push(entry.index);
    grouped.set(key, item);
  }
  return Array.from(grouped.values());
};

const mapHookToJsonEntries = (hook: WorkspaceHookData): Record<string, unknown>[] => (
  hook.matchers.map((matcher) => {
    const hooks = matcher.hooks.map((action) => {
      const raw = typeof action.raw === 'object' && action.raw !== null ? action.raw : {};
      const nextAction: Record<string, unknown> = {
        ...raw,
        type: 'command',
        command: action.command ?? '',
        timeout: action.timeout ?? 30,
      };
      if (action.statusMessage?.trim()) {
        nextAction.statusMessage = action.statusMessage.trim();
      } else {
        delete nextAction.statusMessage;
      }
      return nextAction;
    });
    const rawEntry = typeof matcher.raw === 'object' && matcher.raw !== null
      ? matcher.raw
      : {};
    if (matcherEvents.has(hook.eventName)) {
      return { ...rawEntry, matcher: matcher.matcher || '*', hooks };
    }
    return { ...rawEntry, hooks };
  })
);

const upsertHookContent = (content: string, hook: WorkspaceHookData, previous?: WorkspaceHookData | null) => {
  const parsed = parseHooksContent(content);
  if (previous && previous.eventName !== hook.eventName) {
    delete parsed[previous.eventName];
  }
  parsed[hook.eventName] = mapHookToJsonEntries(hook);
  return JSON.stringify(parsed, null, 2);
};

const deleteHookContent = (content: string, eventName: string) => {
  const parsed = parseHooksContent(content);
  delete parsed[eventName];
  return JSON.stringify(parsed, null, 2);
};

const toWorkspaceHookData = (hook: CodexHookListItem | null): WorkspaceHookData | null => {
  if (!hook || (hook.scope !== 'project' && hook.scope !== 'user')) return null;
  return {
    id: hook.id,
    scope: hook.scope,
    eventName: hook.eventName,
    matchers: hook.matchers,
    pluginName: hook.pluginName,
    marketplaceName: hook.marketplaceName,
  };
};

const CodexHooksPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const [activeLayer, setActiveLayer] = useState<CodexLayer>('project');
  const [search, setSearch] = useState('');
  const [scopeFilter, setScopeFilter] = useState<'all' | CodexHookScope>('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeHook, setActiveHook] = useState<CodexHookListItem | null>(null);
  const [draftContent, setDraftContent] = useState<Record<CodexLayer, string>>({ project: emptyHooksJson, user: emptyHooksJson });
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;

  const hooksQuery = useQuery({
    queryKey: ['codex-hooks-workflow', runtimeBaseUrl, workspaceId],
    queryFn: async () => {
      const response = await api.listCodexHooksScopes(runtimeBaseUrl || '', workspaceId || '');
      const responses = editableLayers.map((layer) => response.scopes.find((scope) => scope.layer === layer));
      if (!responses[0] || !responses[1]) {
        throw new Error(t('workspace.agentSettings.codex.hooks.notifications.loadIncomplete'));
      }
      const byLayer = {
        project: responses[0],
        user: responses[1],
      };
      setDraftContent({
        project: byLayer.project.content || emptyHooksJson,
        user: byLayer.user.content || emptyHooksJson,
      });
      return byLayer;
    },
    enabled: Boolean(runtimeBaseUrl && workspaceId),
    staleTime: 30_000,
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['codex-hooks-workflow', runtimeBaseUrl, workspaceId] });
  };

  const saveMutation = useMutation({
    mutationFn: ({ layer, content }: { layer: CodexLayer; content: string }) =>
      api.updateCodexHooks(runtimeBaseUrl || '', workspaceId || '', layer, content),
    onSuccess: async () => {
      await invalidate();
      toast({ title: t('workspace.agentSettings.codex.hooks.notifications.saved') });
    },
    onError: (error) => toast({
      variant: 'destructive',
      title: t('workspace.agentSettings.codex.hooks.notifications.saveFailed'),
      description: error instanceof Error ? error.message : undefined,
    }),
  });

  const enableMutation = useMutation({
    mutationFn: (layer: CodexLayer) => api.enableCodexHooks(runtimeBaseUrl || '', workspaceId || '', layer),
    onSuccess: async () => {
      await invalidate();
      toast({ title: t('workspace.agentSettings.codex.hooks.notifications.enabled') });
    },
  });

  const codexHookItems = useMemo(() => {
    const entries = [
      ...(hooksQuery.data?.project.entries ?? []),
      ...(hooksQuery.data?.user.entries ?? []),
    ];
    const uniqueEntries = Array.from(new Map(entries.map((entry) => [entry.id, entry])).values());
    return mapHookEntriesToItems(uniqueEntries).sort((a, b) => a.eventName.localeCompare(b.eventName));
  }, [hooksQuery.data]);

  const filteredHooks = useMemo(() => {
    const query = search.trim().toLowerCase();
    return codexHookItems.filter((hook) => {
      if (scopeFilter !== 'all' && hook.layer !== scopeFilter && hook.scope !== scopeFilter) return false;
      if (!query) return true;
      if (hook.eventName.toLowerCase().includes(query)) return true;
      if (hook.layer.toLowerCase().includes(query)) return true;
      return hook.matchers.some((matcher) => (
        matcher.matcher.toLowerCase().includes(query)
        || matcher.hooks.some((action) => (
          action.command?.toLowerCase().includes(query)
          || action.statusMessage?.toLowerCase().includes(query)
        ))
      ));
    });
  }, [codexHookItems, scopeFilter, search]);

  const scopeFilterOptions = useMemo<Array<[string, typeof Layers]>>(() => {
    const hasBuiltInHooks = codexHookItems.some((hook) => hook.scope === 'built_in' || hook.layer === 'built_in');
    return [
      ['all', Layers],
      ['project', FolderGit],
      ['user', User],
      ['plugin', Puzzle],
      ...(hasBuiltInHooks ? [['built_in', Puzzle] as [string, typeof Layers]] : []),
    ];
  }, [codexHookItems]);

  React.useEffect(() => {
    if (scopeFilter !== 'all' && !scopeFilterOptions.some(([value]) => value === scopeFilter)) {
      setScopeFilter('all');
    }
  }, [scopeFilter, scopeFilterOptions]);

  const dialogEventOptions = useMemo<EventOption[]>(() => (
    hookEvents.map((eventName) => ({
      value: eventName,
      label: t(`workspace.agentSettings.codex.hooks.events.${eventName}.option`),
    }))
  ), [t]);

  const eventMetadata = useMemo(() => {
    const metadata = hooksQuery.data?.project.eventMetadata ?? hooksQuery.data?.user.eventMetadata ?? [];
    return new Map<string, CodexHookEventMetadata>(metadata.map((item) => [item.event, item]));
  }, [hooksQuery.data]);

  const getMatcherHelp = (eventName: string) => {
    const metadata = eventMetadata.get(eventName);
    if (!metadata) {
      return [
        t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.intro'),
        t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.simple'),
        t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.regex'),
        t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.wildcard'),
      ];
    }
    if (!metadata.matcherSupported) {
      return [t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.ignored')];
    }
    if (metadata.matcherTarget === 'source') {
      return [
        t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.sessionSource'),
        t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.sessionExamples'),
      ];
    }
    return [
      t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.toolName'),
      t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.toolExamples'),
      t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.regex'),
      t('workspace.agentSettings.codex.hooks.dialog.matcher.helper.wildcard'),
    ];
  };

  const featureEnabled = Boolean(hooksQuery.data?.project.featureEnabled || hooksQuery.data?.user.featureEnabled);
  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId);
  const isBusy = hooksQuery.isFetching || saveMutation.isPending || enableMutation.isPending;

  const openCreateDialog = () => {
    setDialogMode('create');
    setActiveHook(null);
    setDialogOpen(true);
  };

  const openEditDialog = (hook: CodexHookListItem) => {
    if (hook.source !== 'hooks_json') return;
    setDialogMode('edit');
    setActiveHook(hook);
    setDialogOpen(true);
  };

  const submitHook = async (hook: WorkspaceHookData) => {
    const layer = hook.scope === 'user' ? 'user' : 'project';
    const previous = activeHook?.source === 'hooks_json' ? toWorkspaceHookData(activeHook) : null;
    const previousLayer = activeHook?.layer === 'user' || activeHook?.layer === 'project' ? activeHook.layer : layer;

    if (previous && previousLayer !== layer) {
      const removedContent = deleteHookContent(draftContent[previousLayer], previous.eventName);
      setDraftContent((current) => ({ ...current, [previousLayer]: removedContent }));
      await saveMutation.mutateAsync({ layer: previousLayer, content: removedContent });
    }

    const updatedContent = upsertHookContent(draftContent[layer], hook, previousLayer === layer ? previous : null);
    setDraftContent((current) => ({ ...current, [layer]: updatedContent }));
    await saveMutation.mutateAsync({ layer, content: updatedContent });
    setDialogOpen(false);
    setActiveHook(null);
  };

  const deleteHook = async (hook: CodexHookListItem) => {
    if (hook.source !== 'hooks_json' || (hook.layer !== 'project' && hook.layer !== 'user')) return;
    const updatedContent = deleteHookContent(draftContent[hook.layer], hook.eventName);
    setDraftContent((current) => ({ ...current, [hook.layer]: updatedContent }));
    await saveMutation.mutateAsync({ layer: hook.layer, content: updatedContent });
  };

  return (
    <>
      <SettingsWorkflowShell
        title={t('workspace.agentSettings.codex.hooks.header.title')}
        icon={Webhook}
        headerActions={(
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
              <span className="text-xs text-muted-foreground">{t('workspace.agentSettings.codex.hooks.filters.scope.label')}</span>
              <Select value={scopeFilter} onValueChange={(value) => setScopeFilter(value as typeof scopeFilter)}>
                <SelectTrigger className="h-7 w-32 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {scopeFilterOptions.map(([value, Icon]) => (
                    <SelectItem key={String(value)} value={String(value)}>
                      <div className="flex items-center gap-2">
                        {React.createElement(Icon as typeof Layers, { className: 'h-3 w-3' })}
                        {t(`workspace.agentSettings.codex.hooks.filters.scope.options.${String(value)}`)}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => void invalidate()}
              disabled={isBusy}
            >
              <RefreshCw className={`mr-1 h-3 w-3 ${hooksQuery.isFetching ? 'animate-spin' : ''}`} />
              {t('workspace.agentSettings.codex.hooks.actions.refresh')}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={openCreateDialog} disabled={!isRuntimeReady || isBusy}>
              <Plus className="mr-1 h-3 w-3" />
              {t('workspace.agentSettings.codex.hooks.actions.create')}
            </Button>
          </div>
        )}
        summary={<SettingsWorkflowCountBadge label={t('workspace.agentSettings.codex.hooks.stats.hooks', { count: filteredHooks.length })} />}
        controls={(
          <div className="relative w-full max-w-md">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('workspace.agentSettings.codex.hooks.search.placeholder')}
              className="h-7 pl-9 text-xs"
            />
          </div>
        )}
        error={hooksQuery.error instanceof Error ? hooksQuery.error.message : null}
        isLoading={hooksQuery.isFetching && codexHookItems.length === 0}
        loadingLabel={t('workspace.agentSettings.codex.hooks.loading')}
        hasItems={filteredHooks.length > 0 || !featureEnabled}
        emptyTitle={t('workspace.agentSettings.codex.hooks.header.title')}
        emptyDescription={t('workspace.agentSettings.codex.hooks.list.empty')}
        emptyActions={(
          <Button size="sm" onClick={openCreateDialog} disabled={!isRuntimeReady || isBusy}>
            <Plus className="mr-1 h-4 w-4" />
            {t('workspace.agentSettings.codex.hooks.actions.create')}
          </Button>
        )}
        contentClassName="h-full overflow-y-auto"
      >
        <div className="space-y-4 p-6">
          {!featureEnabled ? (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>{t('workspace.agentSettings.codex.hooks.featureWarning.title')}</AlertTitle>
              <AlertDescription className="flex items-center justify-between gap-3">
                <span>{t('workspace.agentSettings.codex.hooks.featureWarning.description')}</span>
                <Button size="sm" onClick={() => enableMutation.mutate(activeLayer)} disabled={enableMutation.isPending}>
                  {t('workspace.agentSettings.codex.hooks.actions.enableFeature')}
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {filteredHooks.map((hook) => {
            const totalMatchers = hook.matchers.length;
            const totalCommands = hook.matchers.reduce((acc, matcher) => acc + matcher.hooks.length, 0);
            const readOnly = hook.readOnly;
            const badgeClass = getAgentSettingsSourceBadgeClassName(hook.layer);

            return (
              <div key={hook.id} className="relative rounded-lg border border-border bg-background p-6">
                <div className="min-w-0">
                  <div className="mb-3 flex flex-wrap items-center gap-3">
                    <h3 className="text-lg font-semibold text-foreground">
                      {t(`workspace.agentSettings.codex.hooks.events.${hook.eventName}.name`, { defaultValue: hook.eventName })}
                    </h3>
                    <Badge
                      variant="outline"
                      className={`text-xs ${badgeClass}`}
                    >
                      {t(`workspace.agentSettings.codex.hooks.scope.badge.${hook.layer}`)}
                    </Badge>
                    <AgentSettingsSourceBadge
                      source={{
                        type: hook.source,
                        label: t(`workspace.agentSettings.codex.hooks.sources.${hook.source}`),
                      }}
                      className="text-xs"
                    />
                  </div>

                  <div className="mb-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Terminal className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium text-muted-foreground">
                        {t('workspace.agentSettings.codex.hooks.matchers.title')}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {hook.matchers.map((matcher, matcherIndex) => (
                        <div key={`${hook.id}-matcher-${matcherIndex}`} className="rounded-lg bg-muted/50 p-3">
                          <div className="mb-2 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {t('workspace.agentSettings.codex.hooks.matchers.matcherLabel')}
                              </span>
                              <code className="rounded bg-muted px-1 text-xs">{matcher.matcher}</code>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {t('workspace.agentSettings.codex.hooks.matchers.actionsCount', { count: matcher.hooks.length })}
                            </span>
                          </div>
                          {matcher.hooks.slice(0, 2).map((action, actionIndex) => (
                            <div key={`${hook.id}-action-${matcherIndex}-${actionIndex}`} className="mb-1 rounded bg-muted px-2 py-1 text-xs">
                              <div className="mb-1 flex items-center gap-2">
                                <Badge variant="outline" className="px-1 py-0 text-xs">
                                  {t('workspace.agentSettings.codex.hooks.matchers.commandLabel')}
                                </Badge>
                                {action.timeout ? (
                                  <span className="text-muted-foreground">
                                    {t('workspace.agentSettings.codex.hooks.matchers.timeoutValue', { value: action.timeout })}
                                  </span>
                                ) : null}
                              </div>
                              <p className="truncate font-mono text-muted-foreground">
                                {action.command?.trim() || t('workspace.agentSettings.codex.hooks.matchers.noCommand')}
                              </p>
                              {action.statusMessage ? (
                                <p className="truncate text-muted-foreground">
                                  {t('workspace.agentSettings.codex.hooks.matchers.statusMessageValue', { value: action.statusMessage })}
                                </p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>

                  {readOnly && hook.rawContent ? (
                    <pre className="mb-4 max-h-28 overflow-auto rounded bg-muted/40 p-3 text-xs">{hook.rawContent}</pre>
                  ) : null}

                  <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                    <span>{t('workspace.agentSettings.codex.hooks.matchers.summary.matchers', { count: totalMatchers })}</span>
                    <span>{t('workspace.agentSettings.codex.hooks.matchers.summary.commands', { count: totalCommands })}</span>
                  </div>
                </div>

                <div className="absolute right-4 top-4 flex items-center gap-2">
                  {!readOnly ? (
                    <>
                      <button
                        type="button"
                        className="rounded-md p-2 transition-colors hover:bg-muted disabled:opacity-50"
                        onClick={() => openEditDialog(hook)}
                        disabled={!isRuntimeReady || isBusy}
                        aria-label={t('workspace.agentSettings.codex.hooks.actions.edit')}
                      >
                        <Edit className="h-4 w-4 text-muted-foreground" />
                      </button>
                      <button
                        type="button"
                        className="rounded-md p-2 transition-colors hover:bg-muted disabled:opacity-50"
                        onClick={() => void deleteHook(hook)}
                        disabled={!isRuntimeReady || isBusy}
                        aria-label={t('workspace.agentSettings.codex.hooks.actions.delete')}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
            );
          })}

          {filteredHooks.length === 0 ? (
            <div className="grid h-48 place-content-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
              {t('workspace.agentSettings.codex.hooks.list.empty')}
            </div>
          ) : null}
        </div>
      </SettingsWorkflowShell>

      <WorkspaceHookDialog
        open={dialogOpen}
        mode={dialogMode}
        hook={toWorkspaceHookData(activeHook)}
        existingHooks={codexHookItems
          .filter((hook) => hook.source === 'hooks_json')
          .map(toWorkspaceHookData)
          .filter((hook): hook is WorkspaceHookData => Boolean(hook))}
        availableScopes={['project', 'user']}
        eventOptions={dialogEventOptions}
        i18nNamespace="workspace.agentSettings.codex"
        matcherHelp={getMatcherHelp}
        supportsStatusMessage
        onClose={() => {
          setDialogOpen(false);
          setActiveHook(null);
        }}
        onSubmit={(hook) => {
          void submitHook(hook);
        }}
      />
    </>
  );
};

export default CodexHooksPage;
