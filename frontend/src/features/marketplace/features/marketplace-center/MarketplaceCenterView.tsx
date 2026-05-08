import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Download, FileArchive, GitBranch, Info, LayoutGrid, List, Plus, RefreshCcw, Search, Settings, Terminal, Trash2, Upload } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { ColumnsLayout } from '@/shared/components/layout/ColumnsLayout';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { fetchWorkspaceList } from '@/features/workspace/services/workspaceRuntimeApi';
import { ApiError } from '@/shared/api/apiClient';
import type {
  MarketplaceFeatureKey,
  MarketplaceCliPreflight,
  MarketplaceImportCandidate,
  MarketplaceImportProvider,
  MarketplaceImportResult,
  MarketplaceInstallResult,
  MarketplaceListQuery,
  MarketplaceListResult,
  MarketplacePackageSummary,
  MarketplaceProvider,
  MarketplaceRegistrySettings,
} from '@/shared/types/marketplace';
import { resolveMarketplacePermissions } from '../../permissions';
import {
  deletePackage,
  exportPackage,
  getInstallPreflight,
  getRegistrySettings,
  importCandidates,
  initializeRegistry,
  installPackage,
  listPackages,
  scanImportSource,
  uploadImportSource,
} from '../../api/marketplaceApi';
import { MarketplacePackageCard } from './components/MarketplacePackageCard';
import { FALLBACK_WORKSPACE_ID, MARKETPLACE_STORAGE_USER_SCOPE } from '../../constants';
import { MarketplaceInstallOutput } from '../../components/MarketplaceInstallOutput';
import {
  loadMarketplaceCenterFilters,
  loadMarketplaceCenterViewMode,
  resolveMarketplaceInstallWorkspaceId,
  saveMarketplaceCenterFilters,
  saveMarketplaceCenterViewMode,
  saveMarketplaceInstallWorkspaceId,
  type MarketplaceCenterViewMode,
  type MarketplaceWorkspaceOption,
} from '../../utils/marketplaceLocalStorage';

const PAGE_SIZE_OPTIONS = [6, 12, 24];
const MARKETPLACE_FEATURES: MarketplaceFeatureKey[] = ['mcp', 'commands', 'hooks', 'agentsMd', 'agents', 'outputStyle', 'skills'];
const IMPORT_SCAN_HIDDEN_VALIDATION_CODES = new Set(['marketplace.validation.metadata_conflict']);
const IMPORT_PROVIDERS: MarketplaceImportProvider[] = ['all', 'claude-code', 'codex', 'gemini'];

const getMarketplaceInstallCommandName = (
  provider: MarketplaceProvider,
  t: (key: string) => string,
) => t(`marketplace.install.commandNames.${provider}`);

const getMarketplaceErrorCode = (err: unknown, fallback: string) => (
  err instanceof ApiError
    ? (err.errorCode ?? err.message ?? fallback)
    : err instanceof Error
      ? err.message
      : typeof err === 'string'
        ? err
        : fallback
);

const translateMarketplaceMessage = (
  t: (key: string, params?: Record<string, unknown>) => string,
  value: string,
  params?: Record<string, unknown>,
) => {
  if (value.startsWith('marketplace.')) {
    return t(value, params);
  }
  return value;
};

export const MarketplaceCenterView: React.FC = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const initialFilters = React.useMemo(
    () => loadMarketplaceCenterFilters(MARKETPLACE_STORAGE_USER_SCOPE),
    [],
  );
  const [searchTerm, setSearchTerm] = React.useState('');
  const [provider, setProvider] = React.useState<MarketplaceProvider | 'all'>(initialFilters.provider);
  const [activeFeatures, setActiveFeatures] = React.useState<Set<MarketplaceFeatureKey>>(
    () => new Set(initialFilters.features),
  );
  const [category, setCategory] = React.useState(initialFilters.category);
  const [viewMode, setViewMode] = React.useState<MarketplaceCenterViewMode>(
    () => loadMarketplaceCenterViewMode(MARKETPLACE_STORAGE_USER_SCOPE),
  );
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(12);
  const [result, setResult] = React.useState<MarketplaceListResult | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [registrySettings, setRegistrySettings] = React.useState<MarketplaceRegistrySettings | null>(null);
  const [isImportOpen, setIsImportOpen] = React.useState(false);
  const [packageAction, setPackageAction] = React.useState<{
    type: 'install' | 'export' | 'delete';
    item: MarketplacePackageSummary;
  } | null>(null);
  const permissions = React.useMemo(() => resolveMarketplacePermissions(), []);

  React.useEffect(() => {
    let isActive = true;
    void getRegistrySettings().then(settings => {
      if (isActive) setRegistrySettings(settings);
    });
    return () => { isActive = false; };
  }, []);

  const loadPackages = React.useCallback(async (overrides: Partial<MarketplaceListQuery> = {}) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listPackages({
        q: overrides.q ?? searchTerm,
        provider: overrides.provider ?? provider,
        category: overrides.category ?? category,
        features: overrides.features ?? Array.from(activeFeatures),
        sort: 'updatedAt',
        direction: 'desc',
        page: overrides.page ?? page,
        pageSize: overrides.pageSize ?? pageSize,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  }, [activeFeatures, category, page, pageSize, provider, searchTerm]);

  React.useEffect(() => {
    void loadPackages();
  }, [loadPackages]);

  React.useEffect(() => {
    saveMarketplaceCenterFilters(MARKETPLACE_STORAGE_USER_SCOPE, {
      provider,
      category,
      features: Array.from(activeFeatures),
    });
  }, [activeFeatures, category, provider]);

  React.useEffect(() => {
    saveMarketplaceCenterViewMode(MARKETPLACE_STORAGE_USER_SCOPE, viewMode);
  }, [viewMode]);

  React.useEffect(() => {
    setPage(1);
  }, [activeFeatures, category, provider, searchTerm]);

  const openDetail = (item: MarketplacePackageSummary) => {
    navigate(ROUTES.MARKETPLACE_PACKAGE_DETAIL(item.provider, item.packageId));
  };

  const openEdit = (item: MarketplacePackageSummary) => {
    navigate(ROUTES.MARKETPLACE_PACKAGE_EDIT(item.provider, item.packageId));
  };

  const completeRegistrySetup = async () => {
    try {
      await initializeRegistry();
      const settings = await getRegistrySettings();
      setRegistrySettings(settings);
      await loadPackages();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const resetFilters = () => {
    setSearchTerm('');
    setProvider('all');
    setActiveFeatures(new Set());
    setCategory('all');
    setPage(1);
  };

  const revealImportedPackages = (importResult: MarketplaceImportResult) => {
    if (importResult.imported.length === 0) {
      void loadPackages();
      return;
    }
    const importedProviders = new Set(importResult.imported.map(item => item.provider));
    const nextProvider = importedProviders.size === 1 ? importResult.imported[0].provider : 'all';
    setSearchTerm('');
    setProvider(nextProvider);
    setActiveFeatures(new Set());
    setCategory('all');
    setPage(1);
    void loadPackages({
      q: '',
      provider: nextProvider,
      category: 'all',
      features: [],
      page: 1,
    });
  };

  const totalPages = result?.totalPages ?? 1;

  if (registrySettings?.status === 'uninitialized') {
    return (
      <MarketplaceFirstRunOnboarding
        rootPath={registrySettings.rootPath}
        onInitialize={completeRegistrySetup}
        onClone={() => navigate(ROUTES.MARKETPLACE_SETTINGS)}
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('marketplace.center.header.title')}
        icon={LayoutGrid}
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
          <div className="flex items-center gap-2">
            {permissions.canImport ? (
              <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => setIsImportOpen(true)}>
                <Upload className="h-3.5 w-3.5 mr-1" />
                {t('marketplace.center.actions.import')}
              </Button>
            ) : null}
            {permissions.canEdit ? (
              <Button size="sm" className="h-7 px-2 text-xs" onClick={() => navigate(`${ROUTES.MARKETPLACE_PACKAGES}/new`)}>
                <Plus className="h-3.5 w-3.5 mr-1" />
                {t('marketplace.center.actions.create')}
              </Button>
            ) : null}
            {permissions.canManageRegistry ? (
              <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => navigate(ROUTES.MARKETPLACE_SETTINGS)}>
                <Settings className="h-3.5 w-3.5 mr-1" />
                {t('marketplace.center.actions.settings')}
              </Button>
            ) : null}
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={loadPackages}>
              <RefreshCcw className="h-3.5 w-3.5 mr-1" />
              {t('marketplace.center.actions.refresh')}
            </Button>
          </div>
        )}
      />

      <ColumnsLayout className="h-[calc(100%-3rem)] min-h-0">
        <ColumnsLayout.PrimarySidebar
          className="hidden bg-muted/20 p-6 border-r border-border lg:block"
          width={280}
          minWidth={220}
          maxWidth={420}
        >
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm font-semibold text-foreground">
                {t('marketplace.center.filters.searchLabel')}
              </p>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-10"
                  value={searchTerm}
                  placeholder={t('marketplace.center.filters.searchPlaceholder')}
                  onChange={event => setSearchTerm(event.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">{t('marketplace.center.filters.cliLabel')}</p>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={resetFilters}>
                  {t('marketplace.center.filters.clear')}
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {(['all', 'claude-code', 'codex', 'gemini'] as const).map(value => (
                  <Button
                    key={value}
                    variant={provider === value ? 'default' : 'outline'}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setProvider(value)}
                  >
                    {value === 'all'
                      ? t('marketplace.center.filters.allProviders')
                      : t(`marketplace.providers.${value}`)}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">
                  {t('marketplace.center.filters.featureLabel')}
                </p>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={resetFilters}>
                  {t('marketplace.center.filters.clear')}
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant={activeFeatures.size === 0 ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setActiveFeatures(new Set())}
                >
                  {t('marketplace.center.filters.allFeatures')}
                </Button>
                {MARKETPLACE_FEATURES.map(feature => {
                  const isActive = activeFeatures.has(feature);
                  return (
                    <Button
                      key={feature}
                      variant={isActive ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => {
                        const next = new Set(activeFeatures);
                        if (next.has(feature)) {
                          next.delete(feature);
                        } else {
                          next.add(feature);
                        }
                        setActiveFeatures(next);
                      }}
                    >
                      {t(`marketplace.features.${feature}`)}
                    </Button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-foreground">
                {t('marketplace.center.filters.categoryLabel')}
              </p>
              <div className="flex flex-col gap-2">
                <Button
                  variant={category === 'all' ? 'default' : 'outline'}
                  size="sm"
                  className="justify-start h-7 px-2 text-xs"
                  onClick={() => setCategory('all')}
                >
                  {t('marketplace.center.filters.allCategories')}
                </Button>
                {(result?.categories ?? []).map(item => (
                  <Button
                    key={item}
                    variant={category === item ? 'default' : 'outline'}
                    size="sm"
                    className="justify-start h-7 px-2 text-xs"
                    onClick={() => setCategory(item)}
                  >
                    {item}
                  </Button>
                ))}
              </div>
            </div>
          </div>

        </ColumnsLayout.PrimarySidebar>

        <ColumnsLayout.Content className="overflow-hidden" scrollable={false}>
          <div className="flex h-full flex-col">
            <div className="flex h-10 items-center border-b border-border bg-muted/10 px-4">
              <div className="flex flex-wrap items-center gap-3 w-full">
                <div className="flex items-center gap-2">
                  <LayoutGrid className="h-4 w-4 text-primary" />
                  <p className="text-sm font-semibold text-foreground">
                    {t('marketplace.center.list.title')}
                  </p>
                </div>

                <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="mr-2 flex items-center rounded-md border border-border bg-background p-0.5">
                    <Button
                      variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      aria-label={t('marketplace.center.viewModes.grid')}
                      onClick={() => setViewMode('grid')}
                    >
                      <LayoutGrid className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      aria-label={t('marketplace.center.viewModes.list')}
                      onClick={() => setViewMode('list')}
                    >
                      <List className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <span>
                    {t('marketplace.center.list.stats.visible', {
                      visible: result?.items.length ?? 0,
                      total: result?.total ?? 0,
                    })}
                  </span>
                  <span>
                    {t('marketplace.center.list.stats.page', {
                      current: page,
                      total: totalPages,
                    })}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-auto px-6 py-6">
              {isLoading ? (
                <LoadingSpinner text={t('marketplace.center.list.loading')} />
              ) : error ? (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                  <p>{t('marketplace.center.list.error.title')}</p>
                  <Button size="sm" className="h-7 px-2 text-xs" onClick={loadPackages}>
                    {t('marketplace.center.list.error.retry')}
                  </Button>
                </div>
              ) : result && result.items.length > 0 ? (
                <div className="space-y-6">
                  {viewMode === 'grid' ? (
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                      {result.items.map(item => (
                        <MarketplacePackageCard
                          key={`${item.provider}:${item.packageId}`}
                          item={item}
                          onOpenDetail={openDetail}
                          onInstall={permissions.canInstall ? item => setPackageAction({ type: 'install', item }) : undefined}
                          onEdit={permissions.canEdit ? openEdit : undefined}
                          onDelete={permissions.canDelete ? item => setPackageAction({ type: 'delete', item }) : undefined}
                          onExport={permissions.canExport ? item => setPackageAction({ type: 'export', item }) : undefined}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {result.items.map(item => (
                        <MarketplacePackageListRow
                          key={`${item.provider}:${item.packageId}`}
                          item={item}
                          onOpenDetail={openDetail}
                          onInstall={permissions.canInstall ? item => setPackageAction({ type: 'install', item }) : undefined}
                          onEdit={permissions.canEdit ? openEdit : undefined}
                          onDelete={permissions.canDelete ? item => setPackageAction({ type: 'delete', item }) : undefined}
                          onExport={permissions.canExport ? item => setPackageAction({ type: 'export', item }) : undefined}
                        />
                      ))}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4 text-sm">
                    <div className="flex items-center gap-3">
                      <span>
                        {t('marketplace.center.pagination.pageCount', {
                          current: page,
                          total: totalPages,
                        })}
                      </span>
                      <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))}>
                          {t('marketplace.center.pagination.previous')}
                        </Button>
                        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" disabled={page >= totalPages} onClick={() => setPage(value => Math.min(totalPages, value + 1))}>
                          {t('marketplace.center.pagination.next')}
                        </Button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span>{t('marketplace.center.pagination.perPage')}</span>
                      <div className="flex items-center gap-2">
                        {PAGE_SIZE_OPTIONS.map(size => (
                          <Button
                            key={size}
                            variant={pageSize === size ? 'default' : 'outline'}
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => {
                              setPageSize(size);
                              setPage(1);
                            }}
                          >
                            {t('marketplace.center.pagination.perPageOption', { count: size })}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                  <Search className="h-10 w-10" />
                  <p>{t('marketplace.center.list.empty.title')}</p>
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs" onClick={resetFilters}>
                    {t('marketplace.center.list.empty.reset')}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </ColumnsLayout.Content>
      </ColumnsLayout>
      <MarketplaceImportDialog open={isImportOpen} onOpenChange={setIsImportOpen} onImported={revealImportedPackages} />
      <MarketplacePackageActionDialog
        action={packageAction}
        onOpenChange={open => {
          if (!open) setPackageAction(null);
        }}
        onDeleted={loadPackages}
      />
    </div>
  );
};

interface MarketplaceFirstRunOnboardingProps {
  rootPath: string;
  onInitialize: () => void;
  onClone: () => void;
}

const MarketplaceFirstRunOnboarding: React.FC<MarketplaceFirstRunOnboardingProps> = ({
  rootPath,
  onInitialize,
  onClone,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('marketplace.onboarding.title')}
        icon={GitBranch}
        info={<div className="text-xs text-muted-foreground">{t('marketplace.onboarding.description')}</div>}
      />
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-6 rounded-lg border border-border bg-background p-6">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold">{t('marketplace.onboarding.setupTitle')}</h2>
            <p className="text-sm text-muted-foreground">{t('marketplace.onboarding.setupDescription')}</p>
          </div>
          <Alert>
            <CheckCircle2 className="h-4 w-4" />
            <AlertDescription>
              {t('marketplace.onboarding.rootPath', { path: rootPath })}
            </AlertDescription>
          </Alert>
          <div className="grid gap-3 md:grid-cols-2">
            <Button className="h-auto justify-start p-4 text-left" onClick={onInitialize}>
              <div>
                <div className="font-medium">{t('marketplace.onboarding.actions.initialize')}</div>
                <div className="mt-1 text-xs opacity-80">{t('marketplace.onboarding.actions.initializeDescription')}</div>
              </div>
            </Button>
            <Button variant="outline" className="h-auto justify-start p-4 text-left" onClick={onClone}>
              <div>
                <div className="font-medium">{t('marketplace.onboarding.actions.clone')}</div>
                <div className="mt-1 text-xs text-muted-foreground">{t('marketplace.onboarding.actions.cloneDescription')}</div>
              </div>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

interface MarketplaceImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (result: MarketplaceImportResult) => void;
}

const MarketplaceImportDialog: React.FC<MarketplaceImportDialogProps> = ({ open, onOpenChange, onImported }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [provider, setProvider] = React.useState<MarketplaceImportProvider>('all');
  const [sourceKind, setSourceKind] = React.useState<'git' | 'local'>('git');
  const [source, setSource] = React.useState('');
  const [localFile, setLocalFile] = React.useState<File | null>(null);
  const [uploadedLocalSource, setUploadedLocalSource] = React.useState('');
  const localFileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [isScanning, setIsScanning] = React.useState(false);
  const [isImporting, setIsImporting] = React.useState(false);
  const [candidates, setCandidates] = React.useState<MarketplaceImportCandidate[]>([]);
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  const [resultStatus, setResultStatus] = React.useState<'idle' | 'scanned'>('idle');
  const [scanErrorKey, setScanErrorKey] = React.useState<string | null>(null);
  const scanBlocked = sourceKind === 'git'
    ? !source.trim()
    : !localFile && !uploadedLocalSource;

  React.useEffect(() => {
    if (!open) {
      setCandidates([]);
      setSelectedIds(new Set());
      setResultStatus('idle');
      setScanErrorKey(null);
      return;
    }
  }, [open]);

  const resetScanState = React.useCallback(() => {
    setCandidates([]);
    setSelectedIds(new Set());
    setResultStatus('idle');
    setScanErrorKey(null);
  }, []);

  const scan = async () => {
    setIsScanning(true);
    setScanErrorKey(null);
    try {
      const importSource = sourceKind === 'local'
        ? (localFile
          ? (await uploadImportSource(provider === 'all' ? 'claude-code' : provider, localFile)).source
          : { provider, sourceKind, source: uploadedLocalSource })
        : {
            provider,
            sourceKind,
            source: source.trim(),
          };
      if (sourceKind === 'local') {
        setUploadedLocalSource(importSource.source);
      }
      const scanned = await scanImportSource(importSource);
      setCandidates(scanned);
      setSelectedIds(new Set());
      setResultStatus('scanned');
    } catch (err) {
      setScanErrorKey(getMarketplaceErrorCode(err, 'marketplace.import.validation.cloneFailed'));
    } finally {
      setIsScanning(false);
    }
  };

  const runImport = async () => {
    setIsImporting(true);
    setScanErrorKey(null);
    try {
      const selected = candidates.filter(candidate => selectedIds.has(candidate.id));
      const result = await importCandidates(selected);
      const summary = {
        imported: result.imported.length,
        skipped: result.skipped.length,
        failed: result.failed.length,
        duplicates: selected.filter(candidate => candidate.duplicate).length,
        warnings: result.warnings.length,
      };
      const failedDetails = result.failed.map(candidate => t('marketplace.import.result.failedDetailItem', {
        displayName: candidate.displayName,
        packageId: candidate.packageId,
        message: translateMarketplaceMessage(t, candidate.errorCode),
      }));
      toast({
        title: t('marketplace.import.result.summary', summary),
        description: failedDetails.length
          ? t('marketplace.import.result.failedDetailsDescription', { details: failedDetails.join('; ') })
          : undefined,
        variant: summary.failed > 0 ? 'destructive' : summary.warnings > 0 ? 'info' : 'success',
      });
      onImported(result);
      onOpenChange(false);
    } catch (err) {
      setScanErrorKey(getMarketplaceErrorCode(err, 'marketplace.import.validation.cloneFailed'));
      setResultStatus('scanned');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,760px)] max-w-3xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{t('marketplace.import.title')}</DialogTitle>
          <DialogDescription>{t('marketplace.import.description')}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>{t('marketplace.import.fields.provider')}</Label>
              <Select value={provider} onValueChange={value => {
                setProvider(value as MarketplaceImportProvider);
                resetScanState();
              }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {IMPORT_PROVIDERS.map(value => (
                    <SelectItem key={value} value={value}>
                      {value === 'all'
                        ? t('marketplace.import.providers.all')
                        : t(`marketplace.providers.${value}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{t('marketplace.import.fields.sourceKind')}</Label>
              <Select value={sourceKind} onValueChange={value => {
                setSourceKind(value as 'git' | 'local');
                resetScanState();
              }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="git">{t('marketplace.import.sourceKinds.git')}</SelectItem>
                  <SelectItem value="local">{t('marketplace.import.sourceKinds.local')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {sourceKind === 'git' ? (
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
              <div className="space-y-2">
                <Label htmlFor="marketplace-import-source">{t('marketplace.import.fields.source')}</Label>
                <Input id="marketplace-import-source" value={source} onChange={event => {
                  setSource(event.target.value);
                  resetScanState();
                }} />
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full md:w-auto"
                onClick={scan}
                disabled={isScanning || scanBlocked}
              >
                {isScanning ? <LoadingSpinner size="sm" className="mr-1.5" /> : <Search className="mr-1.5 h-3.5 w-3.5" />}
                {t('marketplace.import.actions.scan')}
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="marketplace-import-file">{t('marketplace.import.fields.localFile')}</Label>
              <div className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3">
                <input
                  id="marketplace-import-file"
                  ref={localFileInputRef}
                  className="sr-only"
                  type="file"
                  accept=".zip,application/zip"
                  onChange={event => {
                    const file = event.target.files?.[0] ?? null;
                    setLocalFile(file);
                    setUploadedLocalSource('');
                    resetScanState();
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 px-3 text-xs"
                  onClick={() => localFileInputRef.current?.click()}
                >
                  <FileArchive className="mr-1.5 h-3.5 w-3.5" />
                  {t('marketplace.import.actions.chooseFile')}
                </Button>
                <span className="min-w-0 truncate text-sm text-muted-foreground">
                  {localFile?.name ?? t('marketplace.import.localFile.empty')}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="ml-auto h-8 px-3 text-xs"
                  onClick={scan}
                  disabled={isScanning || scanBlocked}
                >
                  {isScanning ? <LoadingSpinner size="sm" className="mr-1.5" /> : <Search className="mr-1.5 h-3.5 w-3.5" />}
                  {t('marketplace.import.actions.scan')}
                </Button>
              </div>
            </div>
          )}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">{t('marketplace.import.candidates.title')}</h3>
              <div className="flex flex-wrap items-center gap-2">
                {candidates.length > 0 ? (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => setSelectedIds(new Set(candidates.map(candidate => candidate.id)))}
                      disabled={selectedIds.size === candidates.length}
                    >
                      {t('marketplace.import.actions.selectAll')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => setSelectedIds(new Set())}
                      disabled={selectedIds.size === 0}
                    >
                      {t('marketplace.import.actions.clearSelection')}
                    </Button>
                  </>
                ) : null}
              </div>
            </div>
            <div className="max-h-[min(34vh,320px)] space-y-2 overflow-y-auto rounded-md border border-border p-3">
              {candidates.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('marketplace.import.candidates.empty')}</p>
              ) : candidates.map(candidate => {
                const visibleValidationResults = candidate.validationResults.filter(
                  result => !IMPORT_SCAN_HIDDEN_VALIDATION_CODES.has(result.code),
                );
                return (
                  <div key={candidate.id} className="flex items-start gap-3 rounded-md border border-border px-3 py-2">
                    <Checkbox
                      checked={selectedIds.has(candidate.id)}
                      onCheckedChange={checked => {
                        const next = new Set(selectedIds);
                        if (checked) next.add(candidate.id);
                        else next.delete(candidate.id);
                        setSelectedIds(next);
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{candidate.displayName}</span>
                        <span className="font-mono text-xs text-muted-foreground">{candidate.packageId}</span>
                        <Badge variant="outline">{t(`marketplace.providers.${candidate.provider}`)}</Badge>
                        <Badge variant={candidate.variantStatus === 'invalid' || candidate.variantStatus === 'unrelated-duplicate' ? 'destructive' : candidate.variantStatus === 'duplicate-variant' ? 'secondary' : 'outline'}>
                          {t(`marketplace.import.variantStatuses.${candidate.variantStatus}`)}
                        </Badge>
                        {candidate.duplicate ? (
                          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                            {t('marketplace.import.candidates.duplicate')}
                          </span>
                        ) : null}
                      </div>
                      {candidate.familyDisplayName || candidate.sourceIdentity || candidate.variants.length > 0 ? (
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          {candidate.familyDisplayName ? (
                            <span>{t('marketplace.import.candidates.family', { family: candidate.familyDisplayName })}</span>
                          ) : null}
                          {candidate.sourceIdentity ? (
                            <span className="font-mono">{candidate.sourceIdentity}</span>
                          ) : null}
                          {candidate.variants.map(variant => (
                            <Badge key={`${variant.provider}:${variant.packageId}`} variant="secondary" className="text-[11px]">
                              {t(`marketplace.providers.${variant.provider}`)}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-1 font-mono text-xs text-muted-foreground">{candidate.sourcePath}</div>
                      {visibleValidationResults.length > 0 ? (
                        <div className="mt-2 space-y-1">
                          {visibleValidationResults.map(result => (
                            <div key={`${candidate.id}-${result.code}`} className="text-xs text-amber-700">
                              {t(result.messageKey)}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    {candidate.duplicate ? (
                      <div className="w-48 space-y-2">
                        <Select
                          value={candidate.duplicateAction}
                          onValueChange={value => setCandidates(items => items.map(item => (
                            item.id === candidate.id ? { ...item, duplicateAction: value as MarketplaceImportCandidate['duplicateAction'] } : item
                          )))}
                        >
                          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="skip">{t('marketplace.import.duplicateActions.skip')}</SelectItem>
                            <SelectItem value="overwrite">{t('marketplace.import.duplicateActions.overwrite')}</SelectItem>
                            <SelectItem value="import-as-new">{t('marketplace.import.duplicateActions.importAsNew')}</SelectItem>
                          </SelectContent>
                        </Select>
                        {candidate.duplicateAction === 'import-as-new' ? (
                          <Input
                            value={candidate.newPackageId ?? ''}
                            aria-label={t('marketplace.import.fields.newPackageId')}
                            placeholder={t('marketplace.import.fields.newPackageIdPlaceholder')}
                            onChange={event => setCandidates(items => items.map(item => (
                              item.id === candidate.id ? { ...item, newPackageId: event.target.value } : item
                            )))}
                          />
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        {scanErrorKey ? (
          <Alert variant="destructive" className="shrink-0">
            <Info className="h-4 w-4" />
            <AlertDescription>{translateMarketplaceMessage(t, scanErrorKey)}</AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</Button>
          <Button onClick={runImport} disabled={selectedIds.size === 0 || isImporting || resultStatus === 'idle'}>
            {isImporting ? <LoadingSpinner size="sm" className="mr-1.5" /> : null}
            {t('marketplace.import.actions.import')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

interface MarketplacePackageListRowProps {
  item: MarketplacePackageSummary;
  onOpenDetail: (item: MarketplacePackageSummary) => void;
  onInstall?: (item: MarketplacePackageSummary) => void;
  onEdit?: (item: MarketplacePackageSummary) => void;
  onDelete?: (item: MarketplacePackageSummary) => void;
  onExport?: (item: MarketplacePackageSummary) => void;
}

const MarketplacePackageListRow: React.FC<MarketplacePackageListRowProps> = ({
  item,
  onOpenDetail,
  onInstall,
  onEdit,
  onDelete,
  onExport,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-md border border-border bg-card p-4">
      <button className="min-w-0 flex-1 text-left" onClick={() => onOpenDetail(item)}>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-foreground hover:text-primary">{item.displayName}</h3>
          <Badge variant="outline">{t(`marketplace.providers.${item.provider}`)}</Badge>
          {item.variants.length > 1 ? (
            item.variants.map(variant => (
              <Badge key={`${variant.provider}:${variant.packageId}`} variant="secondary">
                {t(`marketplace.providers.${variant.provider}`)}
              </Badge>
            ))
          ) : null}
          {item.category ? <Badge variant="secondary">{item.category}</Badge> : null}
        </div>
        <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{item.packageId}</p>
        <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{item.description}</p>
      </button>

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" className="h-7 px-2 text-xs" disabled={!onInstall} onClick={() => onInstall?.(item)}>
          <Terminal className="mr-1.5 h-3.5 w-3.5" />
          {t('marketplace.center.card.actions.install')}
        </Button>
        <Button size="sm" variant="outline" className="h-7 px-2 text-xs" disabled={!onExport} onClick={() => onExport?.(item)}>
          <Download className="mr-1.5 h-3.5 w-3.5" />
          {t('marketplace.center.card.actions.export')}
        </Button>
        {onEdit ? (
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => onEdit(item)}>
            {t('marketplace.center.card.actions.edit')}
          </Button>
        ) : null}
        {onDelete ? (
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-destructive hover:text-destructive" onClick={() => onDelete(item)}>
            {t('marketplace.center.card.actions.delete')}
          </Button>
        ) : null}
      </div>
    </div>
  );
};

interface MarketplacePackageActionDialogProps {
  action: { type: 'install' | 'export' | 'delete'; item: MarketplacePackageSummary } | null;
  onOpenChange: (open: boolean) => void;
  onDeleted: () => void;
}

const MarketplacePackageActionDialog: React.FC<MarketplacePackageActionDialogProps> = ({
  action,
  onOpenChange,
  onDeleted,
}) => {
  const { t } = useI18n();
  const [workspaceId, setWorkspaceId] = React.useState(FALLBACK_WORKSPACE_ID);
  const [workspaceOptions, setWorkspaceOptions] = React.useState<MarketplaceWorkspaceOption[]>([]);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = React.useState(false);
  const [confirmText, setConfirmText] = React.useState('');
  const [status, setStatus] = React.useState<'idle' | 'running' | 'success' | 'failed' | MarketplaceInstallResult['status']>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const [installResult, setInstallResult] = React.useState<MarketplaceInstallResult | null>(null);
  const [preflight, setPreflight] = React.useState<MarketplaceCliPreflight | null>(null);
  const [isLoadingPreflight, setIsLoadingPreflight] = React.useState(false);

  React.useEffect(() => {
    if (action) {
      if (action.type !== 'install') {
        setWorkspaceId(FALLBACK_WORKSPACE_ID);
      }
      setConfirmText('');
      setStatus('idle');
      setErrorCode(null);
      setInstallResult(null);
      setPreflight(null);
    }
  }, [action]);

  React.useEffect(() => {
    if (action?.type !== 'install') return;
    let isActive = true;
    setIsLoadingWorkspaces(true);
    void fetchWorkspaceList()
      .then(result => {
        if (!isActive) return;
        const options = result.items.map(workspace => ({
          id: workspace.id,
          label: workspace.name || workspace.id,
        }));
        setWorkspaceOptions(options);
        setWorkspaceId(resolveMarketplaceInstallWorkspaceId(
          options,
          FALLBACK_WORKSPACE_ID,
          MARKETPLACE_STORAGE_USER_SCOPE,
        ));
      })
      .catch(() => {
        if (!isActive) return;
        setWorkspaceOptions([]);
        setWorkspaceId(resolveMarketplaceInstallWorkspaceId(
          [],
          FALLBACK_WORKSPACE_ID,
          MARKETPLACE_STORAGE_USER_SCOPE,
        ));
      })
      .finally(() => {
        if (isActive) setIsLoadingWorkspaces(false);
      });
    return () => { isActive = false; };
  }, [action?.type]);

  React.useEffect(() => {
    if (action?.type !== 'install' || !workspaceId) return;
    let isActive = true;
    setIsLoadingPreflight(true);
    void getInstallPreflight(action.item.provider, workspaceId)
      .then(result => {
        if (isActive) setPreflight(result);
      })
      .catch(err => {
        if (!isActive) return;
        setPreflight({
          provider: action.item.provider,
          available: false,
          capabilities: {
            supportsUserScope: false,
            supportsMarketplaceAdd: false,
            supportsExtensionInstall: false,
          },
          errorCode: err instanceof Error ? err.message : 'marketplace.install.preflight.failed',
        });
      })
      .finally(() => {
        if (isActive) setIsLoadingPreflight(false);
      });
    return () => { isActive = false; };
  }, [action?.item.provider, action?.type, workspaceId]);

  if (!action) return null;

  const { item } = action;
  const commandName = getMarketplaceInstallCommandName(item.provider, t);
  const titleKey = {
    install: 'marketplace.install.title',
    export: 'marketplace.export.title',
    delete: 'marketplace.delete.title',
  }[action.type];
  const descriptionKey = {
    install: 'marketplace.install.description',
    export: 'marketplace.export.description',
    delete: 'marketplace.delete.description',
  }[action.type];

  const runAction = async () => {
    setStatus('running');
    setErrorCode(null);
    try {
      if (action.type === 'install') {
        saveMarketplaceInstallWorkspaceId(MARKETPLACE_STORAGE_USER_SCOPE, workspaceId);
        const result = await installPackage({
          provider: item.provider,
          packageId: item.packageId,
          revision: item.revision,
          workspaceId,
        });
        setStatus(result.status);
        setErrorCode(result.errorCode ?? null);
        setInstallResult(result);
        return;
      }
      if (action.type === 'export') {
        await exportPackage({ provider: item.provider, packageId: item.packageId, revision: item.revision });
        setStatus('success');
        return;
      }
      const result = await deletePackage({ provider: item.provider, packageId: item.packageId, revision: item.revision });
      if (result.deleted) {
        setStatus('success');
        onDeleted();
        return;
      }
      setStatus('failed');
      setErrorCode(result.errorCode ?? 'marketplace.package.delete_failed');
    } catch (err) {
      setStatus('failed');
      setErrorCode(getMarketplaceErrorCode(err, `marketplace.${action.type}.failed`));
    }
  };

  const isDeleteBlocked = action.type === 'delete' && confirmText !== item.packageId;

  return (
    <AlertDialog open={Boolean(action)} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>{t(titleKey)}</AlertDialogTitle>
          <AlertDialogDescription>{t(descriptionKey, { commandName })}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-4">
          <div className="grid gap-3 rounded-md border border-border p-3 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t('marketplace.install.fields.provider')}</span>
              <span>{t(`marketplace.providers.${item.provider}`)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t('marketplace.install.fields.package')}</span>
              <span className="font-mono">{item.packageId}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t('marketplace.delete.fields.revision')}</span>
              <span className="font-mono">{item.revision}</span>
            </div>
          </div>
          {action.type === 'install' ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="marketplace-center-install-workspace">{t('marketplace.install.fields.workspace')}</Label>
                <Select
                  value={workspaceId}
                  onValueChange={(value) => {
                    setWorkspaceId(value);
                    saveMarketplaceInstallWorkspaceId(MARKETPLACE_STORAGE_USER_SCOPE, value);
                  }}
                  disabled={isLoadingWorkspaces}
                >
                  <SelectTrigger id="marketplace-center-install-workspace">
                    <SelectValue placeholder={t('marketplace.install.workspaceSelect.placeholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {workspaceOptions.length > 0 ? (
                      workspaceOptions.map(workspace => (
                        <SelectItem key={workspace.id} value={workspace.id}>
                          {workspace.label}
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value={FALLBACK_WORKSPACE_ID}>
                        {isLoadingWorkspaces
                          ? t('marketplace.install.workspaceSelect.loading')
                          : t('marketplace.install.workspaceSelect.currentWorkspace')}
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>
          <Alert variant={preflight && !preflight.available ? 'destructive' : 'default'}>
            <Terminal className="h-4 w-4" />
            <AlertDescription>
              {isLoadingPreflight
                ? t('marketplace.install.preflight.loading', { commandName })
                : preflight?.available
                  ? t('marketplace.install.preflight.ready', { commandName, version: preflight.version ?? t('marketplace.install.preflight.unknownVersion') })
                  : t('marketplace.install.preflight.unavailable', { commandName, code: preflight?.errorCode ?? 'unknown' })}
            </AlertDescription>
          </Alert>
            </>
          ) : null}
          {action.type === 'export' ? (
            <Alert>
              <Download className="h-4 w-4" />
              <AlertDescription>{t('marketplace.export.compatibilityNotice')}</AlertDescription>
            </Alert>
          ) : null}
          {action.type === 'delete' ? (
            <>
              <Alert variant="destructive">
                <Trash2 className="h-4 w-4" />
                <AlertDescription>{t('marketplace.delete.warning')}</AlertDescription>
              </Alert>
              <div className="space-y-2">
                <Label htmlFor="marketplace-center-delete-confirm">{t('marketplace.delete.fields.confirm', { id: item.packageId })}</Label>
                <Input id="marketplace-center-delete-confirm" value={confirmText} onChange={event => setConfirmText(event.target.value)} />
              </div>
            </>
          ) : null}
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                {action.type === 'install'
                  ? t('marketplace.install.result.success')
                  : action.type === 'export'
                    ? t('marketplace.export.result.ready')
                    : t('marketplace.delete.result.success')}
              </AlertDescription>
            </Alert>
          ) : null}
          {installResult && status !== 'success' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t(`marketplace.install.result.${installResult.status}`, { commandName, code: errorCode ?? 'unknown' })}
              </AlertDescription>
            </Alert>
          ) : null}
          {status === 'failed' && !installResult ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {errorCode && !errorCode.startsWith('marketplace.')
                  ? errorCode
                  : t(
                    action.type === 'install'
                      ? 'marketplace.install.result.failed'
                      : action.type === 'export'
                        ? 'marketplace.export.result.failed'
                        : 'marketplace.delete.result.failed',
                    { code: errorCode ?? 'unknown' },
                  )}
              </AlertDescription>
            </Alert>
          ) : null}
          {installResult?.stdout || installResult?.stderr ? (
            <MarketplaceInstallOutput result={installResult} />
          ) : null}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</AlertDialogCancel>
          <AlertDialogAction
            className={action.type === 'delete' ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90' : undefined}
            onClick={(event) => {
              event.preventDefault();
              void runAction();
            }}
            disabled={status === 'running' || isDeleteBlocked}
          >
            {status === 'running' ? <LoadingSpinner size="sm" className="mr-1.5" /> : null}
            {action.type === 'install'
              ? t('marketplace.install.actions.install')
              : action.type === 'export'
                ? t('marketplace.export.actions.export')
                : t('marketplace.delete.actions.delete')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default MarketplaceCenterView;
