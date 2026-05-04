import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import type { AgentMcpServer, AgentScope } from '../types';
import MCPImportDialog from './dialogs/MCPImportDialog';
import { WorkspaceMCPServerDialog } from './dialogs/WorkspaceMCPServerDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { AgentSettingsSourceBadge, sortAgentSettingsScopeValues } from '../components/SettingsSourcePrimitives';

const ALL_SCOPES: AgentScope[] = ['project', 'user', 'local', 'extension', 'plugin'];
const scopeFilterIcons = {
  project: Building,
  user: User,
  local: Laptop,
  extension: Puzzle,
  plugin: Puzzle,
} satisfies Record<AgentScope, typeof Building>;

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

  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const runtimeError = workspaceRuntime.error;
  const runtimeLoading = workspaceRuntime.isLoading;

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [servers, setServers] = useState<AgentMcpServer[]>([]);
  const [search, setSearch] = useState('');
  const [selectedScope, setSelectedScope] = useState<AgentScope | 'all'>('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [importOpen, setImportOpen] = useState(false);
  const [activeServer, setActiveServer] = useState<AgentMcpServer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleEnvs, setVisibleEnvs] = useState<Record<string, boolean>>({});

  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeError);

  const filteredServers = useMemo(() => {
    let filtered = servers;

    if (selectedScope !== 'all') {
      filtered = filtered.filter((server) => server.scope === selectedScope);
    }

    if (search) {
      const keyword = search.toLowerCase();
      filtered = filtered.filter((server) => {
        if (server.name.toLowerCase().includes(keyword)) return true;
        if (server.command?.toLowerCase().includes(keyword)) return true;
        return server.args?.some((arg) => arg.toLowerCase().includes(keyword));
      });
    }

    return filtered;
  }, [servers, search, selectedScope]);

  const effectiveScopes = useMemo(() => sortAgentSettingsScopeValues(availableScopes), [availableScopes]);

  useEffect(() => {
    if (selectedScope !== 'all' && !effectiveScopes.includes(selectedScope)) {
      setSelectedScope('all');
    }
  }, [effectiveScopes, selectedScope]);

  const fetchServers = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.listMcpServers(runtimeBaseUrl, workspaceId);
      setServers(Array.isArray(response) ? response : []);
    } catch (err) {
      const message = err instanceof Error
        ? err.message
        : t(`${i18nNamespace}.mcp.messages.loadFailed.description`);
      setError(message);
      toast({
        variant: 'destructive',
        title: t(`${i18nNamespace}.mcp.messages.loadFailed.title`),
        description: message,
      });
    } finally {
      setLoading(false);
    }
  }, [runtimeBaseUrl, workspaceId, runtimeError, toast, api, t, i18nNamespace]);

  useEffect(() => {
    if (!isRuntimeReady) {
      setServers([]);
      return;
    }
    void fetchServers();
  }, [isRuntimeReady, fetchServers]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: ['mcp'],
    onRefresh: fetchServers,
  });

  const canEdit = (server: AgentMcpServer): boolean => {
    return server.scope !== 'plugin' && server.scope !== 'extension';
  };

  const canDelete = (server: AgentMcpServer): boolean => {
    return server.scope !== 'plugin' && server.scope !== 'extension';
  };

  const handleOpenCreate = () => {
    setDialogMode('create');
    setActiveServer(null);
    setDialogOpen(true);
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
    setDialogMode('edit');
    setActiveServer(server);
    setDialogOpen(true);
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
        setDialogOpen(false);
        setActiveServer(null);
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
    [runtimeBaseUrl, workspaceId, runtimeError, dialogMode, fetchServers, toast, api, t, i18nNamespace],
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
      if (server.scope === 'plugin' || server.scope === 'extension') {
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
      if (options.scope === 'plugin' || options.scope === 'extension') {
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
                <Select value={selectedScope} onValueChange={(value) => setSelectedScope(value as AgentScope | 'all')}>
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
                onClick={() => void fetchServers()}
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

              {(runtimeLoading || loading) && (
                <div className="flex h-40 flex-col items-center justify-center text-sm text-muted-foreground">
                  <Loader2 className="mb-2 h-5 w-5 animate-spin text-primary" />
                  <span>
                    {t(`${i18nNamespace}.mcp.list.loading`)}
                  </span>
                </div>
              )}

              {!runtimeLoading && !loading &&
                filteredServers.map((server) => (
                  <MCPServerCard
                    key={server.id}
                    server={server}
                    scopeBadge={(
                      <AgentSettingsSourceBadge
                        source={{
                          type: server.scope,
                          label: t(`${i18nNamespace}.mcp.server.scope.${server.scope}`),
                          pluginName: server.pluginName,
                          marketplaceName: server.marketplaceName,
                          extensionName: server.extensionName,
                          extensionVersion: server.extensionVersion,
                        }}
                      />
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
                    supportsToggle={supportsToggle && server.scope !== 'plugin' && server.scope !== 'extension'}
                    canEdit={canEdit(server)}
                    canDelete={canDelete(server)}
                    disabled={!isRuntimeReady}
                    envVisible={visibleEnvs[server.id]}
                    onEdit={handleOpenEdit}
                    onDelete={handleDelete}
                    onToggleStatus={handleToggleStatus}
                    onToggleEnvVisibility={(target) => {
                      setVisibleEnvs((prev) => ({ ...prev, [target.id]: !prev[target.id] }));
                    }}
                  />
                ))}

              {!runtimeLoading && !loading && filteredServers.length === 0 && isRuntimeReady && !error && (
                <div className="grid h-48 place-content-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
                  {t(`${i18nNamespace}.mcp.list.empty`)}
                </div>
              )}
          </div>
        </SettingsWorkflowShell>

        <WorkspaceMCPServerDialog
          open={dialogOpen}
          mode={dialogMode}
          server={activeServer}
          availableScopes={effectiveScopes.filter((scope) => scope !== 'plugin' && scope !== 'extension')}
          i18nNamespace={i18nNamespace}
          onClose={() => {
            setDialogOpen(false);
            setActiveServer(null);
          }}
          onSubmit={handleSubmit}
        />

        <MCPImportDialog
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onImport={handleImport}
          availableScopes={effectiveScopes.filter((scope) => scope !== 'plugin' && scope !== 'extension')}
          i18nNamespace={i18nNamespace}
        />
      
    </TooltipProvider>
  );
};

export default MCPSettingsPage;
