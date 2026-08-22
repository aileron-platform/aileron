import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutGrid, Search } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { useMarketplaceVersionControlSession } from '@/shared/version-control';
import type {
  MarketplaceImportResult,
  MarketplaceListQuery,
  MarketplaceListResult,
  MarketplacePackageSummary,
  MarketplaceCreateRequest,
  MarketplaceRegistrySettings,
} from '@/features/marketplace/model/marketplaceTypes';
import {
  canRunMarketplacePackageAction,
  resolveMarketplacePermissions,
  type MarketplacePackageAction,
} from '../../model/marketplacePermissions';
import {
  createPackage,
  getRegistrySettings,
  listPackages,
} from '../../api/marketplaceApi';
import { MarketplacePackageCard } from './components/MarketplacePackageCard';
import { MarketplaceFirstRunOnboarding } from './components/MarketplaceFirstRunOnboarding';
import { MarketplacePackageListRow } from './components/MarketplacePackageListRow';
import { MarketplacePackageActionDialog } from './components/MarketplacePackageActionDialog';
import { MarketplaceImportDialog } from './components/MarketplaceImportDialog';
import { MarketplaceCenterFilters } from './components/MarketplaceCenterFilters';
import { MarketplaceCenterHeaderActions } from './components/MarketplaceCenterHeaderActions';
import { MarketplaceCenterListToolbar } from './components/MarketplaceCenterListToolbar';
import { MarketplaceCenterPagination } from './components/MarketplaceCenterPagination';
import { CreatePackageDialog } from './components/CreatePackageDialog';
import {
  MARKETPLACE_STORAGE_USER_SCOPE,
  loadMarketplaceCenterFilters,
  loadMarketplaceCenterViewMode,
  saveMarketplaceCenterFilters,
  saveMarketplaceCenterViewMode,
  type MarketplaceCenterViewMode,
} from '../../storage/marketplaceStorage';
import {
  buildMarketplaceListQuery,
  resolveImportedPackageRevealFilters,
  type MarketplaceCenterQueryState,
} from './marketplaceCenterModel';
import { useAuth } from '@/features/auth/public';
import { MarketplaceShellAdapter } from '../../components/MarketplaceShellAdapter';

const canonicalPackageListKey = (query: MarketplaceListQuery): string => JSON.stringify(
  Object.entries(query)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => [
      key,
      Array.isArray(value) ? [...value].sort() : value,
    ]),
);

const resolveCreatePackageErrorKey = (error: unknown): string => {
  if (typeof error === 'object' && error !== null && 'status' in error) {
    const status = (error as { status?: unknown }).status;
    if (status === 409) return 'marketplace.createPackage.errors.duplicate';
    if (status === 400 || status === 422) return 'marketplace.createPackage.errors.validation';
  }
  return 'marketplace.createPackage.errors.generic';
};

export interface MarketplaceCenterPageProps {
  navigationSlot?: React.ReactNode;
}

export const MarketplaceCenterPage: React.FC<MarketplaceCenterPageProps> = ({ navigationSlot }) => {
  const { t } = useI18n();
  const { platformRole } = useAuth();
  const navigate = useNavigate();
  const versionControl = useMarketplaceVersionControlSession({ isGitRepo: false });
  const initializeRepositoryMutation =
    versionControl.remote.useInitializeRepositoryMutation();
  const initialFilters = React.useMemo(
    () => loadMarketplaceCenterFilters(MARKETPLACE_STORAGE_USER_SCOPE),
    [],
  );
  const [queryState, setQueryState] = React.useState<MarketplaceCenterQueryState>(
    () => ({
      searchTerm: '',
      targetClient: initialFilters.targetClient,
      activeFeatures: new Set(initialFilters.features),
      category: initialFilters.category,
      page: 1,
      pageSize: 12,
    }),
  );
  const {
    searchTerm,
    targetClient,
    activeFeatures,
    category,
    page,
    pageSize,
  } = queryState;
  const [viewMode, setViewMode] = React.useState<MarketplaceCenterViewMode>(
    () => loadMarketplaceCenterViewMode(MARKETPLACE_STORAGE_USER_SCOPE),
  );
  const [result, setResult] = React.useState<MarketplaceListResult | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [registrySettings, setRegistrySettings] = React.useState<MarketplaceRegistrySettings | null>(null);
  const [isImportOpen, setIsImportOpen] = React.useState(false);
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [isCreatingPackage, setIsCreatingPackage] = React.useState(false);
  const [createErrorKey, setCreateErrorKey] = React.useState<string | null>(null);
  const [packageAction, setPackageAction] = React.useState<{
    type: MarketplacePackageAction;
    item: MarketplacePackageSummary;
  } | null>(null);
  const permissions = React.useMemo(
    () => resolveMarketplacePermissions(platformRole),
    [platformRole],
  );
  const registrySettingsRequest = React.useRef<Promise<MarketplaceRegistrySettings> | null>(
    null,
  );
  const packageListRequests = React.useRef(
    new Map<string, Promise<MarketplaceListResult>>(),
  );
  const latestPackageRequest = React.useRef(0);
  const loadRegistrySettingsSingleFlight = React.useCallback(() => {
    const existing = registrySettingsRequest.current;
    if (existing) {
      return existing;
    }
    const request = getRegistrySettings();
    registrySettingsRequest.current = request;
    void request.then(
      () => {
        if (registrySettingsRequest.current === request) {
          registrySettingsRequest.current = null;
        }
      },
      () => {
        if (registrySettingsRequest.current === request) {
          registrySettingsRequest.current = null;
        }
      },
    );
    return request;
  }, []);

  const loadPackageListSingleFlight = React.useCallback((
    query: MarketplaceListQuery,
  ): Promise<MarketplaceListResult> => {
    const key = canonicalPackageListKey(query);
    const existing = packageListRequests.current.get(key);
    if (existing) {
      return existing;
    }
    const request = listPackages(query);
    packageListRequests.current.set(key, request);
    void request.then(
      () => {
        if (packageListRequests.current.get(key) === request) {
          packageListRequests.current.delete(key);
        }
      },
      () => {
        if (packageListRequests.current.get(key) === request) {
          packageListRequests.current.delete(key);
        }
      },
    );
    return request;
  }, []);

  React.useEffect(() => {
    if (!permissions.canManageRegistry) {
      setRegistrySettings(null);
      return undefined;
    }
    let isActive = true;
    void loadRegistrySettingsSingleFlight().then(settings => {
      if (isActive) setRegistrySettings(settings);
    });
    return () => { isActive = false; };
  }, [loadRegistrySettingsSingleFlight, permissions.canManageRegistry]);

  const loadPackages = React.useCallback(async ({
    overrides = {},
    singleFlight = true,
  }: {
    overrides?: Partial<MarketplaceListQuery>;
    singleFlight?: boolean;
  } = {}) => {
    const requestId = ++latestPackageRequest.current;
    setIsLoading(true);
    setError(null);
    try {
      const query = buildMarketplaceListQuery(queryState, overrides);
      const data = await (
        singleFlight ? loadPackageListSingleFlight(query) : listPackages(query)
      );
      if (requestId !== latestPackageRequest.current) return;
      setResult(data);
    } catch (err) {
      if (requestId !== latestPackageRequest.current) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (requestId === latestPackageRequest.current) {
        setIsLoading(false);
      }
    }
  }, [loadPackageListSingleFlight, queryState]);

  React.useEffect(() => {
    void loadPackages();
    return () => {
      latestPackageRequest.current += 1;
    };
  }, [loadPackages]);

  React.useEffect(() => {
    saveMarketplaceCenterFilters(MARKETPLACE_STORAGE_USER_SCOPE, {
      targetClient,
      category,
      features: Array.from(activeFeatures),
    });
  }, [activeFeatures, category, targetClient]);

  React.useEffect(() => {
    saveMarketplaceCenterViewMode(MARKETPLACE_STORAGE_USER_SCOPE, viewMode);
  }, [viewMode]);

  const openDetail = (item: MarketplacePackageSummary) => {
    navigate(ROUTES.marketplace.packageDetail(item.targetClient, item.packageId, item.packageFormat));
  };

  const openEdit = (item: MarketplacePackageSummary) => {
    if (!permissions.canEdit) return;
    navigate(ROUTES.marketplace.packageEdit(item.targetClient, item.packageId, item.packageFormat));
  };

  const completeRegistrySetup = async () => {
    if (!permissions.canManageRegistry) return;
    try {
      await initializeRepositoryMutation.mutateAsync(undefined);
      const settings = await getRegistrySettings();
      setRegistrySettings(settings);
      await loadPackages({ singleFlight: false });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const resetFilters = () => {
    setQueryState(current => ({
      ...current,
      searchTerm: '',
      targetClient: 'all',
      activeFeatures: new Set(),
      category: 'all',
      page: 1,
    }));
  };

  const revealImportedPackages = (importResult: MarketplaceImportResult) => {
    const revealFilters = resolveImportedPackageRevealFilters(importResult);
    if (!revealFilters) {
      void loadPackages({ singleFlight: false });
      return;
    }
    setQueryState(current => ({
      ...current,
      searchTerm: revealFilters.q ?? '',
      targetClient: revealFilters.targetClient ?? 'all',
      activeFeatures: new Set(revealFilters.features ?? []),
      category: revealFilters.category ?? 'all',
      page: revealFilters.page ?? 1,
    }));
  };

  const submitCreatePackage = async (request: MarketplaceCreateRequest) => {
    if (!permissions.canEdit) return;
    setIsCreatingPackage(true);
    setCreateErrorKey(null);
    try {
      const created = await createPackage(request);
      setIsCreateOpen(false);
      navigate(ROUTES.marketplace.packageEdit(
        created.targetClient,
        created.packageId,
        created.packageFormat,
        'basic',
      ));
    } catch (err) {
      setCreateErrorKey(resolveCreatePackageErrorKey(err));
    } finally {
      setIsCreatingPackage(false);
    }
  };

  const totalPages = result?.totalPages ?? 1;
  const visibleItems = result?.items ?? [];
  const visiblePackageAction = packageAction
    && canRunMarketplacePackageAction(packageAction.type, permissions)
    ? packageAction
    : null;

  React.useEffect(() => {
    if (!permissions.canEdit) {
      setIsImportOpen(false);
      setIsCreateOpen(false);
      setCreateErrorKey(null);
    }
    setPackageAction(current => (
      current && (
        (current.type === 'install' && !permissions.canInstall)
        || (current.type === 'delete' && !permissions.canDelete)
        || (current.type === 'export' && !permissions.canExport)
      )
        ? null
        : current
    ));
  }, [
    permissions.canDelete,
    permissions.canEdit,
    permissions.canExport,
    permissions.canInstall,
  ]);

  const openPackageAction = (
    type: MarketplacePackageAction,
    item: MarketplacePackageSummary,
  ) => {
    if (!canRunMarketplacePackageAction(type, permissions)) return;
    setPackageAction({ type, item });
  };

  if (registrySettings?.status === 'uninitialized') {
    return (
      <MarketplaceShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          content: (
            <MarketplaceFirstRunOnboarding
              rootPath={registrySettings.rootPath}
              canManageRegistry={permissions.canManageRegistry}
              onInitialize={completeRegistrySetup}
              onClone={() => navigate(ROUTES.marketplace.settings)}
            />
          ),
        }}
      />
    );
  }

  const centerHeader = (
    <FeatureHeader
        title={t('marketplace.center.header.title')}
        icon={LayoutGrid}
        breadcrumbs={[t('marketplace.breadcrumbs.root')]}
        info={(
          <div className="flex items-center gap-2 text-xs text-muted-foreground whitespace-nowrap">
            <span>{t('marketplace.center.header.description')}</span>
            <span className="text-muted-foreground/50">·</span>
            <span>
              {t('marketplace.center.header.stats', {
                total: result?.total ?? 0,
                visible: result?.items.length ?? 0,
              })}
            </span>
          </div>
        )}
        actions={(
          <MarketplaceCenterHeaderActions
            permissions={permissions}
            onImport={() => {
              if (permissions.canEdit) {
                setIsImportOpen(true);
              }
            }}
            onCreate={() => {
              if (!permissions.canEdit) return;
              setCreateErrorKey(null);
              setIsCreateOpen(true);
            }}
            onSettings={() => {
              if (permissions.canManageRegistry) {
                navigate(ROUTES.marketplace.settings);
              }
            }}
            onRefresh={() => void loadPackages({ singleFlight: false })}
          />
        )}
        className="h-full w-full border-0"
      />
  );

  const filtersRegion = {
    content: ({ collapsed }: { collapsed: boolean }) => collapsed ? null : (
      <div className="h-full overflow-auto p-6">
          <MarketplaceCenterFilters
            searchTerm={searchTerm}
            targetClient={targetClient}
            activeFeatures={activeFeatures}
            category={category}
            categories={result?.categories ?? []}
            onSearchTermChange={value => setQueryState(current => ({
              ...current,
              searchTerm: value,
              page: 1,
            }))}
            onTargetClientChange={value => setQueryState(current => ({
              ...current,
              targetClient: value,
              page: 1,
            }))}
            onActiveFeaturesChange={value => setQueryState(current => ({
              ...current,
              activeFeatures: value,
              page: 1,
            }))}
            onCategoryChange={value => setQueryState(current => ({
              ...current,
              category: value,
              page: 1,
            }))}
            onResetFilters={resetFilters}
          />
      </div>
    ),
    accessibleLabel: t('marketplace.center.accessibility.filtersRegion'),
    preset: 'center-filters' as const,
  };

  const centerMain = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <MarketplaceCenterListToolbar
              viewMode={viewMode}
              visibleCount={visibleItems.length}
              totalCount={result?.total ?? 0}
              currentPage={page}
              totalPages={totalPages}
              onViewModeChange={setViewMode}
            />

            <div className="flex-1 overflow-auto px-6 py-6">
              {isLoading ? (
                <LoadingSpinner text={t('marketplace.center.list.loading')} />
              ) : error ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                  <p>{t('marketplace.center.list.error.title')}</p>
                  <Button
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => void loadPackages({ singleFlight: false })}
                  >
                    {t('marketplace.center.list.error.retry')}
                  </Button>
                </div>
              ) : result && visibleItems.length > 0 ? (
                <div className="space-y-6">
                  {viewMode === 'grid' ? (
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                      {visibleItems.map(item => (
                        <MarketplacePackageCard
                          key={`${item.targetClient}:${item.packageId}`}
                          item={item}
                          onOpenDetail={openDetail}
                          onInstall={permissions.canInstall ? item => openPackageAction('install', item) : undefined}
                          onEdit={permissions.canEdit ? openEdit : undefined}
                          onDelete={permissions.canDelete ? item => openPackageAction('delete', item) : undefined}
                          onExport={permissions.canExport ? item => openPackageAction('export', item) : undefined}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {visibleItems.map(item => (
                        <MarketplacePackageListRow
                          key={`${item.targetClient}:${item.packageId}`}
                          item={item}
                          onOpenDetail={openDetail}
                          onInstall={permissions.canInstall ? item => openPackageAction('install', item) : undefined}
                          onEdit={permissions.canEdit ? openEdit : undefined}
                          onDelete={permissions.canDelete ? item => openPackageAction('delete', item) : undefined}
                          onExport={permissions.canExport ? item => openPackageAction('export', item) : undefined}
                        />
                      ))}
                    </div>
                  )}

                  <MarketplaceCenterPagination
                    page={page}
                    totalPages={totalPages}
                    pageSize={pageSize}
                    onPageChange={value => setQueryState(current => ({
                      ...current,
                      page: value,
                    }))}
                    onPageSizeChange={size => {
                      setQueryState(current => ({
                        ...current,
                        page: 1,
                        pageSize: size,
                      }));
                    }}
                  />
                </div>
              ) : (
                <EmptyState
                  icon={Search}
                  title={t('marketplace.center.list.empty.title')}
                  action={(
                    <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={resetFilters}>
                      {t('marketplace.center.list.empty.reset')}
                    </Button>
                  )}
                />
              )}
            </div>
    </div>
  );

  const dialogs = (
    <>
      {permissions.canEdit ? (
        <CreatePackageDialog
          open={isCreateOpen}
          errorKey={createErrorKey}
          isSubmitting={isCreatingPackage}
          onOpenChange={(open) => {
            setIsCreateOpen(open);
            if (!open) setCreateErrorKey(null);
          }}
          onSubmit={submitCreatePackage}
        />
      ) : null}
      {permissions.canEdit ? (
        <MarketplaceImportDialog
          open={isImportOpen}
          onOpenChange={setIsImportOpen}
          onImported={revealImportedPackages}
        />
      ) : null}
      <MarketplacePackageActionDialog
        action={visiblePackageAction}
        onOpenChange={open => {
          if (!open) setPackageAction(null);
        }}
        onDeleted={() => void loadPackages({ singleFlight: false })}
      />
    </>
  );

  return (
    <MarketplaceShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        header: centerHeader,
        navigator: filtersRegion,
        main: {
          accessibleLabel: t('marketplace.center.header.title'),
          content: (
            <>
              {centerMain}
              {dialogs}
            </>
          ),
        },
      }}
    />
  );
};
