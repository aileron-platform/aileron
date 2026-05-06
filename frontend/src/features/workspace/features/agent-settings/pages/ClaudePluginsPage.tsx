import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Boxes,
  Building,
  ExternalLink,
  FileText,
  FolderGit,
  Layers,
  MoreHorizontal,
  Package,
  Power,
  RefreshCw,
  Search,
  Server,
  Sparkles,
  Tags,
  TerminalSquare,
  User,
  Wrench,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { MarkdownContent } from '@/shared/components/markdown/MarkdownContent';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { SettingsWorkflowCountBadge, SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { AgentSettingsLayerSelector, AgentSettingsSourceFilter } from '../components/SettingsSourcePrimitives';
import {
  DetailSection,
  PluginCard,
  PluginCardGrid,
  PluginDetailDialog,
  PluginDisplayModeToggle,
  PluginEmptyState,
  PluginPagination,
  PluginStatusPill,
  ResourceBadge,
  ResourceSummary,
  type PluginDisplayMode,
} from '../components/plugin-list';
import {
  createAgentSettingsApi,
  type ClaudePluginDetail,
  type ClaudePluginScope,
  type ClaudePluginSummary,
} from '../services/agentSettingsApi';

type ClaudeResourceKey = 'commands' | 'agents' | 'hooks' | 'mcpServers' | 'skills' | 'lspServers';
type ClaudeScopeFilter = 'all' | ClaudePluginScope;

const I18N_PREFIX = 'workspace.agentSettings.claude.plugins';
const COMMON_PREFIX = 'workspace.agentSettings.common.plugins';
const PLUGINS_PER_PAGE = 6;
const scopes: ClaudeScopeFilter[] = ['all', 'project', 'user', 'local'];
const resourceKeys: ClaudeResourceKey[] = ['commands', 'agents', 'hooks', 'mcpServers', 'skills', 'lspServers'];

const scopeIcons: Record<ClaudeScopeFilter, React.ComponentType<{ className?: string }>> = {
  all: Layers,
  project: FolderGit,
  user: User,
  local: Building,
};

const resourceIcons: Record<ClaudeResourceKey, React.ComponentType<{ className?: string }>> = {
  commands: TerminalSquare,
  agents: Package,
  hooks: Wrench,
  mcpServers: Server,
  skills: Sparkles,
  lspServers: Boxes,
};

const ClaudePluginsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const api = useMemo(() => createAgentSettingsApi('claude'), []);
  const [scope, setScope] = useState<ClaudeScopeFilter>('all');
  const [displayMode, setDisplayMode] = useState<PluginDisplayMode>('enabled');
  const [searchQuery, setSearchQuery] = useState('');
  const [marketplaceFilter, setMarketplaceFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const enabled = Boolean(runtimeBaseUrl && workspaceId);

  const pluginsQuery = useQuery({
    queryKey: ['claude-plugins', runtimeBaseUrl, workspaceId],
    queryFn: () => api.listClaudePlugins(runtimeBaseUrl || '', workspaceId || ''),
    enabled,
  });

  const detailQuery = useQuery({
    queryKey: ['claude-plugin-detail', runtimeBaseUrl, workspaceId, selectedId],
    queryFn: () => api.getClaudePlugin(runtimeBaseUrl || '', workspaceId || '', selectedId || ''),
    enabled: enabled && detailOpen && Boolean(selectedId),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ pluginId, nextEnabled }: { pluginId: string; nextEnabled: boolean }) => {
      setError(null);
      if (scope === 'all') {
        throw new Error(t(`${I18N_PREFIX}.errors.selectConcreteScope`));
      }
      return api.setClaudePluginEnabled(runtimeBaseUrl || '', workspaceId || '', pluginId, scope, nextEnabled);
    },
    onSuccess: async (_result, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['claude-plugins', runtimeBaseUrl, workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ['claude-plugin-detail', runtimeBaseUrl, workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ['agent-document-sidebar', runtimeBaseUrl, workspaceId, 'claude'] });
      await queryClient.invalidateQueries({ queryKey: ['agent-file-tree'] });
      toast({
        title: variables.nextEnabled
          ? t(`${I18N_PREFIX}.notifications.enabled.title`)
          : t(`${I18N_PREFIX}.notifications.disabled.title`),
        description: t(`${I18N_PREFIX}.notifications.scope`, { name: variables.pluginId }),
      });
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : t(`${I18N_PREFIX}.errors.updateFailed`);
      setError(message);
      toast({ title: t(`${I18N_PREFIX}.errors.updateFailed`), description: message, variant: 'destructive' });
    },
  });

  const plugins = useMemo(() => pluginsQuery.data?.plugins ?? [], [pluginsQuery.data]);
  const marketplaces = useMemo(
    () => (pluginsQuery.data?.marketplaces ?? []).filter((marketplace) => marketplace.pluginCount > 0),
    [pluginsQuery.data],
  );
  const marketplaceOptions = useMemo(
    () => [
      {
        value: 'all',
        label: t(`${I18N_PREFIX}.filters.allMarketplaces`),
        icon: <Boxes className="h-3 w-3" />,
      },
      ...marketplaces.map((marketplace) => ({
        value: marketplace.name,
        label: marketplace.name,
        icon: <Building className="h-3 w-3" />,
      })),
    ],
    [marketplaces, t],
  );
  const categories = useMemo(
    () => Array.from(new Set(plugins.map((plugin) => plugin.category).filter((value): value is string => Boolean(value)))).sort(),
    [plugins],
  );
  const categoryOptions = useMemo(
    () => [
      {
        value: 'all',
        label: t(`${I18N_PREFIX}.filters.allCategories`),
        icon: <Tags className="h-3 w-3" />,
      },
      ...categories.map((category) => ({
        value: category,
        label: category,
        icon: <Tags className="h-3 w-3" />,
      })),
    ],
    [categories, t],
  );
  const scopeOptions = useMemo(
    () => scopes.map((scopeValue) => {
      const Icon = scopeIcons[scopeValue];
      return {
        value: scopeValue,
        label: t(`${I18N_PREFIX}.scopes.${scopeValue}`),
        icon: <Icon className="h-3 w-3" />,
      };
    }),
    [t],
  );
  const visiblePlugins = useFilteredPlugins(plugins, displayMode, searchQuery, marketplaceFilter, categoryFilter, scope);
  const totalPages = Math.max(1, Math.ceil(visiblePlugins.length / PLUGINS_PER_PAGE));
  const currentPageClamped = Math.min(currentPage, totalPages);
  const paginatedPlugins = useMemo(() => {
    const start = (currentPageClamped - 1) * PLUGINS_PER_PAGE;
    return visiblePlugins.slice(start, start + PLUGINS_PER_PAGE);
  }, [currentPageClamped, visiblePlugins]);
  const detail = detailQuery.data?.plugin;

  useEffect(() => {
    setCurrentPage(1);
  }, [categoryFilter, displayMode, marketplaceFilter, searchQuery, scope]);

  useEffect(() => {
    if (marketplaces.length === 1 && marketplaceFilter === 'all') {
      setMarketplaceFilter(marketplaces[0].name);
      return;
    }
    if (marketplaceFilter !== 'all' && !marketplaces.some((marketplace) => marketplace.name === marketplaceFilter)) {
      setMarketplaceFilter('all');
    }
  }, [marketplaceFilter, marketplaces]);

  useEffect(() => {
    if (categories.length === 1 && categoryFilter === 'all') {
      setCategoryFilter(categories[0]);
      return;
    }
    if (categoryFilter !== 'all' && !categories.includes(categoryFilter)) {
      setCategoryFilter('all');
    }
  }, [categories, categoryFilter]);

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const startItem = visiblePlugins.length > 0 ? (currentPageClamped - 1) * PLUGINS_PER_PAGE + 1 : 0;
  const endItem = visiblePlugins.length > 0 ? Math.min(currentPageClamped * PLUGINS_PER_PAGE, visiblePlugins.length) : 0;

  return (
    <SettingsWorkflowShell
      title={t(`${I18N_PREFIX}.title`)}
      icon={Boxes}
      headerActions={
        <div className="flex flex-wrap items-center gap-2">
          <AgentSettingsLayerSelector
            value={scope}
            onChange={setScope}
            options={scopeOptions}
            label={t(`${I18N_PREFIX}.scopes.label`)}
            className="rounded-lg bg-muted/60 px-3 py-1"
          />
          <PluginDisplayModeToggle
            value={displayMode}
            labels={{
              enabled: t(`${COMMON_PREFIX}.displayModes.enabled`),
              all: t(`${COMMON_PREFIX}.displayModes.all`),
            }}
            onChange={setDisplayMode}
          />
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => void pluginsQuery.refetch()}
            disabled={!enabled || pluginsQuery.isFetching}
          >
            <RefreshCw className={cn('mr-1 h-3 w-3', pluginsQuery.isFetching && 'animate-spin')} />
            {t(`${COMMON_PREFIX}.actions.refresh`)}
          </Button>
        </div>
      }
      summary={
        <SettingsWorkflowCountBadge
          label={t(`${COMMON_PREFIX}.search.resultCount`, { count: visiblePlugins.length })}
        />
      }
      controls={
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative w-full max-w-md">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transform text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={t(`${COMMON_PREFIX}.search.placeholder`)}
              aria-label={t(`${COMMON_PREFIX}.search.label`)}
              className="h-7 pl-9 text-xs"
            />
          </div>
          <AgentSettingsSourceFilter
            value={marketplaceFilter}
            onChange={setMarketplaceFilter}
            options={marketplaceOptions}
            label={t(`${I18N_PREFIX}.filters.marketplaceLabel`)}
            disabled={marketplaces.length <= 1}
            width={220}
          />
          <AgentSettingsSourceFilter
            value={categoryFilter}
            onChange={setCategoryFilter}
            options={categoryOptions}
            label={t(`${I18N_PREFIX}.filters.categoryLabel`)}
            disabled={categories.length <= 1}
            width={180}
          />
        </div>
      }
      error={error ? <AlertMessage message={error} /> : null}
      isLoading={pluginsQuery.isLoading || workspaceRuntime.isLoading}
      loadingLabel={t(`${I18N_PREFIX}.loading`)}
      hasItems={plugins.length > 0}
      emptyIcon={<Boxes className="h-8 w-8 text-muted-foreground" />}
      emptyTitle={t(`${I18N_PREFIX}.empty.title`)}
      emptyDescription={t(`${I18N_PREFIX}.empty.description`)}
      contentClassName="p-6"
    >
      {visiblePlugins.length === 0 ? (
        <PluginEmptyState
          icon={<Boxes className="h-8 w-8" />}
          title={searchQuery.trim() ? t(`${COMMON_PREFIX}.empty.searchTitle`) : t(`${I18N_PREFIX}.empty.enabledTitle`)}
          description={searchQuery.trim() ? t(`${COMMON_PREFIX}.empty.searchDescription`) : t(`${I18N_PREFIX}.empty.enabledDescription`)}
          actions={
            displayMode === 'enabled' && !searchQuery.trim() ? (
              <Button variant="outline" size="sm" onClick={() => setDisplayMode('all')}>
                {t(`${COMMON_PREFIX}.actions.showAll`)}
              </Button>
            ) : null
          }
        />
      ) : (
        <>
          <PluginCardGrid>
            {paginatedPlugins.map((plugin) => (
              <ClaudePluginCard
                key={plugin.id}
                plugin={plugin}
                pending={toggleMutation.isPending}
                scope={scope}
                onDetails={() => {
                  setSelectedId(plugin.id);
                  setDetailOpen(true);
                }}
                onToggle={() => toggleMutation.mutate({ pluginId: plugin.id, nextEnabled: getNextScopeEnabled(plugin, scope) })}
              />
            ))}
          </PluginCardGrid>
          <PluginPagination
            page={currentPageClamped}
            totalPages={totalPages}
            totalItems={visiblePlugins.length}
            pageSize={PLUGINS_PER_PAGE}
            previousLabel={t(`${COMMON_PREFIX}.pagination.previous`)}
            nextLabel={t(`${COMMON_PREFIX}.pagination.next`)}
            pageLabel={t(`${COMMON_PREFIX}.pagination.page`, { current: currentPageClamped, total: totalPages })}
            summaryLabel={t(`${COMMON_PREFIX}.pagination.summary`, { start: startItem, end: endItem, total: visiblePlugins.length })}
            onPageChange={setCurrentPage}
          />
        </>
      )}

      <PluginDetailDialog
        open={detailOpen}
        onOpenChange={setDetailOpen}
        title={detail ? t(`${I18N_PREFIX}.detail.title`, { name: detail.name }) : t(`${I18N_PREFIX}.detail.fallbackTitle`)}
        description={detail?.description ?? undefined}
        icon={<Package className="h-5 w-5" />}
      >
        <ClaudePluginDetailPanel detail={detail} loading={detailQuery.isLoading} />
      </PluginDetailDialog>
    </SettingsWorkflowShell>
  );
};

const AlertMessage: React.FC<{ message: string }> = ({ message }) => (
  <Alert variant="destructive" className="border-0 bg-transparent p-0">
    <AlertDescription>{message}</AlertDescription>
  </Alert>
);

const useFilteredPlugins = (
  plugins: ClaudePluginSummary[],
  displayMode: PluginDisplayMode,
  searchQuery: string,
  marketplaceFilter: string,
  categoryFilter: string,
  scope: ClaudeScopeFilter,
): ClaudePluginSummary[] => useMemo(() => {
  const normalizedQuery = searchQuery.trim().toLowerCase();
  return plugins
    .filter((plugin) => displayMode === 'all' || plugin.enabled)
    .filter((plugin) => marketplaceFilter === 'all' || plugin.marketplace === marketplaceFilter)
    .filter((plugin) => categoryFilter === 'all' || plugin.category === categoryFilter)
    .filter((plugin) => scope === 'all' || plugin.installations.some((installation) => installation.scope === scope))
    .filter((plugin) => {
      if (!normalizedQuery) {
        return true;
      }
      return [
        plugin.id,
        plugin.name,
        plugin.description,
        plugin.version,
        plugin.author,
        plugin.category,
        plugin.marketplace,
      ]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedQuery));
    });
}, [categoryFilter, displayMode, marketplaceFilter, plugins, scope, searchQuery]);

const getScopeInstallation = (plugin: ClaudePluginSummary, scope: ClaudePluginScope) => (
  plugin.installations.find((installation) => installation.scope === scope)
);

const getNextScopeEnabled = (plugin: ClaudePluginSummary, scope: ClaudeScopeFilter): boolean => {
  if (scope === 'all') {
    return !plugin.enabled;
  }
  return getScopeInstallation(plugin, scope)?.enabled !== true;
};

const ClaudePluginCard: React.FC<{
  plugin: ClaudePluginSummary;
  pending: boolean;
  scope: ClaudeScopeFilter;
  onDetails: () => void;
  onToggle: () => void;
}> = ({ plugin, pending, scope, onDetails, onToggle }) => {
  const { t } = useI18n();
  const description = plugin.description?.trim() || t(`${I18N_PREFIX}.descriptionFallback`);
  const toggleDisabled = pending || scope === 'all';
  const selectedScopeEnabled = scope !== 'all' && getScopeInstallation(plugin, scope)?.enabled === true;

  return (
    <PluginCard
      title={plugin.name}
      subtitle={plugin.marketplace ?? plugin.version ?? plugin.id}
      description={description}
      onTitleClick={onDetails}
      warningBadge={plugin.errors.length ? (
        <Badge variant="destructive" className="gap-1">
          <AlertTriangle className="h-3.5 w-3.5" />
          {plugin.errors.length}
        </Badge>
      ) : null}
      statusBadge={
        <PluginStatusPill
          enabled={plugin.enabled}
          enabledLabel={t(`${COMMON_PREFIX}.status.enabled`)}
          disabledLabel={t(`${COMMON_PREFIX}.status.disabled`)}
        />
      }
      actions={
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 w-8 px-0">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">{t(`${COMMON_PREFIX}.actions.more`)}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onDetails}>
              <FileText className="mr-2 h-4 w-4" />
              {t(`${COMMON_PREFIX}.actions.details`)}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={toggleDisabled} onClick={onToggle}>
              <Power className="mr-2 h-4 w-4" />
              {scope === 'all'
                ? t(`${I18N_PREFIX}.actions.selectScopeToToggle`)
                : selectedScopeEnabled
                  ? t(`${COMMON_PREFIX}.actions.disable`)
                  : t(`${COMMON_PREFIX}.actions.enable`)}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      }
    >
      <div className="flex flex-wrap gap-2">
        {plugin.installations.map((installation) => (
          <Badge key={`${installation.scope}:${installation.installPath}`} variant="outline">
            {t(`${I18N_PREFIX}.scopes.${installation.scope}`)}
          </Badge>
        ))}
        {plugin.category ? <Badge variant="outline">{plugin.category}</Badge> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {resourceKeys.map((key) => (
          <ResourceBadge
            key={key}
            icon={resourceIcons[key]}
            label={t(`${I18N_PREFIX}.counts.${key}`, { count: plugin.resourceCounts?.[key] ?? 0 })}
          />
        ))}
      </div>
    </PluginCard>
  );
};

const ClaudePluginDetailPanel: React.FC<{ detail?: ClaudePluginDetail; loading: boolean }> = ({
  detail,
  loading,
}) => {
  const { t } = useI18n();

  if (loading) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${COMMON_PREFIX}.detail.loading`)}</div>;
  }
  if (!detail) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${COMMON_PREFIX}.detail.empty`)}</div>;
  }

  return (
    <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-border px-6 pt-4">
        <TabsList className="h-9 w-full justify-start overflow-x-auto rounded-none bg-transparent p-0">
          <TabsTrigger value="overview" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.overview`)}
          </TabsTrigger>
          <TabsTrigger value="readme" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.readme`)}
          </TabsTrigger>
          <TabsTrigger value="resources" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.resources`)}
          </TabsTrigger>
          <TabsTrigger value="diagnostics" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.diagnostics`)}
          </TabsTrigger>
          <TabsTrigger value="registry" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.registry`)}
          </TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="overview" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <ClaudePluginOverview detail={detail} />
      </TabsContent>
      <TabsContent value="readme" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        {detail.readme ? (
          <MarkdownContent content={detail.readme} variant="detailed" className="rounded-lg border border-border bg-background px-4 py-3" />
        ) : (
          <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noReadme`)}</span>
        )}
      </TabsContent>
      <TabsContent value="resources" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <ClaudePluginResources detail={detail} />
      </TabsContent>
      <TabsContent value="diagnostics" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <ClaudePluginDiagnostics detail={detail} />
      </TabsContent>
      <TabsContent value="registry" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <RegistryMetadataPanel detail={detail} />
      </TabsContent>
    </Tabs>
  );
};

const ClaudePluginOverview: React.FC<{ detail: ClaudePluginDetail }> = ({ detail }) => {
  const { t } = useI18n();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <Badge variant={detail.enabled ? 'default' : 'secondary'}>
          {detail.enabled ? t(`${COMMON_PREFIX}.status.enabled`) : t(`${COMMON_PREFIX}.status.disabled`)}
        </Badge>
        {detail.version ? <Badge variant="outline">{detail.version}</Badge> : null}
        {detail.license ? <Badge variant="outline">{detail.license}</Badge> : null}
        {detail.marketplace ? <Badge variant="outline">{detail.marketplace}</Badge> : null}
      </div>
      <DetailSection title={t(`${COMMON_PREFIX}.detail.description`)}>
        <p className="whitespace-pre-wrap text-sm text-muted-foreground">
          {detail.description || t(`${I18N_PREFIX}.descriptionFallback`)}
        </p>
      </DetailSection>
      <DetailSection title={t(`${I18N_PREFIX}.detail.installations`)}>
        <div className="overflow-hidden rounded border border-border">
          {detail.installations.map((installation) => (
            <div
              key={`${installation.scope}:${installation.installPath}`}
              className="grid gap-2 border-b border-border p-3 text-sm last:border-b-0 sm:grid-cols-[120px_1fr_100px]"
            >
              <span className="font-medium">{t(`${I18N_PREFIX}.scopes.${installation.scope}`)}</span>
              <span className="min-w-0 truncate text-muted-foreground">{installation.installPath}</span>
              <Badge variant={installation.enabled ? 'default' : 'secondary'} className="justify-self-start">
                {installation.enabled ? t(`${COMMON_PREFIX}.status.enabled`) : t(`${COMMON_PREFIX}.status.disabled`)}
              </Badge>
            </div>
          ))}
        </div>
      </DetailSection>
      <DetailSection title={t(`${I18N_PREFIX}.detail.dependencies`)}>
        <div className="flex flex-wrap gap-2">
          {detail.dependencies.length
            ? detail.dependencies.map((dependency) => (
              <Badge key={`${dependency.marketplace ?? ''}:${dependency.name}:${dependency.version ?? ''}`} variant="outline">
                {dependency.version ? `${dependency.name}@${dependency.version}` : dependency.name}
              </Badge>
            ))
            : <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noDependencies`)}</span>}
        </div>
      </DetailSection>
    </div>
  );
};

const ClaudePluginResources: React.FC<{ detail: ClaudePluginDetail }> = ({ detail }) => {
  const { t } = useI18n();

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {resourceKeys.map((key) => (
        <ResourceSummary
          key={key}
          label={t(`${I18N_PREFIX}.detail.${key}`)}
          count={detail.resourceCounts?.[key] ?? 0}
        />
      ))}
    </div>
  );
};

const ClaudePluginDiagnostics: React.FC<{ detail: ClaudePluginDetail }> = ({ detail }) => {
  const { t } = useI18n();

  return (
    <div className="space-y-2">
      {detail.errors.length
        ? detail.errors.map((error) => (
          <pre key={error} className="overflow-auto whitespace-pre-wrap rounded bg-destructive/10 p-3 text-xs text-destructive">
            {error}
          </pre>
        ))
        : <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noErrors`)}</span>}
    </div>
  );
};

const RegistryMetadataPanel: React.FC<{ detail: ClaudePluginDetail }> = ({ detail }) => {
  const { t } = useI18n();
  const manifest = detail.manifest ?? {};
  const metadataItems = [
    { key: 'id', label: t(`${I18N_PREFIX}.detail.metadata.id`), value: detail.id },
    { key: 'name', label: t(`${I18N_PREFIX}.detail.metadata.name`), value: getStringValue(manifest.name) || detail.name },
    { key: 'version', label: t(`${I18N_PREFIX}.detail.metadata.version`), value: getStringValue(manifest.version) || detail.version },
    { key: 'author', label: t(`${I18N_PREFIX}.detail.metadata.author`), value: getAuthorValue(manifest.author) || detail.author },
    { key: 'category', label: t(`${I18N_PREFIX}.detail.metadata.category`), value: getStringValue(manifest.category) || detail.category },
    { key: 'marketplace', label: t(`${I18N_PREFIX}.detail.metadata.marketplace`), value: detail.marketplace },
    { key: 'homepage', label: t(`${I18N_PREFIX}.detail.metadata.homepage`), value: getStringValue(manifest.homepage) || detail.homepage },
    { key: 'repository', label: t(`${I18N_PREFIX}.detail.metadata.repository`), value: getStringValue(manifest.repository) || detail.repository },
    { key: 'license', label: t(`${I18N_PREFIX}.detail.metadata.license`), value: getStringValue(manifest.license) || detail.license },
  ].filter((item): item is { key: string; label: string; value: string } => Boolean(item.value));
  const sourceItems = getSourceItems(manifest.source, t);

  return (
    <div className="space-y-3">
      {metadataItems.length ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {metadataItems.map((item) => (
            <MetadataItem key={item.key} label={item.label} value={item.value} />
          ))}
        </div>
      ) : (
        <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.metadata.empty`)}</span>
      )}
      {sourceItems.length ? (
        <div className="rounded-lg border border-border">
          <div className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
            {t(`${I18N_PREFIX}.detail.metadata.source`)}
          </div>
          <div className="grid gap-2 p-3 sm:grid-cols-2">
            {sourceItems.map((item) => (
              <MetadataItem key={item.key} label={item.label} value={item.value} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
};

const MetadataItem: React.FC<{ label: string; value: string }> = ({ label, value }) => {
  const isLink = /^https?:\/\//i.test(value);
  return (
    <div className="min-w-0 rounded-lg border border-border bg-muted/30 px-3 py-2">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      {isLink ? (
        <a
          href={value}
          target="_blank"
          rel="noreferrer"
          className="mt-1 flex min-w-0 items-center gap-1 text-sm text-primary hover:underline"
        >
          <span className="truncate">{value}</span>
          <ExternalLink className="h-3 w-3 shrink-0" />
        </a>
      ) : (
        <div className="mt-1 truncate text-sm">{value}</div>
      )}
    </div>
  );
};

const getStringValue = (value: unknown): string | undefined => (
  typeof value === 'string' && value.trim() ? value.trim() : undefined
);

const getAuthorValue = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return getStringValue(value);
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return getStringValue(record.name) || getStringValue(record.email);
  }
  return undefined;
};

const getSourceItems = (
  value: unknown,
  t: ReturnType<typeof useI18n>['t'],
): Array<{ key: string; label: string; value: string }> => {
  if (typeof value === 'string' && value.trim()) {
    return [{ key: 'source', label: t(`${I18N_PREFIX}.detail.metadata.sourcePath`), value: value.trim() }];
  }
  if (!value || typeof value !== 'object') {
    return [];
  }
  const source = value as Record<string, unknown>;
  return [
    { key: 'type', label: t(`${I18N_PREFIX}.detail.metadata.sourceType`), value: getStringValue(source.source) },
    { key: 'repo', label: t(`${I18N_PREFIX}.detail.metadata.sourceRepo`), value: getStringValue(source.repo) },
    { key: 'url', label: t(`${I18N_PREFIX}.detail.metadata.sourceUrl`), value: getStringValue(source.url) },
    { key: 'path', label: t(`${I18N_PREFIX}.detail.metadata.sourcePath`), value: getStringValue(source.path) },
    { key: 'branch', label: t(`${I18N_PREFIX}.detail.metadata.sourceBranch`), value: getStringValue(source.branch) },
    { key: 'ref', label: t(`${I18N_PREFIX}.detail.metadata.sourceRef`), value: getStringValue(source.ref) },
  ].filter((item): item is { key: string; label: string; value: string } => Boolean(item.value));
};

export default ClaudePluginsPage;
