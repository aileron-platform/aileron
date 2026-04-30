import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Zap, Search, RefreshCw, Plus, Edit, Trash2, Terminal, Puzzle, Layers, FolderGit, User, HardDrive } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Button } from '@/shared/components/ui/button';
import {
  WorkspaceHookDialog,
  type EventOption,
  type WorkspaceHookData,
} from './dialogs/WorkspaceHookDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import {
  createAgentSettingsApi,
  buildHookRulesFromAgentHook,
  mapHookScopeDocumentToAgentHooks,
  type AgentHookScopeDocument,
  type AgentHookRuleMap,
  type AgentHookWithEvent,
  type AgentHookMatcher,
} from '../services/agentSettingsApi';
import { SCOPE_BADGE_CLASSES } from '../constants/scopeStyles';
import type { AgentScope, HookEventOption } from '../types';
import { createLogger } from '@/shared/services/logger';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';

const logger = createLogger('HooksSettingsPage');

type AgentHook = AgentHookWithEvent;

type HookScopeState = Record<AgentHook['scope'], AgentHookScopeDocument>;

const createEmptyScopeDocuments = (): HookScopeState => ({
  project: { scope: 'project', hooks: {} },
  user: { scope: 'user', hooks: {} },
  local: { scope: 'local', hooks: {} },
  plugin: { scope: 'plugin', hooks: {} },
});

const cloneRuleMap = (hooks: AgentHookRuleMap | undefined): AgentHookRuleMap => {
  if (!hooks) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(hooks).map(([eventName, rules]) => [
      eventName,
      rules.map((rule) => ({
        matcher: rule.matcher,
        hooks: rule.hooks.map((action) => ({ ...action })),
      })),
    ]),
  );
};

const upsertHookInMap = (
  hooks: AgentHookRuleMap,
  payload: AgentHook,
  previous?: AgentHook | null,
): AgentHookRuleMap => {
  const next = cloneRuleMap(hooks);
  if (previous && previous.scope === payload.scope && previous.eventName !== payload.eventName) {
    delete next[previous.eventName];
  }
  const rules = buildHookRulesFromAgentHook(payload);
  if (rules.length > 0) {
    next[payload.eventName] = rules;
  } else {
    delete next[payload.eventName];
  }
  return next;
};

const removeHookFromMap = (hooks: AgentHookRuleMap, target: AgentHook): AgentHookRuleMap => {
  const next = cloneRuleMap(hooks);
  delete next[target.eventName];
  return next;
};

const ALL_SCOPES: AgentScope[] = ['project', 'user', 'local', 'plugin'];

export interface HooksSettingsPageProps {
  apiPrefix?: string;
  availableScopes?: AgentScope[];
  hookEvents?: HookEventOption[];
  i18nNamespace?: string;
}

const HooksSettingsPage: React.FC<HooksSettingsPageProps> = ({ apiPrefix = 'claude-code', availableScopes = ALL_SCOPES, hookEvents, i18nNamespace = 'workspace.agentSettings.common' }) => {
  const [scopeDocuments, setScopeDocuments] = useState<HookScopeState>(() => createEmptyScopeDocuments());
  const [search, setSearch] = useState('');
  const [scopeFilter, setScopeFilter] = useState<'all' | AgentHook['scope']>('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [activeHook, setActiveHook] = useState<AgentHook | null>(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const { runtimeBaseUrl, workspaceId, error: runtimeError, isLoading: runtimeLoading } = workspaceRuntime;

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const eventLabels = useMemo<Record<string, string>>(
    () => {
      if (hookEvents) {
        return Object.fromEntries(
          hookEvents.map((e) => [e.value, t(e.labelKey)])
        );
      }
      return {
        PostToolUse: t(`${i18nNamespace}.hooks.events.PostToolUse.name`),
        PreToolUse: t(`${i18nNamespace}.hooks.events.PreToolUse.name`),
        Notification: t(`${i18nNamespace}.hooks.events.Notification.name`),
        SessionStart: t(`${i18nNamespace}.hooks.events.SessionStart.name`),
        Stop: t(`${i18nNamespace}.hooks.events.Stop.name`),
        UserPromptSubmit: t(`${i18nNamespace}.hooks.events.UserPromptSubmit.name`),
        SubagentStop: t(`${i18nNamespace}.hooks.events.SubagentStop.name`),
        PreCompact: t(`${i18nNamespace}.hooks.events.PreCompact.name`),
        SessionEnd: t(`${i18nNamespace}.hooks.events.SessionEnd.name`),
      };
    },
    [t, hookEvents, i18nNamespace],
  );

  const describeEvent = (eventName: string) => eventLabels[eventName] ?? eventName;

  const dialogEventOptions = useMemo<EventOption[] | undefined>(() => {
    if (!hookEvents) return undefined;
    return hookEvents.map((e) => ({
      value: e.value,
      label: t(e.optionKey),
    }));
  }, [hookEvents, t]);

  const scopeFilterOptions = useMemo(() => {
    const options: Record<string, string> = {
      all: t(`${i18nNamespace}.hooks.filters.scope.options.all`),
    };
    for (const s of availableScopes) {
      options[s] = t(`${i18nNamespace}.hooks.filters.scope.options.${s}`);
    }
    return options;
  }, [t, availableScopes, i18nNamespace]);

  const hooks = useMemo(
    () =>
      Object.values(scopeDocuments)
        .flatMap((document) => mapHookScopeDocumentToAgentHooks(document))
        .sort((a, b) => a.eventName.localeCompare(b.eventName)),
    [scopeDocuments],
  );

  const filteredHooks = useMemo(() => {
    return hooks.filter((hook) => {
      if (scopeFilter !== 'all' && hook.scope !== scopeFilter) {
        return false;
      }
      if (!search) {
        return true;
      }
      const keyword = search.toLowerCase();
      if (hook.scope.includes(keyword)) return true;
      if (hook.eventName.toLowerCase().includes(keyword)) return true;
      if (describeEvent(hook.eventName).toLowerCase().includes(keyword)) return true;
      return hook.matchers.some((matcher) => {
        if (matcher.matcher.toLowerCase().includes(keyword)) return true;
        return matcher.hooks.some((exec) => exec.command?.toLowerCase().includes(keyword));
      });
    });
  }, [hooks, search, scopeFilter, describeEvent]);

  const refreshHooks = useCallback(async () => {
    if (runtimeLoading) {
      setLoading(true);
      setError(null);
      return;
    }

    if (!runtimeBaseUrl || !workspaceId) {
      setScopeDocuments(createEmptyScopeDocuments());
      if (runtimeError) {
        setError(t(`${i18nNamespace}.agentsMd.status.runtimeUnavailable`, { message: runtimeError }));
      } else {
        setError(t(`${i18nNamespace}.agentsMd.status.runtimeMissing`));
      }
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await api.listHookScopes(runtimeBaseUrl, workspaceId);
      const next = createEmptyScopeDocuments();
      response.scopes.forEach((document) => {
        next[document.scope] = {
          scope: document.scope,
          hooks: cloneRuleMap(document.hooks),
        };
      });
      setScopeDocuments(next);
    } catch (err) {
      const message = err instanceof Error ? err.message : t(`${i18nNamespace}.hooks.messages.loadFailed`);
      setError(message);
      logger.error('Failed to load hooks', { error: err });
    } finally {
      setLoading(false);
    }
  }, [runtimeLoading, runtimeBaseUrl, workspaceId, runtimeError, t, api, i18nNamespace]);

  useEffect(() => {
    refreshHooks();
  }, [refreshHooks]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: ['hooks'],
    onRefresh: refreshHooks,
  });

  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeLoading);
  const isBusy = loading || processing;

  const canEdit = (hook: AgentHook): boolean => {
    return hook.scope !== 'plugin';
  };

  const canDelete = (hook: AgentHook): boolean => {
    return hook.scope !== 'plugin';
  };

  const handleSubmit = async (payload: AgentHook) => {
    if (!runtimeBaseUrl || !workspaceId) {
      if (runtimeError) {
        setError(t(`${i18nNamespace}.agentsMd.status.runtimeUnavailable`, { message: runtimeError }));
      } else {
        setError(t(`${i18nNamespace}.agentsMd.status.runtimeMissing`));
      }
      return;
    }

    setProcessing(true);
    try {
      let nextDocuments: HookScopeState = { ...scopeDocuments };

      if (dialogMode === 'edit' && activeHook) {
        if (activeHook.scope !== payload.scope) {
          const previousDoc = nextDocuments[activeHook.scope] ?? {
            scope: activeHook.scope,
            hooks: {},
          };
          const reducedMap = removeHookFromMap(previousDoc.hooks ?? {}, activeHook);
          if (Object.keys(reducedMap).length === 0) {
            await api.deleteHookScope(runtimeBaseUrl, workspaceId, activeHook.scope);
            nextDocuments = {
              ...nextDocuments,
              [activeHook.scope]: { scope: activeHook.scope, hooks: {} },
            };
          } else {
            const response = await api.updateHookScope(
              runtimeBaseUrl,
              workspaceId,
              activeHook.scope,
              reducedMap,
            );
            nextDocuments = {
              ...nextDocuments,
              [activeHook.scope]: {
                scope: response.scope,
                hooks: cloneRuleMap(response.hooks),
              },
            };
          }
        }
      }

      const referenceDoc = nextDocuments[payload.scope] ?? { scope: payload.scope, hooks: {} };
      const previousInScope =
        dialogMode === 'edit' && activeHook?.scope === payload.scope ? activeHook : null;
      const updatedMap = upsertHookInMap(referenceDoc.hooks ?? {}, payload, previousInScope);
      const response = await api.updateHookScope(
        runtimeBaseUrl,
        workspaceId,
        payload.scope,
        updatedMap,
      );

      nextDocuments = {
        ...nextDocuments,
        [payload.scope]: {
          scope: response.scope,
          hooks: cloneRuleMap(response.hooks),
        },
      };

      setScopeDocuments(nextDocuments);
      setDialogOpen(false);
      setActiveHook(null);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : t(`${i18nNamespace}.hooks.messages.updateFailed`);
      setError(message);
      logger.error('Failed to update hook', { error: err });
    } finally {
      setProcessing(false);
    }
  };

  const handleDelete = async (hook: AgentHook) => {
    if (!canDelete(hook)) {
      return;
    }

    if (!runtimeBaseUrl || !workspaceId) {
      if (runtimeError) {
        setError(t(`${i18nNamespace}.agentsMd.status.runtimeUnavailable`, { message: runtimeError }));
      } else {
        setError(t(`${i18nNamespace}.agentsMd.status.runtimeMissing`));
      }
      return;
    }

    const currentDoc = scopeDocuments[hook.scope];
    if (!currentDoc) {
      return;
    }

    setProcessing(true);
    try {
      const updatedMap = removeHookFromMap(currentDoc.hooks ?? {}, hook);
      if (Object.keys(updatedMap).length === 0) {
        await api.deleteHookScope(runtimeBaseUrl, workspaceId, hook.scope);
        setScopeDocuments((prev) => ({
          ...prev,
          [hook.scope]: { scope: hook.scope, hooks: {} },
        }));
      } else {
        const response = await api.updateHookScope(
          runtimeBaseUrl,
          workspaceId,
          hook.scope,
          updatedMap,
        );
        setScopeDocuments((prev) => ({
          ...prev,
          [hook.scope]: {
            scope: response.scope,
            hooks: cloneRuleMap(response.hooks),
          },
        }));
      }
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : t(`${i18nNamespace}.hooks.messages.deleteFailed`);
      setError(message);
      logger.error('Failed to delete hook', { error: err });
    } finally {
      setProcessing(false);
    }
  };

  const handleOpenCreate = () => {
    setDialogMode('create');
    setActiveHook(null);
    setDialogOpen(true);
  };

  const handleOpenEdit = (hook: AgentHook) => {
    if (!canEdit(hook)) {
      return;
    }
    setDialogMode('edit');
    setActiveHook(hook);
    setDialogOpen(true);
  };



  return (
    <>
      <SettingsWorkflowShell
        title={t(`${i18nNamespace}.hooks.header.title`)}
        icon={Zap}
        headerActions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
              <span className="text-xs text-muted-foreground">
                {t(`${i18nNamespace}.hooks.filters.scope.label`)}
              </span>
              <Select value={scopeFilter} onValueChange={(value) => setScopeFilter(value as typeof scopeFilter)}>
                <SelectTrigger className="h-7 w-32 text-xs">
                  <SelectValue placeholder={t(`${i18nNamespace}.hooks.filters.scope.placeholder`)} />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(scopeFilterOptions).map(([value, label]) => {
                    const icons: Record<string, React.ReactNode> = {
                      all: <Layers className="h-3 w-3" />,
                      project: <FolderGit className="h-3 w-3" />,
                      user: <User className="h-3 w-3" />,
                      local: <HardDrive className="h-3 w-3" />,
                      plugin: <Puzzle className="h-3 w-3" />,
                    };
                    return (
                      <SelectItem key={value} value={value}>
                        <div className="flex items-center gap-2">
                          {icons[value]}
                          {label}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => refreshHooks()}
              disabled={isBusy}
            >
              <RefreshCw className={`mr-1 h-3 w-3 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
              {t(`${i18nNamespace}.hooks.actions.refresh`)}
            </Button>
            <Button
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={handleOpenCreate}
              disabled={!isRuntimeReady || processing}
            >
              <Plus className="mr-1 h-3 w-3" /> {t(`${i18nNamespace}.hooks.actions.create`)}
            </Button>
          </div>
        }
        error={error}
        hasItems
        summary={
          <SettingsWorkflowCountBadge
            label={t(`${i18nNamespace}.hooks.stats.hooks`, { count: filteredHooks.length })}
          />
        }
        controls={
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transform text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t(`${i18nNamespace}.hooks.search.placeholder`)}
              className="h-7 pl-9 text-xs"
            />
          </div>
        }
        emptyTitle={t(`${i18nNamespace}.hooks.header.title`)}
        emptyDescription={t(`${i18nNamespace}.hooks.list.empty`)}
        contentClassName="h-full overflow-y-auto"
      >
        <div className="space-y-4 p-6">
            {filteredHooks.map((hook) => {
              const totalMatchers = hook.matchers.length;
              const totalCommands = hook.matchers.reduce((acc, matcher) => acc + matcher.hooks.length, 0);

              return (
                <div key={hook.id} className="relative rounded-lg border border-border bg-background p-6">
                  <div className="flex items-start">
                    <div className="min-w-0 flex-1">
                      <div className="mb-3 flex items-center gap-3">
                        <h3 className="text-lg font-semibold text-foreground">
                          {describeEvent(hook.eventName)}
                        </h3>
                        <Badge
                          variant="outline"
                          className={`text-xs ${SCOPE_BADGE_CLASSES[hook.scope]}`}
                        >
                          {t(`${i18nNamespace}.hooks.scope.badge.${hook.scope}`)}
                        </Badge>
                        {hook.scope === 'plugin' && hook.pluginName && (
                          <Badge variant="outline" className="flex items-center gap-1 text-xs">
                            <Puzzle className="h-3 w-3" />
                            {hook.pluginName}@{hook.marketplaceName}
                          </Badge>
                        )}
                      </div>

                      <div className="mb-4">
                        <div className="mb-3 flex items-center gap-2">
                          <Terminal className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium text-muted-foreground">
                            {t(`${i18nNamespace}.hooks.matchers.title`)}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {hook.matchers.map((matcher: AgentHookMatcher, matcherIndex) => (
                            <div key={`${hook.id}-matcher-${matcherIndex}`} className="rounded-lg bg-muted/50 p-3">
                              <div className="mb-2 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs text-muted-foreground">
                                    {t(`${i18nNamespace}.hooks.matchers.matcherLabel`)}
                                  </span>
                                  <code className="rounded bg-muted px-1 text-xs">{matcher.matcher}</code>
                                </div>
                                <span className="text-xs text-muted-foreground">
                                  {t(`${i18nNamespace}.hooks.matchers.actionsCount`, {
                                    count: matcher.hooks.length,
                                  })}
                                </span>
                              </div>
                              {matcher.hooks.slice(0, 2).map((exec, execIndex) => (
                                <div key={`${hook.id}-exec-${matcherIndex}-${execIndex}`} className="mb-1 rounded bg-muted px-2 py-1 text-xs">
                                  <div className="mb-1 flex items-center gap-2">
                                    <Badge variant="outline" className="px-1 py-0 text-xs">
                                      {t(`${i18nNamespace}.hooks.matchers.commandLabel`)}
                                    </Badge>
                                    {exec.timeout && (
                                      <span className="text-muted-foreground">
                                        {t(`${i18nNamespace}.hooks.matchers.timeoutValue`, {
                                          value: exec.timeout,
                                        })}
                                      </span>
                                    )}
                                  </div>
                                  <p className="truncate font-mono text-muted-foreground">
                                    {exec.command?.trim()
                                      ? exec.command
                                      : t(`${i18nNamespace}.hooks.matchers.noCommand`)}
                                  </p>
                                </div>
                              ))}
                              {matcher.hooks.length > 2 && (
                                <div className="text-xs italic text-muted-foreground">
                                  {t(`${i18nNamespace}.hooks.matchers.moreActions`, {
                                    count: matcher.hooks.length - 2,
                                  })}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="flex gap-4 rounded bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                        <span>
                          {t(`${i18nNamespace}.hooks.matchers.summary.matchers`, {
                            count: totalMatchers,
                          })}
                        </span>
                        <span>
                          {t(`${i18nNamespace}.hooks.matchers.summary.commands`, {
                            count: totalCommands,
                          })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="absolute top-4 right-4 flex items-center gap-2">
                    {canEdit(hook) && (
                      <button
                        type="button"
                        className="rounded-md p-2 transition-colors hover:bg-muted disabled:opacity-50"
                        onClick={() => handleOpenEdit(hook)}
                        disabled={!isRuntimeReady || processing}
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
                        onClick={() => handleDelete(hook)}
                        disabled={!isRuntimeReady || processing}
                        aria-label={t(`${i18nNamespace}.hooks.actions.delete`)}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                        <span className="sr-only">{t(`${i18nNamespace}.hooks.actions.delete`)}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {filteredHooks.length === 0 && (
              <div className="grid h-48 place-content-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
                {t(`${i18nNamespace}.hooks.list.empty`)}
              </div>
            )}
        </div>
      </SettingsWorkflowShell>

      <WorkspaceHookDialog
        open={dialogOpen}
        mode={dialogMode}
        hook={activeHook}
        existingHooks={hooks}
        availableScopes={availableScopes}
        eventOptions={dialogEventOptions}
        i18nNamespace={i18nNamespace}
        onClose={() => {
          setDialogOpen(false);
          setActiveHook(null);
        }}
        onSubmit={(hook) => {
          void handleSubmit(hook);
        }}
      />
    </>
  );
};

export default HooksSettingsPage;
