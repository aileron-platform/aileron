import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Boxes,
  CheckCircle2,
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
import { Card, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
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
import { SettingsWorkflowShell } from '@/shared/components/settings-workflow';
import { createAgentSettingsApi, type GeminiExtensionDetail, type GeminiExtensionSummary } from '../services/agentSettingsApi';

const I18N_PREFIX = 'workspace.agentSettings.geminiExtensions';
const EXTENSIONS_PER_PAGE = 6;

type DisplayMode = 'enabled' | 'all';
type ToggleScope = 'workspace' | 'user';
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
  const [displayMode, setDisplayMode] = useState<DisplayMode>('enabled');
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
    mutationFn: ({ name, scope, enabledHere }: { name: string; scope: ToggleScope; enabledHere: boolean }) => {
      setError(null);
      return enabledHere
        ? api.disableGeminiExtension(runtimeBaseUrl || '', workspaceId || '', name, scope)
        : api.enableGeminiExtension(runtimeBaseUrl || '', workspaceId || '', name, scope);
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
        description: t(`${I18N_PREFIX}.notifications.scope.${variables.scope}`, { name: variables.name }),
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

  const toggleExtension = (extension: GeminiExtensionSummary, scope: ToggleScope) => {
    toggleMutation.mutate({ name: extension.name, scope, enabledHere: extension.enabledHere });
  };

  const modeControls = (
    <div className="flex flex-wrap items-center gap-2">
      {(['enabled', 'all'] as const).map((mode) => (
        <Button
          key={mode}
          type="button"
          variant={displayMode === mode ? 'default' : 'outline'}
          size="sm"
          className="h-8 px-3 text-xs"
          onClick={() => setDisplayMode(mode)}
        >
          {t(`${I18N_PREFIX}.displayModes.${mode}`)}
        </Button>
      ))}
    </div>
  );

  return (
    <SettingsWorkflowShell
      title={t(`${I18N_PREFIX}.title`)}
      icon={Boxes}
      headerActions={
        <div className="flex flex-wrap items-center gap-2">
          {modeControls}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => void listQuery.refetch()}
            disabled={!enabled || listQuery.isFetching}
          >
            <RefreshCw className={`mr-1 h-3 w-3 ${listQuery.isFetching ? 'animate-spin' : ''}`} />
            {t(`${I18N_PREFIX}.actions.refresh`)}
          </Button>
        </div>
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
      contentClassName="p-6"
    >
      {extensions.length > 0 ? (
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex w-full gap-2 lg:max-w-md">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={t(`${I18N_PREFIX}.search.placeholder`)}
                aria-label={t(`${I18N_PREFIX}.search.label`)}
                className="pl-9"
              />
            </div>
            {normalizedSearchQuery ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-10 shrink-0 px-3"
                onClick={() => setSearchQuery('')}
              >
                <X className="mr-1 h-4 w-4" />
                {t(`${I18N_PREFIX}.actions.clearSearch`)}
              </Button>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            {t(`${I18N_PREFIX}.search.resultCount`, { count: visibleExtensions.length })}
          </p>
        </div>
      ) : null}

      {visibleExtensions.length === 0 ? (
        <div className="flex h-full min-h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-6 text-center">
          <Boxes className="h-8 w-8 text-muted-foreground" />
          <div className="space-y-1">
            <p className="text-base font-medium">
              {normalizedSearchQuery
                ? t(`${I18N_PREFIX}.empty.searchTitle`)
                : displayMode === 'enabled'
                  ? t(`${I18N_PREFIX}.empty.enabledTitle`)
                  : t(`${I18N_PREFIX}.empty.allTitle`)}
            </p>
            <p className="max-w-md text-sm text-muted-foreground">
              {normalizedSearchQuery
                ? t(`${I18N_PREFIX}.empty.searchDescription`)
                : displayMode === 'enabled'
                  ? t(`${I18N_PREFIX}.empty.enabledDescription`)
                  : t(`${I18N_PREFIX}.empty.installHint`)}
            </p>
          </div>
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
        </div>
      ) : (
        <>
          <div className="grid items-stretch gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {paginatedExtensions.map((extension) => (
              <ExtensionCard
                key={extension.name}
                extension={extension}
                pending={toggleMutation.isPending}
                onToggleWorkspace={() => toggleExtension(extension, 'workspace')}
                onToggleUser={() => toggleExtension(extension, 'user')}
                onDetails={() => openDetail(extension.name)}
              />
            ))}
          </div>
          <ExtensionPagination
            page={currentPageClamped}
            totalPages={totalPages}
            totalItems={visibleExtensions.length}
            pageSize={EXTENSIONS_PER_PAGE}
            onPageChange={setCurrentPage}
          />
        </>
      )}

      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="flex max-h-[85vh] max-w-4xl flex-col overflow-hidden p-0">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>{detail ? t(`${I18N_PREFIX}.detail.title`, { name: detail.name }) : t(`${I18N_PREFIX}.detail.fallbackTitle`)}</DialogTitle>
            <DialogDescription>
              {detail?.installInfo?.source ?? t(`${I18N_PREFIX}.detail.noInstallSource`)}
            </DialogDescription>
          </DialogHeader>
          <ExtensionDetailPanel detail={detail} loading={detailQuery.isLoading} />
        </DialogContent>
      </Dialog>
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

interface ExtensionPaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

const ExtensionPagination: React.FC<ExtensionPaginationProps> = ({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}) => {
  const { t } = useI18n();
  const startItem = totalItems > 0 ? (page - 1) * pageSize + 1 : 0;
  const endItem = totalItems > 0 ? Math.min(page * pageSize, totalItems) : 0;
  const canGoPrevious = page > 1;
  const canGoNext = page < totalPages;

  if (totalItems <= pageSize) {
    return null;
  }

  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <span>
        {t(`${I18N_PREFIX}.pagination.summary`, { start: startItem, end: endItem, total: totalItems })}
      </span>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canGoPrevious}
          onClick={() => onPageChange(page - 1)}
        >
          {t(`${I18N_PREFIX}.pagination.previous`)}
        </Button>
        <span className="min-w-20 text-center">
          {t(`${I18N_PREFIX}.pagination.page`, { current: page, total: totalPages })}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canGoNext}
          onClick={() => onPageChange(page + 1)}
        >
          {t(`${I18N_PREFIX}.pagination.next`)}
        </Button>
      </div>
    </div>
  );
};

interface ExtensionCardProps {
  extension: GeminiExtensionSummary;
  pending: boolean;
  onToggleWorkspace: () => void;
  onToggleUser: () => void;
  onDetails: () => void;
}

const ExtensionCard: React.FC<ExtensionCardProps> = ({
  extension,
  pending,
  onToggleWorkspace,
  onToggleUser,
  onDetails,
}) => {
  const { t } = useI18n();
  const description = extension.description?.trim() || t(`${I18N_PREFIX}.descriptionFallback`);
  const metadata = [
    extension.version ?? t(`${I18N_PREFIX}.unknownVersion`),
    formatInstallSource(extension.installSource),
    extension.installType,
    extension.releaseTag,
  ].filter((item): item is string => Boolean(item));

  return (
    <Card
      className={cn(
        'flex h-full flex-col overflow-hidden border-border/80 transition-colors',
        extension.enabledHere
          ? 'bg-card'
          : 'border-dashed bg-muted/30 text-muted-foreground',
      )}
    >
      <CardHeader className="flex h-full flex-col gap-4 border-b-0 pb-5">
        <div className="flex items-center justify-between gap-3">
          <ExtensionStatusPill enabled={extension.enabledHere} />
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
              <DropdownMenuItem disabled={pending} onClick={onToggleWorkspace}>
                <Power className="mr-2 h-4 w-4" />
                {extension.enabledHere
                  ? t(`${I18N_PREFIX}.actions.disableWorkspace`)
                  : t(`${I18N_PREFIX}.actions.enableWorkspace`)}
              </DropdownMenuItem>
              <DropdownMenuItem disabled={pending} onClick={onToggleUser}>
                <Power className="mr-2 h-4 w-4" />
                {extension.enabledHere
                  ? t(`${I18N_PREFIX}.actions.disableUser`)
                  : t(`${I18N_PREFIX}.actions.enableUser`)}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <CardTitle className="truncate text-xl font-semibold">{extension.name}</CardTitle>
            <div className="line-clamp-2 text-xs leading-4 text-muted-foreground">
              {metadata.map((item) => (
                <span key={item} className="mr-2 inline-block">{item}</span>
              ))}
            </div>
          </div>
          <div className={cn(
            'grid h-11 w-11 shrink-0 place-content-center rounded-xl border',
            extension.enabledHere ? 'border-primary/30 bg-primary/10 text-primary' : 'border-border bg-background text-muted-foreground',
          )}>
            <Sparkles className="h-5 w-5" />
          </div>
        </div>
        <p className="line-clamp-2 text-sm leading-6 text-muted-foreground">{description}</p>
        <div className="flex flex-wrap gap-2 pt-1">
          {extension.contextFileName ? (
            <ResourceBadge label={extension.contextFileName} icon={FileText} />
          ) : null}
          {cardResourceKeys.map((key) => (
            <ResourceBadge
              key={key}
              label={t(`${I18N_PREFIX}.counts.${key}`, { count: extension.resourceCounts[key] })}
              icon={resourceIcons[key]}
            />
          ))}
        </div>
      </CardHeader>
    </Card>
  );
};

const ExtensionStatusPill: React.FC<{ enabled: boolean }> = ({ enabled }) => {
  const { t } = useI18n();

  return (
    <span
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium',
        enabled
          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
          : 'border-border bg-muted text-muted-foreground',
      )}
    >
      {enabled ? <CheckCircle2 className="h-3.5 w-3.5" /> : <span className="h-2 w-2 rounded-full bg-muted-foreground/60" />}
      {enabled ? t(`${I18N_PREFIX}.status.enabledHere`) : t(`${I18N_PREFIX}.status.disabledHere`)}
    </span>
  );
};

const ResourceBadge: React.FC<{ label: string; icon: React.ComponentType<{ className?: string }> }> = ({ label, icon: Icon }) => (
  <Badge variant="outline" className="gap-1.5 text-xs">
    <Icon className="h-3.5 w-3.5" />
    {label}
  </Badge>
);

const ExtensionDetailPanel: React.FC<{ detail?: GeminiExtensionDetail; loading: boolean }> = ({ detail, loading }) => {
  const { t } = useI18n();

  if (loading) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${I18N_PREFIX}.detail.loading`)}</div>;
  }
  if (!detail) {
    return <div className="px-6 py-8 text-sm text-muted-foreground">{t(`${I18N_PREFIX}.detail.empty`)}</div>;
  }

  return (
    <div className="min-h-0 flex-1 space-y-5 overflow-auto px-6 pb-6">
      <div className="flex flex-wrap gap-2">
        <Badge variant={detail.enabledHere ? 'default' : 'secondary'}>
          {detail.enabledHere ? t(`${I18N_PREFIX}.status.enabledHere`) : t(`${I18N_PREFIX}.status.disabledHere`)}
        </Badge>
        {detail.version ? <Badge variant="outline">{detail.version}</Badge> : null}
        {detail.installInfo?.type ? <Badge variant="outline">{detail.installInfo.type}</Badge> : null}
        {detail.installInfo?.releaseTag ? <Badge variant="outline">{detail.installInfo.releaseTag}</Badge> : null}
      </div>
      <DetailSection title={t(`${I18N_PREFIX}.detail.context`)}>
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
          {detail.contextFile?.content ?? t(`${I18N_PREFIX}.detail.noContext`)}
        </pre>
      </DetailSection>
      <DetailSection title={t(`${I18N_PREFIX}.detail.policies`)}>
        <div className="space-y-2">
          {detail.policies.length
            ? detail.policies.map((policy) => (
              <pre key={policy.path} className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
                {policy.content}
              </pre>
            ))
            : <p className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noPolicies`)}</p>}
        </div>
      </DetailSection>
      <DetailSection title={t(`${I18N_PREFIX}.detail.excludeTools`)}>
        <div className="flex flex-wrap gap-2">
          {detail.excludeTools.length
            ? detail.excludeTools.map((tool) => <Badge key={tool} variant="outline">{tool}</Badge>)
            : <span className="text-xs text-muted-foreground">{t(`${I18N_PREFIX}.detail.noExcludeTools`)}</span>}
        </div>
      </DetailSection>
      <DetailSection title={t(`${I18N_PREFIX}.advanced.overrides`)}>
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs">
          {detail.overrides.length ? detail.overrides.join('\n') : t(`${I18N_PREFIX}.advanced.noOverrides`)}
        </pre>
      </DetailSection>
      <DetailSection title={t(`${I18N_PREFIX}.detail.resources`)}>
        <div className="grid gap-2 sm:grid-cols-2">
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.mcpServers`)} count={detail.mcpServers.length} />
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.slashCommands`)} count={detail.slashCommands.length} />
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.skills`)} count={detail.skills.length} />
          <ResourceSummary label={t(`${I18N_PREFIX}.detail.hooks`)} count={detail.hooks.length} />
        </div>
      </DetailSection>
    </div>
  );
};

const DetailSection: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <section>
    <h3 className="mb-2 text-sm font-medium">{title}</h3>
    {children}
  </section>
);

const ResourceSummary: React.FC<{ label: string; count: number }> = ({ label, count }) => (
  <div className="flex items-center justify-between rounded border border-border p-3 text-sm">
    <span className="text-muted-foreground">{label}</span>
    <Badge variant="secondary">{count}</Badge>
  </div>
);

export default GeminiExtensionsPage;
