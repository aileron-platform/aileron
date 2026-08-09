import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  Boxes,
  Building,
  FileText,
  Layers,
  MoreHorizontal,
  Package,
  Power,
  RefreshCw,
  Search,
  Server,
  Sparkles,
  Tags,
  Wrench,
  type LucideIcon,
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
import { getDocumentSourceIcon } from '@/shared/components/document-resource';
import {
  AgentSettingsLayerSelector,
  AgentSettingsSourceFilter,
  NewThreadNotice,
} from '../../components/AgentSettingsSourceControls';
import { PluginCard } from '../../components/plugin-list/PluginCard';
import { PluginCardGrid } from '../../components/plugin-list/PluginCardGrid';
import { PluginDetailDialog } from '../../components/plugin-list/PluginDetailDialog';
import {
  PluginDisplayModeToggle,
  type PluginDisplayMode,
} from '../../components/plugin-list/PluginDisplayModeToggle';
import { PluginEmptyState } from '../../components/plugin-list/PluginEmptyState';
import { PluginPagination } from '../../components/plugin-list/PluginPagination';
import { PluginStatusPill } from '../../components/plugin-list/PluginStatusPill';
import { ResourceBadge } from '../../components/plugin-list/ResourceBadge';
import { ResourceSummary } from '../../components/plugin-list/ResourceSummary';
import { useAgentSettingsAuthorization } from '../../AgentSettingsAuthorizationContext';
import { createAgentSettingsApi, type CodexPluginDetail, type CodexPluginSummary } from '../../api/agentSettingsApi';
import {
  filterCodexPlugins,
  getCodexLayerState,
  getCodexPluginPagination,
  getNextCodexLayerEnabled,
  isCodexLayerOverridden,
  type CodexLayer,
  type CodexLayerFilter,
} from './codexPluginsPageModel';
import {
  buildPluginResourceSettingsHref,
  buildProviderPluginDetailQueryKey,
  invalidateProviderResourceQueries,
  type PluginSettingsResourceKind,
} from '../../model/pluginResources';
import { useProviderPluginListQuery } from '../plugin-resources/useProviderPluginListQuery';

type CodexResourceKey = 'skills' | 'mcpServers' | 'apps' | 'hooks';

const I18N_PREFIX = 'workspace.agentSettings.codex.plugins';
const COMMON_PREFIX = 'workspace.agentSettings.common.plugins';
const PLUGINS_PER_PAGE = 6;
const resourceKeys: CodexResourceKey[] = ['skills', 'mcpServers', 'apps', 'hooks'];
const resourceSettings: Partial<Record<CodexResourceKey, PluginSettingsResourceKind>> = {
  skills: 'skills',
  mcpServers: 'mcp',
  hooks: 'hooks',
};

const resourceIcons: Record<CodexResourceKey, LucideIcon> = {
  skills: Sparkles,
  mcpServers: Server,
  apps: Package,
  hooks: Wrench,
};

const CodexPluginsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { workspaceRuntime } = useWorkspace();
  const { readOnly } = useAgentSettingsAuthorization();
  const [searchParams, setSearchParams] = useSearchParams();
  const api = useMemo(() => createAgentSettingsApi('codex'), []);
  const [layer, setLayer] = useState<CodexLayerFilter>('all');
  const [displayMode, setDisplayMode] = useState<PluginDisplayMode>('enabled');
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [marketplaceFilter, setMarketplaceFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [showNewThreadNotice, setShowNewThreadNotice] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const enabled = Boolean(runtimeBaseUrl && workspaceId);

  const pluginsQuery = useProviderPluginListQuery({
    provider: 'codex',
    runtimeBaseUrl: runtimeBaseUrl || '',
    workspaceId: workspaceId || '',
    enabled,
  });
  const providerResourceGeneration =
    pluginsQuery.data?.providerResourceGeneration ?? 0;

  const detailQuery = useQuery({
    queryKey: buildProviderPluginDetailQueryKey({
      provider: 'codex',
      runtimeBaseUrl: runtimeBaseUrl || '',
      workspaceId: workspaceId || '',
      providerResourceGeneration,
      pluginId: selectedId,
    }),
    queryFn: () => api.getCodexPlugin(runtimeBaseUrl || '', workspaceId || '', selectedId || ''),
    enabled: enabled && detailOpen && Boolean(selectedId),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ pluginId, nextEnabled }: { pluginId: string; nextEnabled: boolean }) => {
      setError(null);
      if (readOnly) {
        throw new Error(t('common.authorization.readOnlyDescription'));
      }
      if (layer === 'all') {
        throw new Error(t(`${I18N_PREFIX}.errors.selectConcreteScope`));
      }
      return api.setCodexPluginEnabled(runtimeBaseUrl || '', workspaceId || '', pluginId, layer, nextEnabled);
    },
    onSuccess: async (_result, variables) => {
      setShowNewThreadNotice(true);
      await invalidateProviderResourceQueries(
        queryClient,
        'codex',
        workspaceId || '',
      );
      await queryClient.invalidateQueries({ queryKey: ['codex-hooks-workflow', runtimeBaseUrl, workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ['codex-skills-scope-availability', runtimeBaseUrl, workspaceId] });
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
  const layerOptions = useMemo(
    () => [
      {
        value: 'all',
        label: t(`${I18N_PREFIX}.layers.all`),
        icon: <Layers className="h-3 w-3" />,
      },
      ...(['project', 'user'] as CodexLayer[]).map((scopeValue) => {
        const Icon = getDocumentSourceIcon(scopeValue);
        return {
          value: scopeValue,
          label: t(`${I18N_PREFIX}.layers.${scopeValue}`),
          icon: <Icon className="h-3 w-3" />,
        };
      }),
    ],
    [t],
  );
  const marketplaces = useMemo(
    () => Array.from(new Set(plugins.map((plugin) => plugin.marketplace).filter((value): value is string => Boolean(value)))).sort(),
    [plugins],
  );
  const marketplaceOptions = useMemo(
    () => [
      {
        value: 'all',
        label: t(`${I18N_PREFIX}.filters.allMarketplaces`),
        icon: <Boxes className="h-3 w-3" />,
      },
      ...marketplaces.map((marketplace) => ({
        value: marketplace,
        label: marketplace,
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
  const visiblePlugins = useMemo(() => filterCodexPlugins(plugins, {
    displayMode,
    searchQuery,
    marketplaceFilter,
    categoryFilter,
    layer,
  }), [categoryFilter, displayMode, layer, marketplaceFilter, plugins, searchQuery]);
  const pagination = getCodexPluginPagination(visiblePlugins.length, currentPage, PLUGINS_PER_PAGE);
  const paginatedPlugins = useMemo(() => {
    const start = (pagination.currentPage - 1) * PLUGINS_PER_PAGE;
    return visiblePlugins.slice(start, start + PLUGINS_PER_PAGE);
  }, [pagination.currentPage, visiblePlugins]);
  const detail = detailQuery.data?.plugin;
  const deepLinkedPluginId = searchParams.get('pluginId')?.trim() || null;
  const deepLinkedResource = searchParams.get('resource')?.trim() || null;
  const openDeepLinkedResource = Object.values(resourceSettings)
    .some(resource => resource === deepLinkedResource);

  useEffect(() => {
    setCurrentPage(1);
  }, [categoryFilter, displayMode, layer, marketplaceFilter, searchQuery]);

  useEffect(() => {
    if (!deepLinkedPluginId) {
      return;
    }
    setSelectedId(deepLinkedPluginId);
    setDetailOpen(true);
  }, [deepLinkedPluginId]);

  useEffect(() => {
    if (marketplaces.length === 1 && marketplaceFilter === 'all') {
      setMarketplaceFilter(marketplaces[0]);
      return;
    }
    if (marketplaceFilter !== 'all' && !marketplaces.includes(marketplaceFilter)) {
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
    setCurrentPage((page) => Math.min(page, pagination.totalPages));
  }, [pagination.totalPages]);

  return (
    <SettingsWorkflowShell
      title={t(`${I18N_PREFIX}.title`)}
      icon={Boxes}
      headerActions={
        <div className="flex flex-wrap items-center gap-2">
          <AgentSettingsLayerSelector
            value={layer}
            onChange={value => setLayer(value as CodexLayerFilter)}
            options={layerOptions}
            label={t(`${I18N_PREFIX}.layers.label`)}
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
            width={200}
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
      {showNewThreadNotice ? <div className="mb-4"><NewThreadNotice /></div> : null}
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
              <CodexPluginCard
                key={plugin.id}
                plugin={plugin}
                pending={toggleMutation.isPending}
                readOnly={readOnly}
                layer={layer}
                onDetails={() => {
                  setSelectedId(plugin.id);
                  setDetailOpen(true);
                }}
                onToggle={() => toggleMutation.mutate({ pluginId: plugin.id, nextEnabled: getNextCodexLayerEnabled(plugin, layer) })}
              />
            ))}
          </PluginCardGrid>
          <PluginPagination
            page={pagination.currentPage}
            totalPages={pagination.totalPages}
            totalItems={visiblePlugins.length}
            pageSize={PLUGINS_PER_PAGE}
            previousLabel={t(`${COMMON_PREFIX}.pagination.previous`)}
            nextLabel={t(`${COMMON_PREFIX}.pagination.next`)}
            pageLabel={t(`${COMMON_PREFIX}.pagination.page`, { current: pagination.currentPage, total: pagination.totalPages })}
            summaryLabel={t(`${COMMON_PREFIX}.pagination.summary`, { start: pagination.startItem, end: pagination.endItem, total: visiblePlugins.length })}
            onPageChange={setCurrentPage}
          />
        </>
      )}

      <PluginDetailDialog
        open={detailOpen}
        onOpenChange={(nextOpen) => {
          setDetailOpen(nextOpen);
          if (!nextOpen && deepLinkedPluginId) {
            const next = new URLSearchParams(searchParams);
            next.delete('pluginId');
            next.delete('resource');
            setSearchParams(next, { replace: true });
          }
        }}
        title={detail ? t(`${I18N_PREFIX}.detail.title`, { name: detail.displayName || detail.name }) : t(`${I18N_PREFIX}.detail.fallbackTitle`)}
        description={detail?.shortDescription ?? undefined}
        icon={Package}
      >
        <CodexPluginDetailPanel
          detail={detail}
          loading={detailQuery.isLoading}
          workspaceId={workspaceId || ''}
          openResources={openDeepLinkedResource}
        />
      </PluginDetailDialog>
    </SettingsWorkflowShell>
  );
};

const AlertMessage: React.FC<{ message: string }> = ({ message }) => (
  <Alert variant="destructive" className="border-0 bg-transparent p-0">
    <AlertDescription>{message}</AlertDescription>
  </Alert>
);

const CodexPluginCard: React.FC<{
  plugin: CodexPluginSummary;
  pending: boolean;
  readOnly: boolean;
  layer: CodexLayerFilter;
  onDetails: () => void;
  onToggle: () => void;
}> = ({ plugin, pending, readOnly, layer, onDetails, onToggle }) => {
  const { t } = useI18n();
  const description = plugin.shortDescription?.trim() || t(`${I18N_PREFIX}.descriptionFallback`);
  const toggleDisabled = pending || !plugin.installed || layer === 'all';
  const selectedLayerState = layer === 'all' ? undefined : getCodexLayerState(plugin, layer);
  const selectedLayerEnabled = selectedLayerState?.enabled === true;
  const overridden = isCodexLayerOverridden(plugin, layer);

  return (
    <PluginCard
      title={plugin.displayName || plugin.name}
      subtitle={plugin.marketplace ?? plugin.version ?? plugin.id}
      description={description}
      onTitleClick={onDetails}
      statusBadge={
        <PluginStatusPill
          enabled={plugin.effectiveEnabled}
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
            {!readOnly ? <DropdownMenuSeparator /> : null}
            {!readOnly ? (
            <DropdownMenuItem disabled={toggleDisabled} onClick={onToggle}>
              <Power className="mr-2 h-4 w-4" />
              {layer === 'all'
                ? t(`${I18N_PREFIX}.actions.selectScopeToToggle`)
                : selectedLayerEnabled
                  ? t(`${COMMON_PREFIX}.actions.disable`)
                  : t(`${COMMON_PREFIX}.actions.enable`)}
            </DropdownMenuItem>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      }
    >
      <div className="flex flex-wrap gap-2">
        {plugin.installed ? <Badge variant="secondary">{t(`${I18N_PREFIX}.status.installed`)}</Badge> : null}
        {plugin.listed ? <Badge variant="outline">{t(`${I18N_PREFIX}.status.listed`)}</Badge> : null}
        {selectedLayerState?.configured ? (
          <Badge variant="outline">
            {t(`${I18N_PREFIX}.layers.configured`, { layer: t(`${I18N_PREFIX}.layers.${selectedLayerState.scope}`) })}
          </Badge>
        ) : null}
        {plugin.category ? <Badge variant="outline">{plugin.category}</Badge> : null}
      </div>
      {overridden ? (
        <Alert className="border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
          <AlertDescription>{t(`${I18N_PREFIX}.layers.projectOverride`)}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {resourceKeys
          .filter((key) => (plugin.resourceCounts?.[key] ?? 0) > 0)
          .map((key) => (
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

const CodexPluginDetailPanel: React.FC<{
  detail?: CodexPluginDetail;
  loading: boolean;
  workspaceId: string;
  openResources: boolean;
}> = ({
  detail,
  loading,
  workspaceId,
  openResources,
}) => {
  const { t } = useI18n();

  if (loading) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${COMMON_PREFIX}.detail.loading`)}</div>;
  }
  if (!detail) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${COMMON_PREFIX}.detail.empty`)}</div>;
  }

  return (
    <Tabs
      key={`${detail.id}:${openResources ? 'resources' : 'overview'}`}
      defaultValue={openResources ? 'resources' : 'overview'}
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
    >
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
        </TabsList>
      </div>
      <TabsContent value="overview" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <CodexPluginOverview detail={detail} />
      </TabsContent>
      <TabsContent value="readme" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        {detail.readme ? (
          <MarkdownContent content={detail.readme} variant="detailed" className="rounded-lg border border-border bg-background px-4 py-3" />
        ) : (
          <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noReadme`)}</span>
        )}
      </TabsContent>
      <TabsContent value="resources" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <CodexPluginResources detail={detail} workspaceId={workspaceId} />
      </TabsContent>
    </Tabs>
  );
};

const CodexPluginOverview: React.FC<{ detail: CodexPluginDetail }> = ({ detail }) => {
  const { t } = useI18n();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <Badge variant={detail.effectiveEnabled ? 'default' : 'secondary'}>
          {detail.effectiveEnabled ? t(`${COMMON_PREFIX}.status.enabled`) : t(`${COMMON_PREFIX}.status.disabled`)}
        </Badge>
        {detail.version ? <Badge variant="outline">{detail.version}</Badge> : null}
        {detail.license ? <Badge variant="outline">{detail.license}</Badge> : null}
        {detail.marketplace ? <Badge variant="outline">{detail.marketplace}</Badge> : null}
      </div>
      <p className="whitespace-pre-wrap text-sm text-muted-foreground">
        {detail.longDescription || detail.shortDescription || t(`${I18N_PREFIX}.descriptionFallback`)}
      </p>
      {detail.defaultPrompts.length > 0 ? (
        <section className="space-y-2 rounded-lg border border-border bg-muted/30 p-3">
          <h4 className="text-xs font-medium text-muted-foreground">
            {t(`${I18N_PREFIX}.detail.starterPrompts`)}
          </h4>
          <div className="space-y-2">
            {detail.defaultPrompts.map((prompt, index) => (
              <p
                key={`${index}:${prompt}`}
                className="whitespace-pre-wrap rounded border border-border bg-background px-3 py-2 text-sm"
              >
                {prompt}
              </p>
            ))}
          </div>
        </section>
      ) : null}
      <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-3">
        <div className="text-xs font-medium text-muted-foreground">{t(`${I18N_PREFIX}.layers.stateTitle`)}</div>
        <div className="flex flex-wrap gap-2">
          {detail.scopes.map((scopeState) => (
            <Badge key={scopeState.scope} variant={scopeState.enabled ? 'default' : 'outline'}>
              {t(`${I18N_PREFIX}.layers.state`, {
                layer: t(`${I18N_PREFIX}.layers.${scopeState.scope}`),
                state: scopeState.configured
                  ? scopeState.enabled
                    ? t(`${COMMON_PREFIX}.status.enabled`)
                    : t(`${COMMON_PREFIX}.status.disabled`)
                  : t(`${I18N_PREFIX}.layers.unconfigured`),
              })}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
};

const CodexPluginResources: React.FC<{
  detail: CodexPluginDetail;
  workspaceId: string;
}> = ({ detail, workspaceId }) => {
  const { t } = useI18n();
  const summaries: Array<{ key: string; label: string; count: number }> = [
    { key: 'skills', label: t(`${I18N_PREFIX}.detail.skills`), count: detail.skills.length },
    { key: 'mcpServers', label: t(`${I18N_PREFIX}.detail.mcpServers`), count: detail.mcpServers.length },
    { key: 'apps', label: t(`${I18N_PREFIX}.detail.apps`), count: detail.apps.length },
    { key: 'hooks', label: t(`${I18N_PREFIX}.detail.hooks`), count: detail.hooks.length },
  ].filter((item) => item.count > 0);

  if (summaries.length === 0) {
    return <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noResources`)}</span>;
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {summaries.map((item) => {
        const resource = resourceSettings[item.key as CodexResourceKey];
        return (
          <ResourceSummary
            key={item.key}
            label={item.label}
            count={item.count}
            href={resource
              ? buildPluginResourceSettingsHref({
                workspaceId,
                provider: 'codex',
                resource,
                pluginId: detail.id,
              })
              : undefined}
            linkLabel={resource
              ? t(`${I18N_PREFIX}.detail.openResource`, {
                resource: item.label,
              })
              : undefined}
          />
        );
      })}
    </div>
  );
};

export default CodexPluginsPage;
