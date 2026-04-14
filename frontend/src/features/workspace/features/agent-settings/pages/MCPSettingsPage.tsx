import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Wrench, Search, Edit, Trash2, Upload, Plus, Loader2, AlertCircle, Building, User, Layers, Laptop, Puzzle, Info, Eye, EyeOff } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Switch } from '@/shared/components/ui/switch';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import type { ClaudeMcpServer, ClaudeScope } from '../../claude-code/data';

const ALL_SCOPES: ClaudeScope[] = ['project', 'user', 'local', 'plugin'];
import { MCPServerDialog } from '@/shared/components/dialogs';
import MCPImportDialog from './dialogs/MCPImportDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { useToast } from '@/shared/components/ui/use-toast';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import { SCOPE_BADGE_CLASSES } from '../constants/scopeStyles';

export interface MCPSettingsPageProps {
  apiPrefix?: string;
  availableScopes?: ClaudeScope[];
  supportsToggle?: boolean;
  i18nNamespace?: string;
}

const MCPSettingsPage: React.FC<MCPSettingsPageProps> = ({ apiPrefix = 'claude-code', availableScopes = ALL_SCOPES, supportsToggle = true, i18nNamespace = 'workspace.claudeCode' }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();

  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const runtimeError = workspaceRuntime.error;
  const runtimeLoading = workspaceRuntime.isLoading;

  const api = useMemo(() => createAgentSettingsApi(apiPrefix), [apiPrefix]);

  const [servers, setServers] = useState<ClaudeMcpServer[]>([]);
  const [search, setSearch] = useState('');
  const [selectedScope, setSelectedScope] = useState<ClaudeScope | 'all'>('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit'>('create');
  const [importOpen, setImportOpen] = useState(false);
  const [activeServer, setActiveServer] = useState<ClaudeMcpServer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleEnvs, setVisibleEnvs] = useState<Record<string, boolean>>({});

  const isRuntimeReady = Boolean(runtimeBaseUrl && workspaceId && !runtimeError);

  const filteredServers = useMemo(() => {
    let filtered = servers;

    // 按 scope 篩選
    if (selectedScope !== 'all') {
      filtered = filtered.filter((server) => server.scope === selectedScope);
    }

    // 按搜尋關鍵字篩選
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

  const fetchServers = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId || runtimeError) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.listMcpServers(runtimeBaseUrl, workspaceId);
      setServers(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : '無法載入 MCP 伺服器列表';
      setError(message);
      toast({
        variant: 'destructive',
        title: '載入失敗',
        description: message,
      });
    } finally {
      setLoading(false);
    }
  }, [runtimeBaseUrl, workspaceId, runtimeError, toast, api]);

  useEffect(() => {
    if (!isRuntimeReady) {
      setServers([]);
      return;
    }
    void fetchServers();
  }, [isRuntimeReady, fetchServers]);

  // 權限檢查函數
  const canEdit = (server: ClaudeMcpServer): boolean => {
    return server.scope !== 'plugin';
  };

  const canDelete = (server: ClaudeMcpServer): boolean => {
    return server.scope !== 'plugin';
  };

  const handleOpenCreate = () => {
    setDialogMode('create');
    setActiveServer(null);
    setDialogOpen(true);
  };

  const handleOpenEdit = (server: ClaudeMcpServer) => {
    if (!canEdit(server)) {
      toast({
        variant: 'destructive',
        title: '無法編輯',
        description: 'Plugin 提供的 MCP Server 為唯讀',
      });
      return;
    }
    setDialogMode('edit');
    setActiveServer(server);
    setDialogOpen(true);
  };

  const handleSubmit = useCallback(
    async (payload: ClaudeMcpServer) => {
      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        throw new Error('Workspace Runtime 尚未就緒');
      }

      const normalized: ClaudeMcpServer = {
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
          toast({ title: '已建立 MCP 伺服器', description: normalized.name });
        } else {
          await api.updateMcpServer(runtimeBaseUrl, workspaceId, normalized);
          toast({ title: '已更新 MCP 伺服器', description: normalized.name });
        }
        await fetchServers();
        setDialogOpen(false);
        setActiveServer(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'MCP 伺服器操作失敗';
        toast({ variant: 'destructive', title: '操作失敗', description: message });
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, dialogMode, fetchServers, toast, api],
  );

  const handleDelete = useCallback(
    async (server: ClaudeMcpServer) => {
      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        toast({ variant: 'destructive', title: '操作失敗', description: 'Workspace Runtime 尚未就緒' });
        return;
      }

      if (!canDelete(server)) {
        toast({
          variant: 'destructive',
          title: '無法刪除',
          description: 'Plugin 提供的 MCP Server 為唯讀',
        });
        return;
      }

      const confirmed = window.confirm(
        t(`${i18nNamespace}.mcp.confirm.delete`, {
          defaultValue: '確定要刪除「{{name}}」嗎？',
          name: server.name,
        }) as string,
      );
      if (!confirmed) {
        return;
      }

      try {
        await api.deleteMcpServer(runtimeBaseUrl, workspaceId, server);
        toast({ title: '已刪除 MCP 伺服器', description: server.name });
        await fetchServers();
      } catch (err) {
        const message = err instanceof Error ? err.message : '刪除失敗';
        toast({ variant: 'destructive', title: '刪除失敗', description: message });
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, fetchServers, toast, t, api, i18nNamespace],
  );

  const handleToggleStatus = useCallback(
    async (server: ClaudeMcpServer, enabled: boolean) => {
      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        toast({ variant: 'destructive', title: '操作失敗', description: 'Workspace Runtime 尚未就緒' });
        return;
      }

      try {
        await api.toggleMcpServerStatus(runtimeBaseUrl, workspaceId, server, enabled);
        toast({
          title: enabled ? '已啟用 MCP 伺服器' : '已停用 MCP 伺服器',
          description: server.name,
        });
        await fetchServers();
      } catch (err) {
        const message = err instanceof Error ? err.message : '切換狀態失敗';
        toast({ variant: 'destructive', title: '操作失敗', description: message });
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, fetchServers, toast, api],
  );

  const handleImport = useCallback(
    async (options: { scope: ClaudeMcpServer['scope']; file: File; overwrite?: boolean }) => {
      if (!runtimeBaseUrl || !workspaceId || runtimeError) {
        throw new Error('Workspace Runtime 尚未就緒');
      }

      try {
        const result = await api.importMcpServers(runtimeBaseUrl, workspaceId, options);
        await fetchServers();
        toast({
          title: '匯入完成',
          description: `新增 ${result.created.length}、更新 ${result.updated.length}、跳過 ${result.skipped.length}`,
        });
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : '匯入失敗';
        toast({ variant: 'destructive', title: '匯入失敗', description: message });
        throw err instanceof Error ? err : new Error(message);
      }
    },
    [runtimeBaseUrl, workspaceId, runtimeError, fetchServers, toast, api],
  );


  return (
    <TooltipProvider>
      <div className="flex h-full flex-col bg-background">
        <FeatureHeader
          title={t(`${i18nNamespace}.mcp.header.title`)}
          icon={Wrench}
          actions={
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-1">
                <span className="text-xs text-muted-foreground">
                  {t(`${i18nNamespace}.mcp.server.scope.label`)}
                </span>
                <Select value={selectedScope} onValueChange={(value) => setSelectedScope(value as ClaudeScope | 'all')}>
                  <SelectTrigger className="h-7 w-32 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      <div className="flex items-center gap-2">
                        <Layers className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.all`)}
                      </div>
                    </SelectItem>
                    {availableScopes.includes('project') && (
                      <SelectItem value="project">
                        <div className="flex items-center gap-2">
                          <Building className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.project`)}
                        </div>
                      </SelectItem>
                    )}
                    {availableScopes.includes('user') && (
                      <SelectItem value="user">
                        <div className="flex items-center gap-2">
                          <User className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.user`)}
                        </div>
                      </SelectItem>
                    )}
                    {availableScopes.includes('local') && (
                      <SelectItem value="local">
                        <div className="flex items-center gap-2">
                          <Laptop className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.local`)}
                        </div>
                      </SelectItem>
                    )}
                    {availableScopes.includes('plugin') && (
                      <SelectItem value="plugin">
                        <div className="flex items-center gap-2">
                          <Puzzle className="h-3 w-3" /> {t(`${i18nNamespace}.mcp.server.scope.plugin`, { defaultValue: 'Plugins' })}
                        </div>
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>
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
        />

        <div className="flex-1 overflow-hidden">
          <div className="h-full overflow-y-auto">
            <div className="flex h-10 items-center border-b border-border bg-background px-4">
              <div className="flex items-center justify-between gap-4 w-full">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <Wrench className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">
                      {t(`${i18nNamespace}.mcp.stats.title`)}
                    </span>
                  </div>
                  <Badge variant="secondary" className="text-[11px]">
                    {t(`${i18nNamespace}.mcp.stats.total`, { count: filteredServers.length })}
                  </Badge>
                </div>
                <div className="relative w-64">
                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transform text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={t(`${i18nNamespace}.mcp.search.placeholder`)}
                    className="h-7 pl-9 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4 p-6">
              {!isRuntimeReady && !runtimeLoading && (
                <Alert>
                  <AlertDescription>
                    {t(`${i18nNamespace}.mcp.status.runtimeUnavailable`, {
                      defaultValue: 'Workspace Runtime 尚未就緒，請稍後再試。',
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
                    {t(`${i18nNamespace}.mcp.list.loading`, {
                      defaultValue: '載入 MCP 伺服器中…',
                    })}
                  </span>
                </div>
              )}

              {!runtimeLoading && !loading &&
                filteredServers.map((server) => (
                  <div
                    key={server.id}
                    className={`rounded-lg border border-border bg-background p-6 transition-all ${supportsToggle && server.enabled === false ? 'opacity-60 bg-muted/30' : ''
                      }`}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-3 flex-wrap">
                          <h3 className="text-lg font-semibold text-foreground">{server.name}</h3>
                          <Badge className={SCOPE_BADGE_CLASSES[server.scope]}>
                            {t(`${i18nNamespace}.mcp.server.scope.${server.scope}`, { defaultValue: server.scope })}
                          </Badge>

                          {/* Plugin 來源標記 */}
                          {server.scope === 'plugin' && server.pluginName && (
                            <Badge variant="outline" className="flex items-center gap-1 text-xs">
                              <Puzzle className="h-3 w-3" />
                              {server.pluginName}@{server.marketplaceName}
                            </Badge>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 ml-4">
                        {supportsToggle && (
                          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/50">
                            <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                              {server.enabled !== false
                                ? t(`${i18nNamespace}.mcp.server.status.enabled`, { defaultValue: '啟用' })
                                : t(`${i18nNamespace}.mcp.server.status.disabled`, { defaultValue: '停用' })}
                            </span>
                            <Switch
                              checked={server.enabled !== false}
                              onCheckedChange={(checked) => handleToggleStatus(server, checked)}
                              disabled={!isRuntimeReady}
                            />
                          </div>
                        )}

                        {/* 非 plugin scope：顯示編輯和刪除按鈕 */}
                        {canEdit(server) && (
                          <>
                            <button
                              type="button"
                              className="rounded-md p-2 transition-colors hover:bg-muted"
                              onClick={() => handleOpenEdit(server)}
                              disabled={!isRuntimeReady}
                            >
                              <Edit className="h-4 w-4 text-muted-foreground" />
                            </button>
                            <button
                              type="button"
                              className="rounded-md p-2 transition-colors hover:bg-muted"
                              onClick={() => handleDelete(server)}
                              disabled={!isRuntimeReady}
                            >
                              <Trash2 className="h-4 w-4 text-muted-foreground" />
                            </button>
                          </>
                        )}

                        {/* Plugin scope：顯示提示訊息 */}
                        {server.scope === 'plugin' && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                className="rounded-md p-2 text-muted-foreground cursor-help"
                                disabled
                              >
                                <Info className="h-4 w-4" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-xs">
                              <p className="text-sm">
                                {t(`${i18nNamespace}.mcp.plugin.readonly`, {
                                  defaultValue: 'Plugin 提供的 MCP Server 為唯讀。可以啟用/停用，但無法編輯或刪除。',
                                })}
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    </div>

                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-muted-foreground min-w-[80px]">
                          {t(`${i18nNamespace}.mcp.serverDetails.transportType`)}:
                        </span>
                        <span className="font-mono bg-muted px-2 py-1 text-xs">
                          {(server.transport ?? 'stdio').toUpperCase()}
                        </span>
                      </div>
                      {(server.transport === 'http' || server.transport === 'sse') && server.url && (
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-muted-foreground min-w-[80px]">
                            {t(`${i18nNamespace}.mcp.serverDetails.serverUrl`)}:
                          </span>
                          <span className="font-mono text-xs break-all">{server.url}</span>
                        </div>
                      )}
                      {(server.transport === 'http' || server.transport === 'sse') && server.headers && Object.keys(server.headers).length > 0 && (
                        <div className="flex items-start gap-2">
                          <span className="font-medium text-muted-foreground min-w-[80px]">
                            {t(`${i18nNamespace}.mcp.serverDetails.headers`)}:
                          </span>
                          <div className="flex-1 space-y-1">
                            {Object.entries(server.headers).map(([key, value]) => (
                              <div key={key} className="bg-muted/30 rounded px-2 py-1">
                                <span className="font-mono text-xs break-all">
                                  <span className="text-blue-600 dark:text-blue-400 font-semibold">{key}</span>
                                  <span className="text-muted-foreground mx-1">:</span>
                                  <span className="text-foreground">{value}</span>
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {server.transport === 'stdio' && (
                        <>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-muted-foreground min-w-[80px]">
                              {t(`${i18nNamespace}.mcp.serverDetails.command`)}:
                            </span>
                            <span className="font-mono text-xs">{server.command ?? '-'}</span>
                          </div>
                          {server.args && server.args.length > 0 && (
                            <div className="flex items-start gap-2">
                              <span className="font-medium text-muted-foreground min-w-[80px]">
                                {t(`${i18nNamespace}.mcp.serverDetails.commandArgs`)}:
                              </span>
                              <span className="font-mono text-xs break-all">{server.args.join(' ')}</span>
                            </div>
                          )}
                        </>
                      )}
                      {server.env && Object.keys(server.env).length > 0 && (
                        <div className="flex items-start gap-2">
                          <div className="flex items-center gap-2 min-w-[80px]">
                            <span className="font-medium text-muted-foreground">
                              {t(`${i18nNamespace}.mcp.serverDetails.env`)}:
                            </span>
                            <button
                              type="button"
                              onClick={() => setVisibleEnvs(prev => ({ ...prev, [server.id]: !prev[server.id] }))}
                              className="rounded p-0.5 transition-colors hover:bg-muted"
                              title={visibleEnvs[server.id] ? '隱藏環境變數' : '顯示環境變數'}
                            >
                              {visibleEnvs[server.id] ? (
                                <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                              ) : (
                                <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                              )}
                            </button>
                          </div>
                          <div className="flex-1 space-y-1">
                            {Object.entries(server.env).map(([key, value]) => (
                              <div key={key} className="bg-muted/30 rounded px-2 py-1">
                                <span className="font-mono text-xs break-all">
                                  <span className="text-primary font-semibold">{key}</span>
                                  <span className="text-muted-foreground mx-1">=</span>
                                  <span className="text-foreground">
                                    {visibleEnvs[server.id] ? value : '***'}
                                  </span>
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

              {!runtimeLoading && !loading && filteredServers.length === 0 && isRuntimeReady && !error && (
                <div className="grid h-48 place-content-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
                  {t(`${i18nNamespace}.mcp.list.empty`)}
                </div>
              )}
            </div>
          </div>
        </div>

        <MCPServerDialog
          open={dialogOpen}
          mode={dialogMode}
          server={activeServer}
          availableScopes={availableScopes}
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
          availableScopes={availableScopes}
          i18nNamespace={i18nNamespace}
        />
      </div>
    </TooltipProvider>
  );
};

export default MCPSettingsPage;
