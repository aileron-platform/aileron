import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Wrench, Search, Upload, Plus, Loader2, AlertCircle, Building, User, Layers, Laptop, Puzzle, RefreshCw } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { MCPServerCard } from '@/shared/components/mcp-workflow';
import type { AgentScope } from '../../model/documents';
import type {
  AgentMcpServer,
  CodexPluginMcpPolicy,
} from '../../model/mcp';
import MCPImportDialog from '../../components/dialogs/MCPImportDialog';
import { WorkspaceMCPServerDialog } from '../../components/dialogs/WorkspaceMCPServerDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import {
  getWritableAgentScopes,
  isReadOnlyAgentScope,
  resolveAgentSettingsSelectedScope,
  type AgentSettingsScopeSelection,
} from '../../agentSettingsScopeModel';
import {
  SettingsListWorkbench,
  SettingsWorkflowCountBadge,
  SettingsWorkflowShell,
  useSettingsListController,
} from '@/shared/components/settings-workflow';
import { DocumentSourceBadge } from '@/shared/components/document-resource';
import { sortAgentSettingsScopeValues } from '../../components/AgentSettingsSourceControls';
import {
  getCodexPluginControlErrorKey,
  invalidateProviderResourceQueries,
} from '../../model/pluginResources';
import CodexPluginMcpPolicyControl from './CodexPluginMcpPolicyControl';
import { agentSettingsQueryKeys } from '../../api/agentSettingsQueryKeys';

const ALL_SCOPES: AgentScope[] = ['project', 'user', 'local', 'plugin'];
const scopeFilterIcons = {
  project: Building,
  user: User,
  local: Laptop,
  plugin: Puzzle,
} satisfies Record<AgentScope, typeof Building>;

const hasCodexPluginMcpPolicy = (
  server: AgentMcpServer,
): server is AgentMcpServer & {
  pluginId: string;
  serverId: string;
  policy: CodexPluginMcpPolicy;
  policyRevision: string;
} => (
  server.scope === 'plugin'
  && Boolean(
    server.pluginId
    && server.serverId
    && server.policy
    && server.policyRevision,
  )
);

export interface MCPSettingsPageProps {
  apiPrefix?: string;
  availableScopes?: AgentScope[];
  supportsToggle?: boolean;
  i18nNamespace?: string;
}

const MCPSettingsPage: React.FC<MCPSettingsPageProps> = ({ apiPrefix = 'claude-code', availableScopes = ALL_SCOPES, supportsToggle = true, i18nNamespace = 'workspace.agentSettings.common' }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const queryClient = useQueryClient();

  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const runtimeError = workspaceRuntime.error;
  const runtimeLoading = workspaceRuntime.isLoading;

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [importOpen, setImportOpen] = useState(false);
  const [visibleEnvs, setVisibleEnvs] = useState<Record<string, boolean>>({});

  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeError);
  const provider = apiPrefix === 'codex' ? 'codex' : 'claude-code';
  const serverQueryKey = useMemo(
    () => agentSettingsQueryKeys.collection({
      runtimeBaseUrl: runtimeBaseUrl ?? '',
      workspaceId: workspaceId ?? '',
      provider,
      capability: 'mcp',
      scope: 'all',
    }),
    [
      provider,
      runtimeBaseUrl,
      workspaceId,
    ],
  );
  const serversQuery = useQuery({
    queryKey: serverQueryKey,
    queryFn: async ({ signal }) => {
      const response = await api.listMcpServers(
        runtimeBaseUrl ?? '',
        workspaceId ?? '',
        signal,
      );
      return Array.isArray(response) ? response : [];
    },
    enabled: isRuntimeReady,
    staleTime: 5 * 60 * 1000,
  });
  const servers = serversQuery.data ?? [];
  const loading = serversQuery.isLoading || serversQuery.isFetching;
  const queryError = serversQuery.error;
  const error = queryError
    ? apiPrefix === 'codex'
      ? t(getCodexPluginControlErrorKey('mcp-policy', queryError))
      : t(`${i18nNamespace}.mcp.messages.loadFailed.description`)
    : null;
  const refetchServers = serversQuery.refetch;

  const getServerSearchText = useCallback((server: AgentMcpServer) => [
    server.name,
    server.command,
    ...(server.args ?? []),
  ], []);

  const {
    filteredItems: filteredServers,
    selectedItem: activeServer,
    scope: selectedScope,
    setScope: setSelectedScope,
    query: search,
    setQuery: setSearch,
    editorMode: dialogMode,
    editorOpen: dialogOpen,
    openCreate,
    openEdit,
    closeEditor,
  } = useSettingsListController<AgentMcpServer>(servers, {
    getScope: (server) => server.scope,
    getSearchText: getServerSearchText,
  });

  const effectiveScopes = useMemo(() => sortAgentSettingsScopeValues(availableScopes), [availableScopes]);
  const writableScopes = useMemo(() => getWritableAgentScopes(effectiveScopes), [effectiveScopes]);

  useEffect(() => {
    const currentScope = selectedScope as AgentSettingsScopeSelection;
    const nextScope = resolveAgentSettingsSelectedScope(
      currentScope,
      effectiveScopes,
    );
    if (nextScope !== selectedScope) {
      setSelectedScope(nextScope);
    }
  }, [effectiveScopes, selectedScope, setSelectedScope]);

  useEffect(() => {
    if (!queryError) {
      return;
    }
    toast({
      variant: 'destructive',
      title: t(`${i18nNamespace}.mcp.messages.loadFailed.title`),
      description: error ?? t(`${i18nNamespace}.mcp.messages.loadFailed.description`),
    });
  }, [error, i18nNamespace, queryError, t, toast]);

  const fetchServers = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      return;
    }
    await refetchServers();
  }, [
    runtimeBaseUrl,
    runtimeError,
    refetchServers,
    workspaceId,
  ]);

  const refreshServers = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) return;
    await api.refreshCache(runtimeBaseUrl, workspaceId, {
      provider,
      capability: 'mcp',
      scope: 'all',
    });
    queryClient.removeQueries({ queryKey: serverQueryKey, exact: true });
    await refetchServers();
  }, [
    api,
    provider,
    queryClient,
    refetchServers,
    runtimeBaseUrl,
    runtimeError,
    serverQueryKey,
    workspaceId,
  ]);

  const canEdit = (server: AgentMcpServer): boolean => {
    return !isReadOnlyAgentScope(server.scope);
  };

  const canDelete = (server: AgentMcpServer): boolean => {
    return !isReadOnlyAgentScope(server.scope);
  };

  const handleOpenCreate = () => {
    openCreate();
  };

  const handleOpenEdit = (server: AgentMcpServer) => {
    if (!canEdit(server)) {
      toast({
        variant: 'destructive',
        title: t(`${i18nNamespace}.mcp.messages.editForbidden.title`),
        description: t(`${i18nNamespace}.mcp.messages.editForbidden.description`),
      });
      return;
    }
    openEdit(server);
  };

  const handleSubmit = useCallback(
    async (payload: AgentMcpServer) => {
      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        throw new Error(t(`${i18nNamespace}.mcp.messages.runtimeNotReady`));
      }

      const normalized: AgentMcpServer = {
        ...payload,
        id: `${payload.scope}:${payload.name}`,
        command: payload.command?.trim(),
        args: payload.args?.map((arg) => arg.trim()).filter(Boolean),
        env: payload.env,
        headers: payload.headers,
      };

      try {
        if (dialogMode === 'create') {
          await api.createMcpServer(runtimeBaseUrl, workspaceId, normalized);
          toast({
            title: t(`${i18nNamespace}.mcp.messages.createSuccess.title`),
            description: normalized.name,
          });
        } else {
          await api.updateMcpServer(runtimeBaseUrl, workspaceId, normalized);
          toast({
            title: t(`${i18nNamespace}.mcp.messages.updateSuccess.title`),
            description: normalized.name,
          });
        }
        await fetchServers();
        closeEditor();
      } catch (err) {
        const message = err instanceof Error
          ? err.message
          : t(`${i18nNamespace}.mcp.messages.operationFailed.description`);
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.operationFailed.title`),
          description: message,
        });
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, dialogMode, fetchServers, closeEditor, toast, api, t, i18nNamespace],
  );

  const handleDelete = useCallback(
    async (server: AgentMcpServer) => {
      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.operationFailed.title`),
          description: t(`${i18nNamespace}.mcp.messages.runtimeNotReady`),
        });
        return;
      }

      if (!canDelete(server)) {
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.deleteForbidden.title`),
          description: t(`${i18nNamespace}.mcp.messages.deleteForbidden.description`),
        });
        return;
      }

      const confirmed = window.confirm(
        t(`${i18nNamespace}.mcp.confirm.delete`, {
          name: server.name,
        }) as string,
      );
      if (!confirmed) {
        return;
      }

      try {
        await api.deleteMcpServer(runtimeBaseUrl, workspaceId, server);
        toast({
          title: t(`${i18nNamespace}.mcp.messages.deleteSuccess.title`),
          description: server.name,
        });
        await fetchServers();
      } catch (err) {
        const message = err instanceof Error
          ? err.message
          : t(`${i18nNamespace}.mcp.messages.deleteFailed.description`);
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.deleteFailed.title`),
          description: message,
        });
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, fetchServers, toast, t, api, i18nNamespace],
  );

  const handleToggleStatus = useCallback(
    async (server: AgentMcpServer, enabled: boolean) => {
      if (isReadOnlyAgentScope(server.scope)) {
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.pluginReadOnly.title`),
          description: t(`${i18nNamespace}.mcp.messages.pluginReadOnly.description`),
        });
        return;
      }

      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.operationFailed.title`),
          description: t(`${i18nNamespace}.mcp.messages.runtimeNotReady`),
        });
        return;
      }

      try {
        await api.toggleMcpServerStatus(runtimeBaseUrl, workspaceId, server, enabled);
        toast({
          title: enabled
            ? t(`${i18nNamespace}.mcp.messages.toggleEnabled.title`)
            : t(`${i18nNamespace}.mcp.messages.toggleDisabled.title`),
          description: server.name,
        });
        await fetchServers();
      } catch (err) {
        const message = err instanceof Error
          ? err.message
          : t(`${i18nNamespace}.mcp.messages.toggleFailed.description`);
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.operationFailed.title`),
          description: message,
        });
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, fetchServers, toast, api, t, i18nNamespace],
  );

  const handleImport = useCallback(
    async (options: { scope: AgentMcpServer['scope']; file: File; overwrite?: boolean }) => {
      if (isReadOnlyAgentScope(options.scope)) {
        throw new Error(t(`${i18nNamespace}.mcp.messages.pluginReadOnly.description`));
      }

      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        throw new Error(t(`${i18nNamespace}.mcp.messages.runtimeNotReady`));
      }

      try {
        const result = await api.importMcpServers(runtimeBaseUrl, workspaceId, options);
        await fetchServers();
        toast({
          title: t(`${i18nNamespace}.mcp.messages.importSuccess.title`),
          description: t(`${i18nNamespace}.mcp.messages.importSuccess.description`, {
            created: result.created.length,
            updated: result.updated.length,
            skipped: result.skipped.length,
          }),
        });
        return result;
      } catch (err) {
        const message = err instanceof Error
          ? err.message
          : t(`${i18nNamespace}.mcp.messages.importFailed.description`);
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.messages.importFailed.title`),
          description: message,
        });
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, fetchServers, toast, api, t, i18nNamespace],
  );

  const handlePluginPolicySave = useCallback(
    async (server: AgentMcpServer, policy: CodexPluginMcpPolicy) => {
      if (
        apiPrefix !== 'codex'
        || !runtimeBaseUrl
        || !workspaceId
        || runtimeError
        || !hasCodexPluginMcpPolicy(server)
      ) {
        throw new Error(t(`${i18nNamespace}.mcp.messages.runtimeNotReady`));
      }

      try {
        await api.updateCodexPluginMcpPolicy(
          runtimeBaseUrl,
          workspaceId,
          server.pluginId,
          server.serverId,
          policy,
          server.policyRevision,
        );
        toast({
          title: t(`${i18nNamespace}.mcp.pluginPolicy.messages.saveSuccess`),
          description: server.name,
        });
        await invalidateProviderResourceQueries(
          queryClient,
          'codex',
          workspaceId,
        );
      } catch (err) {
        const message = t(getCodexPluginControlErrorKey('mcp-policy', err));
        toast({
          variant: 'destructive',
          title: t(`${i18nNamespace}.mcp.pluginPolicy.messages.saveFailed`),
          description: message,
        });
        throw err;
      }
    },
    [
      api,
      apiPrefix,
      i18nNamespace,
      queryClient,
      runtimeBaseUrl,
      runtimeError,
      t,
      toast,
      workspaceId,
    ],
  );

  return (
    <TooltipProvider>
      <SettingsWorkflowShell
        title={t(`${i18nNamespace}.mcp.header.title`)}
        icon={Wrench}
        headerActions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
              <span className="text-xs text-muted-foreground">
                {t(`${i18nNamespace}.mcp.server.scope.label`)}
              </span>
              <Select
                value={selectedScope}
                onValueChange={(value) => setSelectedScope(value as AgentScope | 'all')}
              >
                <SelectTrigger className="h-7 w-32 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    <div className="flex items-center gap-2">
                      <Layers className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.all`)}
                    </div>
                  </SelectItem>
                  {effectiveScopes.map((scopeOption) => {
                    const Icon = scopeFilterIcons[scopeOption];
                    return (
                      <SelectItem key={scopeOption} value={scopeOption}>
                        <div className="flex items-center gap-2">
                          <Icon className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.${scopeOption}`)}
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
              onClick={() => void refreshServers()}
              disabled={!isRuntimeReady || loading || runtimeLoading}
            >
              <RefreshCw className={`mr-1 h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
              {t(`${i18nNamespace}.mcp.header.actions.refresh`)}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => setImportOpen(true)}
              disabled={!isRuntimeReady}
            >
              <Upload className="mr-1 h-3 w-3" /> {t(`${i18nNamespace}.mcp.header.actions.import`)}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs" onClick={handleOpenCreate} disabled={!isRuntimeReady}>
              <Plus className="mr-1 h-3 w-3" /> {t(`${i18nNamespace}.mcp.header.actions.create`)}
            </Button>
          </div>
        }
        hasItems
        summary={
          <SettingsWorkflowCountBadge
            label={t(`${i18nNamespace}.mcp.stats.total`, { count: filteredServers.length })}
          />
        }
        controls={
          <div className="relative w-full max-w-md">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transform text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t(`${i18nNamespace}.mcp.search.placeholder`)}
              className="h-7 pl-9 text-xs"
            />
          </div>
        }
        emptyTitle={t(`${i18nNamespace}.mcp.header.title`)}
        emptyDescription={t(`${i18nNamespace}.mcp.list.empty`)}
        contentClassName="h-full overflow-y-auto"
      >
        <div className="space-y-4 p-6">
          {!isRuntimeReady && !runtimeLoading && (
            <Alert>
              <AlertDescription>
                {t(`${i18nNamespace}.mcp.status.runtimeUnavailable`, {
                  message: t(`${i18nNamespace}.mcp.messages.runtimeNotReady`),
                })}
              </AlertDescription>
            </Alert>
          )}

          {runtimeError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{runtimeError}</AlertDescription>
            </Alert>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <SettingsListWorkbench
            items={filteredServers}
            getItemKey={(server) => server.id}
            isLoading={runtimeLoading || loading}
            loading={(
              <div className="flex h-40 flex-col items-center justify-center text-sm text-muted-foreground">
                <Loader2 className="mb-2 h-5 w-5 animate-spin text-primary" />
                <span>{t(`${i18nNamespace}.mcp.list.loading`)}</span>
              </div>
            )}
            i18nKeys={{
              emptyTitle: `${i18nNamespace}.mcp.header.title`,
              emptyDescription: `${i18nNamespace}.mcp.list.empty`,
            }}
            card={(server) => (
              <MCPServerCard
                key={server.id}
                server={server}
                scopeBadge={(
                  <span className="inline-flex flex-wrap items-center gap-1">
                    <DocumentSourceBadge
                      source={{
                        type: server.scope,
                        label: t(`${i18nNamespace}.mcp.server.scope.${server.scope}`),
                        pluginName: server.pluginName,
                        marketplaceName: server.marketplaceName,
                      }}
                    />
                  </span>
                )}
                labels={{
                  enabled: t(`${i18nNamespace}.mcp.server.status.enabled`),
                  disabled: t(`${i18nNamespace}.mcp.server.status.disabled`),
                  transportType: t(`${i18nNamespace}.mcp.serverDetails.transportType`),
                  serverUrl: t(`${i18nNamespace}.mcp.serverDetails.serverUrl`),
                  headers: t(`${i18nNamespace}.mcp.serverDetails.headers`),
                  command: t(`${i18nNamespace}.mcp.serverDetails.command`),
                  commandArgs: t(`${i18nNamespace}.mcp.serverDetails.commandArgs`),
                  env: t(`${i18nNamespace}.mcp.serverDetails.env`),
                  showEnvValues: t(`${i18nNamespace}.mcp.actions.showEnvValues`),
                  hideEnvValues: t(`${i18nNamespace}.mcp.actions.hideEnvValues`),
                  edit: t(`${i18nNamespace}.mcp.actions.edit`),
                  delete: t(`${i18nNamespace}.mcp.actions.delete`),
                  readOnlyTooltip: t(`${i18nNamespace}.mcp.plugin.readonly`),
                }}
                supportsToggle={supportsToggle && !isReadOnlyAgentScope(server.scope)}
                canEdit={canEdit(server)}
                canDelete={canDelete(server)}
                disabled={!isRuntimeReady}
                envVisible={visibleEnvs[server.id]}
                policyControl={(
                  apiPrefix === 'codex' && hasCodexPluginMcpPolicy(server)
                    ? (
                      <CodexPluginMcpPolicyControl
                        server={server}
                        disabled={!isRuntimeReady}
                        i18nNamespace={i18nNamespace}
                        onSave={handlePluginPolicySave}
                      />
                    )
                    : null
                )}
                onEdit={handleOpenEdit}
                onDelete={handleDelete}
                onToggleStatus={handleToggleStatus}
                onToggleEnvVisibility={(target) => {
                  setVisibleEnvs((prev) => ({ ...prev, [target.id]: !prev[target.id] }));
                }}
              />
            )}
            dialog={(
              <>
                <WorkspaceMCPServerDialog
                  open={dialogOpen}
                  mode={dialogMode}
                  server={activeServer}
                  availableScopes={writableScopes}
                  i18nNamespace={i18nNamespace}
                  onClose={closeEditor}
                  onSubmit={handleSubmit}
                />

                <MCPImportDialog
                  open={importOpen}
                  onClose={() => setImportOpen(false)}
                  onImport={handleImport}
                  availableScopes={writableScopes}
                  i18nNamespace={i18nNamespace}
                />
              </>
            )}
          />
        </div>
      </SettingsWorkflowShell>
    </TooltipProvider>
  );
};

export default MCPSettingsPage;
