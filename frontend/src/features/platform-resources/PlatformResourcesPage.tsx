import React from 'react';
import { BarChart3, Database, ListChecks, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { AuthorizationDeniedState, useAuth } from '@/features/auth/public';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { PlatformResourceDistribution } from './components/PlatformResourceDistribution';
import { KnowledgeBaseQuotaDialog } from './components/KnowledgeBaseQuotaDialog';
import { OwnerReassignmentDialog } from './components/OwnerReassignmentDialog';
import { PlatformResourceInventoryTable } from './components/PlatformResourceInventoryTable';
import { PlatformResourceSummaryCards } from './components/PlatformResourceSummaryCards';
import {
  PlatformResourceCapacityTrendPanel,
  PlatformResourceTrendPanel,
} from './components/PlatformResourceTrendPanels';
import { WorkspaceCapacityExpansionDialog } from './components/WorkspaceCapacityExpansionDialog';
import { usePlatformResourcesDataSession } from './data-session/usePlatformResourcesDataSession';
import { usePlatformResourceUrlState } from './hooks/usePlatformResourceUrlState';
import type {
  PlatformResourceKind,
  PlatformResourceRange,
  PlatformResourceSummary,
} from './model/platformResourceTypes';

const PAGE_SIZE = 25;
const RESOURCE_RANGES: PlatformResourceRange[] = ['7d', '30d', '90d'];

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
};

interface PlatformResourcesPageProps {
  kind: PlatformResourceKind;
  section: 'management' | 'analytics';
}

const sectionRoute = (
  section: PlatformResourcesPageProps['section'],
  kind: PlatformResourceKind,
): string => {
  if (section === 'analytics') {
    return kind === 'workspaces'
      ? ROUTES.platformResources.analytics.workspaces
      : ROUTES.platformResources.analytics.knowledgeBases;
  }
  return kind === 'workspaces'
    ? ROUTES.platformResources.workspaces
    : ROUTES.platformResources.knowledgeBases;
};

export const PlatformResourcesPage: React.FC<PlatformResourcesPageProps> = ({ kind, section }) => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { allowedOperations, user } = useAuth();
  const {
    searchParams,
    range,
    query,
    page,
    health,
    visibility,
    indexingHealth,
    capacityRisk,
    sort,
    order,
    update: updateSearchParams,
  } = usePlatformResourceUrlState();
  const [searchInput, setSearchInput] = React.useState(query);
  const authSubject = user?.id ?? null;
  const listQuery = React.useMemo(() => ({
    q: query,
    page,
    pageSize: PAGE_SIZE,
    ...(kind === 'workspaces' && health ? { health } : {}),
    ...(kind === 'knowledge-bases' && visibility ? { visibility } : {}),
    ...(kind === 'knowledge-bases' && indexingHealth ? { indexingHealth } : {}),
    ...(capacityRisk ? { capacityRisk } : {}),
    ...(sort ? { sort } : {}),
    ...(order ? { order } : {}),
  }), [capacityRisk, health, indexingHealth, kind, order, page, query, sort, visibility]);
  const dataSession = usePlatformResourcesDataSession({
    authSubject,
    kind,
    section,
    range,
    listQuery,
    allowedOperations,
  });
  const { permissions, inventory, analytics } = dataSession;

  React.useEffect(() => {
    setSearchInput(query);
  }, [query]);

  const handleSearchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    updateSearchParams({ q: searchInput.trim(), page: null });
  };
  const totalPages = Math.max(1, Math.ceil(inventory.total / PAGE_SIZE));
  const detailRoute = (resource: PlatformResourceSummary) => (
    kind === 'workspaces'
      ? ROUTES.workspace.home(resource.id)
      : ROUTES.knowledgeBase.files(resource.id)
  );

  if (!permissions.canRead) {
    return <AuthorizationDeniedState />;
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Database
                aria-hidden="true"
                className="h-6 w-6 shrink-0 text-primary"
                data-testid="platform-resources-title-icon"
              />
              <h1 className="text-2xl font-semibold">{t('platformResources.title')}</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {t(`platformResources.sectionDescriptions.${section}`)}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {section === 'analytics' && analytics.summary.data?.calculatedAt ? (
              <div className="text-right text-xs text-muted-foreground">
                <div>{t('platformResources.statistics.lastUpdated', {
                  value: formatTimestamp(analytics.summary.data.calculatedAt),
                })}</div>
                {analytics.summary.data.collectionStartedAt ? (
                  <div>{t('platformResources.statistics.collectionStartedAt', {
                    value: formatTimestamp(analytics.summary.data.collectionStartedAt),
                  })}</div>
                ) : null}
              </div>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              disabled={dataSession.refresh.isRefreshing}
              onClick={() => { void dataSession.refresh.run(); }}
            >
              <RefreshCw aria-hidden="true" className="mr-1.5 h-4 w-4" />
              {t('platformResources.actions.refresh')}
            </Button>
          </div>
        </div>

        <nav
          aria-label={t('platformResources.title')}
          className="flex w-fit items-center gap-1 rounded-xl border bg-muted/40 p-1"
        >
          <Button
            type="button"
            size="sm"
            variant={section === 'management' ? 'default' : 'ghost'}
            className="gap-2"
            aria-current={section === 'management' ? 'page' : undefined}
            onClick={() => navigate(sectionRoute('management', kind))}
          >
            <ListChecks aria-hidden="true" className="h-4 w-4" />
            {t('platformResources.sections.management')}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={section === 'analytics' ? 'default' : 'ghost'}
            className="gap-2"
            aria-current={section === 'analytics' ? 'page' : undefined}
            onClick={() => navigate(sectionRoute('analytics', kind))}
          >
            <BarChart3 aria-hidden="true" className="h-4 w-4" />
            {t('platformResources.sections.analytics')}
          </Button>
        </nav>

        <Tabs
          value={kind}
          onValueChange={value => {
            const path = sectionRoute(section, value as PlatformResourceKind);
            const queryString = searchParams.toString();
            navigate(queryString ? `${path}?${queryString}` : path);
          }}
        >
          <TabsList>
            <TabsTrigger value="workspaces">{t('platformResources.tabs.workspaces')}</TabsTrigger>
            <TabsTrigger value="knowledge-bases">{t('platformResources.tabs.knowledgeBases')}</TabsTrigger>
          </TabsList>
        </Tabs>

        {section === 'analytics' ? (
          <>
            <div className="flex flex-wrap gap-2" aria-label={t('platformResources.statistics.ranges.label')}>
              {RESOURCE_RANGES.map(value => (
                <Button
                  key={value}
                  type="button"
                  size="sm"
                  variant={range === value ? 'default' : 'outline'}
                  aria-pressed={range === value}
                  onClick={() => updateSearchParams({ range: value, page: null })}
                >
                  {t(`platformResources.statistics.ranges.${value}`)}
                </Button>
              ))}
            </div>

            <PlatformResourceSummaryCards
              summary={analytics.summary.data}
              isLoading={analytics.summary.isLoading}
              hasError={analytics.summary.hasError}
              onRetry={() => { void analytics.summary.retry(); }}
              onNearLimit={() => navigate(`${sectionRoute('management', kind)}?capacityRisk=warning`)}
            />
            <PlatformResourceDistribution summary={analytics.summary.data} />
            <div className="grid gap-4 xl:grid-cols-2">
              <PlatformResourceTrendPanel
                trend={analytics.resourceTrend.data}
                isLoading={analytics.resourceTrend.isLoading}
                hasError={analytics.resourceTrend.hasError}
                onRetry={() => { void analytics.resourceTrend.retry(); }}
              />
              <PlatformResourceCapacityTrendPanel
                trend={analytics.capacityTrend.data}
                isLoading={analytics.capacityTrend.isLoading}
                hasError={analytics.capacityTrend.hasError}
                onRetry={() => { void analytics.capacityTrend.retry(); }}
              />
            </div>
          </>
        ) : (
          <>

        <div className="flex flex-wrap items-end gap-3">
        <form className="flex min-w-72 max-w-xl flex-1 gap-2" role="search" onSubmit={handleSearchSubmit}>
          <Input
            type="search"
            aria-label={t('platformResources.search.label')}
            placeholder={t('platformResources.search.placeholder')}
            value={searchInput}
            onChange={event => setSearchInput(event.target.value)}
          />
          <Button type="submit">{t('platformResources.search.submit')}</Button>
        </form>
        {kind === 'workspaces' ? (
          <label className="space-y-1 text-xs text-muted-foreground">
            <span>{t('platformResources.filters.health')}</span>
            <select className="block h-10 rounded-md border bg-background px-3 text-sm text-foreground" value={health ?? ''} onChange={event => updateSearchParams({ health: event.target.value, page: null })}>
              <option value="">{t('platformResources.filters.all')}</option>
              {['running', 'transitioning', 'stopped', 'error', 'deleting'].map(value => <option key={value} value={value}>{t(`platformResources.runtimeStatus.${value}`)}</option>)}
            </select>
          </label>
        ) : (
          <>
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>{t('platformResources.filters.visibility')}</span>
              <select className="block h-10 rounded-md border bg-background px-3 text-sm text-foreground" value={visibility ?? ''} onChange={event => updateSearchParams({ visibility: event.target.value, page: null })}>
                <option value="">{t('platformResources.filters.all')}</option>
                {['private', 'public'].map(value => <option key={value} value={value}>{t(`platformResources.visibility.${value}`)}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-xs text-muted-foreground">
              <span>{t('platformResources.filters.indexingHealth')}</span>
              <select className="block h-10 rounded-md border bg-background px-3 text-sm text-foreground" value={indexingHealth ?? ''} onChange={event => updateSearchParams({ indexingHealth: event.target.value, page: null })}>
                <option value="">{t('platformResources.filters.all')}</option>
                {['success', 'processing', 'failure', 'never_indexed'].map(value => <option key={value} value={value}>{t(`platformResources.statistics.distributions.${value}`)}</option>)}
              </select>
            </label>
          </>
        )}
        <label className="space-y-1 text-xs text-muted-foreground">
          <span>{t('platformResources.filters.capacityRisk')}</span>
          <select className="block h-10 rounded-md border bg-background px-3 text-sm text-foreground" value={capacityRisk ?? ''} onChange={event => updateSearchParams({ capacityRisk: event.target.value, page: null })}>
            <option value="">{t('platformResources.filters.all')}</option>
            {['normal', 'warning', 'critical', 'unknown', 'stale'].map(value => <option key={value} value={value}>{t(`platformResources.capacity.risks.${value}`)}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-xs text-muted-foreground">
          <span>{t('platformResources.filters.sort')}</span>
          <select className="block h-10 rounded-md border bg-background px-3 text-sm text-foreground" value={sort ?? ''} onChange={event => updateSearchParams({ sort: event.target.value, page: null })}>
            <option value="">{t('platformResources.filters.defaultSort')}</option>
            {['name', 'created_at', 'used_bytes', 'utilization'].map(value => <option key={value} value={value}>{t(`platformResources.filters.sortOptions.${value}`)}</option>)}
          </select>
        </label>
        <Button type="button" variant="outline" onClick={() => updateSearchParams({ order: order === 'asc' ? 'desc' : 'asc', page: null })}>
          {t(`platformResources.filters.order.${order ?? 'asc'}`)}
        </Button>
        </div>

        <PlatformResourceInventoryTable
          kind={kind}
          items={inventory.items}
          isLoading={inventory.isLoading}
          hasError={inventory.hasError}
          detailRoute={detailRoute}
          onReassign={dataSession.commands.openOwnerReassignment}
          onManageQuota={dataSession.commands.openKnowledgeBaseQuota}
          onExpand={dataSession.commands.openCapacityExpansion}
          canReassignOwner={permissions.canReassignOwner}
          canManageKnowledgeBaseQuota={permissions.canManageKnowledgeBaseQuota}
          canExpandWorkspaceCapacity={permissions.canExpandWorkspaceCapacity}
        />

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {t('platformResources.pagination.summary', { page, totalPages, total: inventory.total })}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={page <= 1 || inventory.isLoading}
              onClick={() => updateSearchParams({ page: String(Math.max(1, page - 1)) })}
            >
              {t('platformResources.pagination.previous')}
            </Button>
            <Button
              variant="outline"
              disabled={page >= totalPages || inventory.isLoading}
              onClick={() => updateSearchParams({ page: String(Math.min(totalPages, page + 1)) })}
            >
              {t('platformResources.pagination.next')}
            </Button>
          </div>
        </div>
          </>
        )}
      </div>

      {section === 'management' ? (
        <>
      <OwnerReassignmentDialog
        selectionIdentity={dataSession.dialogs.ownerReassignment.selectionIdentity}
        resource={permissions.canReassignOwner ? dataSession.dialogs.ownerReassignment.resource : null}
        candidates={dataSession.dialogs.ownerReassignment.candidates}
        isSearching={dataSession.dialogs.ownerReassignment.isSearching}
        searchError={dataSession.dialogs.ownerReassignment.searchError}
        isSubmitting={dataSession.dialogs.ownerReassignment.isSubmitting}
        submitError={dataSession.dialogs.ownerReassignment.submitError}
        onSearch={dataSession.dialogs.ownerReassignment.search}
        onSubmit={dataSession.dialogs.ownerReassignment.submit}
        onClose={dataSession.dialogs.ownerReassignment.reset}
      />
      <KnowledgeBaseQuotaDialog
        selectionIdentity={dataSession.dialogs.knowledgeBaseQuota.selectionIdentity}
        resource={permissions.canManageKnowledgeBaseQuota
          ? dataSession.dialogs.knowledgeBaseQuota.resource
          : null}
        onSubmit={dataSession.dialogs.knowledgeBaseQuota.submit}
        isSubmitting={dataSession.dialogs.knowledgeBaseQuota.isSubmitting}
        hasError={dataSession.dialogs.knowledgeBaseQuota.hasError}
        onClose={dataSession.dialogs.knowledgeBaseQuota.reset}
      />
      <WorkspaceCapacityExpansionDialog
        resource={permissions.canExpandWorkspaceCapacity
          ? dataSession.dialogs.capacityExpansion.resource
          : null}
        onSubmit={dataSession.dialogs.capacityExpansion.submit}
        status={dataSession.dialogs.capacityExpansion.status}
        isSubmitting={dataSession.dialogs.capacityExpansion.isSubmitting}
        hasError={dataSession.dialogs.capacityExpansion.hasError}
        onClose={dataSession.dialogs.capacityExpansion.reset}
      />
        </>
      ) : null}
    </div>
  );
};
