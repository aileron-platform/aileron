import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Building,
  Boxes,
  FileText,
  MoreHorizontal,
  Power,
  RefreshCw,
  Search,
  SquareSlash,
  Sparkles,
  TerminalSquare,
  Wrench,
  X,
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
import { AgentSettingsLayerSelector } from '../components/SettingsSourcePrimitives';
import {
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
import { createAgentSettingsApi, type GeminiExtensionDetail, type GeminiExtensionSummary } from '../services/agentSettingsApi';

const I18N_PREFIX = 'workspace.agentSettings.geminiExtensions';
const EXTENSIONS_PER_PAGE = 6;

type CardResourceCountKey = 'mcp' | 'commands' | 'skills' | 'hooks';

const cardResourceKeys: CardResourceCountKey[] = ['mcp', 'commands', 'skills', 'hooks'];

const resourceIcons: Record<CardResourceCountKey, React.ComponentType<{ className?: string }>> = {
  mcp: TerminalSquare,
  commands: SquareSlash,
  skills: Sparkles,
  hooks: Wrench,
};

const GeminiExtensionsPage: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime } = useWorkspace();
  const queryClient = useQueryClient();
  const [displayMode, setDisplayMode] = useState<PluginDisplayMode>('enabled');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const api = useMemo(() => createAgentSettingsApi('gemini'), []);
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const enabled = Boolean(runtimeBaseUrl && workspaceId);

  const listQuery = useQuery({
    queryKey: ['gemini-extensions', runtimeBaseUrl, workspaceId],
    queryFn: () => api.listGeminiExtensions(runtimeBaseUrl || '', workspaceId || ''),
    enabled,
  });

  const detailQuery = useQuery({
    queryKey: ['gemini-extension-detail', runtimeBaseUrl, workspaceId, selectedName],
    queryFn: () => api.getGeminiExtension(runtimeBaseUrl || '', workspaceId || '', selectedName || ''),
    enabled: enabled && detailOpen && Boolean(selectedName),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ name, enabledHere }: { name: string; enabledHere: boolean }) => {
      setError(null);
      return enabledHere
        ? api.disableGeminiExtension(runtimeBaseUrl || '', workspaceId || '', name)
        : api.enableGeminiExtension(runtimeBaseUrl || '', workspaceId || '', name);
    },
    onSuccess: async (_result, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['gemini-extensions', runtimeBaseUrl, workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ['gemini-extension-detail', runtimeBaseUrl, workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ['agent-document-sidebar', runtimeBaseUrl, workspaceId, 'gemini'] });
      await queryClient.invalidateQueries({ queryKey: ['agent-file-tree'] });
      toast({
        title: variables.enabledHere
          ? t(`${I18N_PREFIX}.notifications.disabled.title`)
          : t(`${I18N_PREFIX}.notifications.enabled.title`),
        description: t(`${I18N_PREFIX}.notifications.scope.workspace`, { name: variables.name }),
      });
    },
    onError: (err) => {
      const message = err instanceof Error ? err.message : t(`${I18N_PREFIX}.errors.commandFailed`);
      setError(message);
      toast({ title: t(`${I18N_PREFIX}.errors.commandFailed`), description: message, variant: 'destructive' });
    },
  });

  const extensions = useMemo(() => listQuery.data?.extensions ?? [], [listQuery.data]);
  const modeFilteredExtensions = useMemo(
    () => extensions.filter((extension) => displayMode === 'all' || extension.enabledHere),
    [displayMode, extensions],
  );
  const normalizedSearchQuery = searchQuery.trim().toLowerCase();
  const visibleExtensions = useMemo(
    () => modeFilteredExtensions.filter((extension) => matchesSearch(extension, normalizedSearchQuery)),
    [modeFilteredExtensions, normalizedSearchQuery],
  );
  const totalPages = Math.max(1, Math.ceil(visibleExtensions.length / EXTENSIONS_PER_PAGE));
  const currentPageClamped = Math.min(currentPage, totalPages);
  const paginatedExtensions = useMemo(() => {
    const start = (currentPageClamped - 1) * EXTENSIONS_PER_PAGE;
    return visibleExtensions.slice(start, start + EXTENSIONS_PER_PAGE);
  }, [currentPageClamped, visibleExtensions]);
  const detail = detailQuery.data?.extension;
  const loading = listQuery.isLoading || workspaceRuntime.isLoading;

  useEffect(() => {
    setCurrentPage(1);
  }, [displayMode, normalizedSearchQuery]);

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const openDetail = (name: string) => {
    setSelectedName(name);
    setDetailOpen(true);
  };

  const toggleExtension = (extension: GeminiExtensionSummary) => {
    toggleMutation.mutate({ name: extension.name, enabledHere: extension.enabledHere });
  };

  return (
    <SettingsWorkflowShell
      title={t(`${I18N_PREFIX}.title`)}
      icon={Boxes}
      headerActions={
        <div className="flex flex-wrap items-center gap-2">
          <AgentSettingsLayerSelector
            value="workspace"
            onChange={() => undefined}
            options={[{
              value: 'workspace',
              label: t(`${I18N_PREFIX}.scope.workspace`),
              icon: <Building className="h-3 w-3" />,
            }]}
            label={t(`${I18N_PREFIX}.scope.label`)}
            disabled
            className="rounded-lg bg-muted/60 px-3 py-1"
          />
          <PluginDisplayModeToggle
            value={displayMode}
            labels={{
              enabled: t(`${I18N_PREFIX}.displayModes.enabled`),
              all: t(`${I18N_PREFIX}.displayModes.all`),
            }}
            onChange={setDisplayMode}
          />
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => void listQuery.refetch()}
            disabled={!enabled || listQuery.isFetching}
          >
            <RefreshCw className={cn('mr-1 h-3 w-3', listQuery.isFetching && 'animate-spin')} />
            {t(`${I18N_PREFIX}.actions.refresh`)}
          </Button>
        </div>
      }
      summary={
        <SettingsWorkflowCountBadge
          label={t(`${I18N_PREFIX}.search.resultCount`, { count: visibleExtensions.length })}
        />
      }
      controls={
        extensions.length > 0 ? (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative w-full max-w-md">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 transform text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={t(`${I18N_PREFIX}.search.placeholder`)}
                aria-label={t(`${I18N_PREFIX}.search.label`)}
                className="h-7 pl-9 text-xs"
              />
            </div>
            {normalizedSearchQuery ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 shrink-0 px-2 text-xs"
                onClick={() => setSearchQuery('')}
              >
                <X className="mr-1 h-3 w-3" />
                {t(`${I18N_PREFIX}.actions.clearSearch`)}
              </Button>
            ) : null}
          </div>
        ) : null
      }
      error={error ? (
        <Alert variant="destructive" className="border-0 bg-transparent p-0">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      isLoading={loading}
      loadingLabel={t(`${I18N_PREFIX}.loading`)}
      hasItems={extensions.length > 0}
      emptyTitle={t(`${I18N_PREFIX}.empty.title`)}
      emptyDescription={t(`${I18N_PREFIX}.empty.description`)}
      emptyIcon={<Boxes className="h-8 w-8 text-muted-foreground" />}
      contentClassName="p-6"
    >
      {visibleExtensions.length === 0 ? (
        <PluginEmptyState
          icon={<Boxes className="h-8 w-8" />}
          title={normalizedSearchQuery
            ? t(`${I18N_PREFIX}.empty.searchTitle`)
            : displayMode === 'enabled'
              ? t(`${I18N_PREFIX}.empty.enabledTitle`)
              : t(`${I18N_PREFIX}.empty.allTitle`)}
          description={normalizedSearchQuery
            ? t(`${I18N_PREFIX}.empty.searchDescription`)
            : displayMode === 'enabled'
              ? t(`${I18N_PREFIX}.empty.enabledDescription`)
              : t(`${I18N_PREFIX}.empty.installHint`)}
          actions={(
            <>
              {displayMode === 'enabled' && !normalizedSearchQuery ? (
                <Button variant="outline" size="sm" onClick={() => setDisplayMode('all')}>
                  {t(`${I18N_PREFIX}.actions.showAll`)}
                </Button>
              ) : null}
              {normalizedSearchQuery ? (
                <Button variant="outline" size="sm" onClick={() => setSearchQuery('')}>
                  {t(`${I18N_PREFIX}.actions.clearSearch`)}
                </Button>
              ) : null}
            </>
          )}
        />
      ) : (
        <>
          <PluginCardGrid>
            {paginatedExtensions.map((extension) => (
              <ExtensionCard
                key={extension.name}
                extension={extension}
                pending={toggleMutation.isPending}
                onToggle={() => toggleExtension(extension)}
                onDetails={() => openDetail(extension.name)}
              />
            ))}
          </PluginCardGrid>
          <PluginPagination
            page={currentPageClamped}
            totalPages={totalPages}
            totalItems={visibleExtensions.length}
            pageSize={EXTENSIONS_PER_PAGE}
            previousLabel={t(`${I18N_PREFIX}.pagination.previous`)}
            nextLabel={t(`${I18N_PREFIX}.pagination.next`)}
            pageLabel={t(`${I18N_PREFIX}.pagination.page`, { current: currentPageClamped, total: totalPages })}
            summaryLabel={t(`${I18N_PREFIX}.pagination.summary`, {
              start: visibleExtensions.length > 0 ? (currentPageClamped - 1) * EXTENSIONS_PER_PAGE + 1 : 0,
              end: visibleExtensions.length > 0 ? Math.min(currentPageClamped * EXTENSIONS_PER_PAGE, visibleExtensions.length) : 0,
              total: visibleExtensions.length,
            })}
            onPageChange={setCurrentPage}
          />
        </>
      )}

      <PluginDetailDialog
        open={detailOpen}
        onOpenChange={setDetailOpen}
        title={detail ? t(`${I18N_PREFIX}.detail.title`, { name: detail.name }) : t(`${I18N_PREFIX}.detail.fallbackTitle`)}
        description={detail?.installInfo?.source ?? t(`${I18N_PREFIX}.detail.noInstallSource`)}
        icon={<Sparkles className="h-5 w-5" />}
      >
        <ExtensionDetailPanel detail={detail} loading={detailQuery.isLoading} />
      </PluginDetailDialog>
    </SettingsWorkflowShell>
  );
};

const matchesSearch = (extension: GeminiExtensionSummary, normalizedQuery: string): boolean => {
  if (!normalizedQuery) {
    return true;
  }

  return [
    extension.name,
    extension.version,
    extension.description,
    extension.installSource,
    extension.installType,
    extension.releaseTag,
  ]
    .filter((value): value is string => Boolean(value))
    .some((value) => value.toLowerCase().includes(normalizedQuery));
};

const formatInstallSource = (source: string | null | undefined): string | null => {
  if (!source) {
    return null;
  }

  try {
    const url = new URL(source);
    if (url.hostname === 'github.com') {
      return url.pathname.replace(/^\/+/, '').replace(/\.git$/, '');
    }
  } catch {
    return source;
  }

  return source;
};

interface ExtensionCardProps {
  extension: GeminiExtensionSummary;
  pending: boolean;
  onToggle: () => void;
  onDetails: () => void;
}

const ExtensionCard: React.FC<ExtensionCardProps> = ({
  extension,
  pending,
  onToggle,
  onDetails,
}) => {
  const { t } = useI18n();
  const description = extension.description?.trim() || t(`${I18N_PREFIX}.descriptionFallback`);
  const subtitle = [
    extension.version ?? t(`${I18N_PREFIX}.unknownVersion`),
  ].filter((item): item is string => Boolean(item)).join(' · ');
  const installSource = formatInstallSource(extension.installSource);

  return (
    <PluginCard
      title={extension.name}
      subtitle={subtitle || extension.name}
      description={description}
      onTitleClick={onDetails}
      statusBadge={
        <PluginStatusPill
          enabled={extension.enabledHere}
          enabledLabel={t(`${I18N_PREFIX}.status.enabledHere`)}
          disabledLabel={t(`${I18N_PREFIX}.status.disabledHere`)}
        />
      }
      actions={
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 w-8 px-0">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">{t(`${I18N_PREFIX}.actions.more`)}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onDetails}>
              <FileText className="mr-2 h-4 w-4" />
              {t(`${I18N_PREFIX}.actions.details`)}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={pending} onClick={onToggle}>
              <Power className="mr-2 h-4 w-4" />
              {extension.enabledHere
                ? t(`${I18N_PREFIX}.actions.disableWorkspace`)
                : t(`${I18N_PREFIX}.actions.enableWorkspace`)}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      }
    >
      <div className="flex flex-wrap gap-2">
        {installSource ? <Badge variant="outline">{installSource}</Badge> : null}
        {extension.installType ? <Badge variant="outline">{extension.installType}</Badge> : null}
        {extension.releaseTag ? <Badge variant="outline">{extension.releaseTag}</Badge> : null}
        {extension.contextFileName ? <ResourceBadge label={extension.contextFileName} icon={FileText} /> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {cardResourceKeys.map((key) => (
          <ResourceBadge
            key={key}
            label={t(`${I18N_PREFIX}.counts.${key}`, { count: extension.resourceCounts[key] })}
            icon={resourceIcons[key]}
          />
        ))}
      </div>
    </PluginCard>
  );
};

const ExtensionDetailPanel: React.FC<{ detail?: GeminiExtensionDetail; loading: boolean }> = ({ detail, loading }) => {
  const { t } = useI18n();

  if (loading) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${I18N_PREFIX}.detail.loading`)}</div>;
  }
  if (!detail) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${I18N_PREFIX}.detail.empty`)}</div>;
  }

  return (
    <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-border px-6 pt-4">
        <TabsList className="h-9 w-full justify-start overflow-x-auto rounded-none bg-transparent p-0">
          <TabsTrigger value="overview" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.overview`)}
          </TabsTrigger>
          <TabsTrigger value="context" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.context`)}
          </TabsTrigger>
          <TabsTrigger value="policies" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.policies`)}
          </TabsTrigger>
          <TabsTrigger value="resources" className="h-9 rounded-none border-b-2 border-transparent px-3 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none">
            {t(`${I18N_PREFIX}.detail.tabs.resources`)}
          </TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="overview" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <GeminiExtensionOverview detail={detail} />
      </TabsContent>
      <TabsContent value="context" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        {detail.contextFile?.content ? (
          <MarkdownContent content={detail.contextFile.content} variant="detailed" className="rounded-lg border border-border bg-background px-4 py-3" />
        ) : (
          <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noContext`)}</span>
        )}
      </TabsContent>
      <TabsContent value="policies" className="mt-0 min-h-0 flex-1 overflow-auto px-6 pb-6 pt-5">
        <div className="space-y-3">
          {detail.policies.length
            ? detail.policies.map((policy) => (
              <div key={policy.path} className="overflow-hidden rounded-lg border border-border">
                <div className="truncate border-b border-border px-3 py-2 text-xs text-muted-foreground">{policy.path}</div>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap bg-muted/40 p-3 text-xs">
                  {policy.content}
                </pre>
              </div>
            ))
            : <p className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noPolicies`)}</p>}
        </div>
      </TabsContent>
      <TabsContent value="resources" className="mt-0 min-h-0 flex-1 space-y-5 overflow-auto px-6 pb-6 pt-5">
        <div className="flex flex-wrap gap-2">
          {detail.excludeTools.length
            ? detail.excludeTools.map((tool) => <Badge key={tool} variant="outline">{tool}</Badge>)
            : <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noExcludeTools`)}</span>}
        </div>
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
          {detail.overrides.length ? detail.overrides.join('\n') : t(`${I18N_PREFIX}.advanced.noOverrides`)}
        </pre>
        <div className="grid gap-2 sm:grid-cols-2">
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.mcpServers`)} count={detail.mcpServers.length} />
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.slashCommands`)} count={detail.slashCommands.length} />
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.skills`)} count={detail.skills.length} />
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.hooks`)} count={detail.hooks.length} />
        </div>
      </TabsContent>
    </Tabs>
  );
};

const GeminiExtensionOverview: React.FC<{ detail: GeminiExtensionDetail }> = ({ detail }) => {
  const { t } = useI18n();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <Badge variant={detail.enabledHere ? 'default' : 'secondary'}>
          {detail.enabledHere ? t(`${I18N_PREFIX}.status.enabledHere`) : t(`${I18N_PREFIX}.status.disabledHere`)}
        </Badge>
        {detail.version ? <Badge variant="outline">{detail.version}</Badge> : null}
        {detail.installInfo?.type ? <Badge variant="outline">{detail.installInfo.type}</Badge> : null}
        {detail.installInfo?.releaseTag ? <Badge variant="outline">{detail.installInfo.releaseTag}</Badge> : null}
      </div>
      <p className="whitespace-pre-wrap text-sm text-muted-foreground">
        {detail.installInfo?.source ?? t(`${I18N_PREFIX}.detail.noInstallSource`)}
      </p>
    </div>
  );
};

export default GeminiExtensionsPage;
