import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Info, Network } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { getDocumentWorkbenchIcon } from '@/shared/components/document-resource';
import {
  DocumentListSidebar,
  type DocumentListSidebarItem,
} from '@/shared/components/document-workflow';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import type {
  MarketplaceFeatureContentItem,
  MarketplacePackageDetail,
  MarketplaceTargetClient,
} from '@/features/marketplace/model/marketplaceTypes';
import {
  canRunMarketplacePackageAction,
  resolveMarketplacePermissions,
  type MarketplacePackageAction,
} from '../../model/marketplacePermissions';
import {
  getHooks,
  getMarketplaceReadme,
  getPackage,
  getRootDocument,
  listDocuments,
  listMCPServers,
  loadDocument,
} from '../../api/marketplaceApi';
import { MarketplaceInstallDialog } from '../../components/MarketplaceInstallDialog';
import { MarketplaceResourceLoadError } from '../../components/MarketplaceResourceLoadError';
import {
  MarketplaceDeleteDialog,
  MarketplaceExportDialog,
} from './components/MarketplaceDetailActionDialogs';
import {
  MarketplaceMarkdownDetailPanel,
  MarketplaceBasicInfoPanel,
  MarketplaceHooksWorkflow,
  MarketplaceMCPWorkflow,
} from './components/MarketplaceDetailContentPanels';
import { MarketplaceDetailTopTabs } from './components/MarketplaceDetailTopTabs';
import { MarketplaceDetailFilesSection } from './components/MarketplaceDetailFilesSection';
import { MarketplacePackageDetailHeader } from './components/MarketplacePackageDetailHeader';
import { getMarketplaceFeatureLabelKey } from '../../model/marketplaceFeatureLabels';
import {
  getMarketplaceDetailFeatureItems,
  type MarketplaceDetailFeatureItem,
} from './model/marketplaceDetailNavigationModel';
import { useAuth } from '@/features/auth/public';
import { useMarketplaceResourceSession } from '../../model/marketplaceResourceSession';
import { MarketplaceShellAdapter } from '../../components/MarketplaceShellAdapter';

type MarketplaceDetailTab = 'basic-info' | MarketplaceDetailFeatureItem['id'];

const isTargetClient = (value: string | undefined): value is MarketplaceTargetClient =>
  value === 'claude-code' || value === 'codex';

type MarketplaceDetailEmptyResource = 'mcp' | 'commands' | 'subagents' | 'output-styles';

const marketplaceDetailEmptyStateConfig = {
  mcp: {
    icon: Network,
    titleKey: 'marketplace.editor.featureSections.mcp.emptyTitle',
    descriptionKey: 'marketplace.editor.featureSections.mcp.emptyDescription',
  },
  commands: {
    icon: getDocumentWorkbenchIcon('slash-commands'),
    titleKey: 'marketplace.editor.featureSections.commands.emptyTitle',
    descriptionKey: 'marketplace.editor.featureSections.commands.emptyDescription',
  },
  subagents: {
    icon: getDocumentWorkbenchIcon('subagents'),
    titleKey: 'marketplace.editor.featureSections.agents.emptyTitle',
    descriptionKey: 'marketplace.editor.featureSections.agents.emptyDescription',
  },
  'output-styles': {
    icon: getDocumentWorkbenchIcon('output-styles'),
    titleKey: 'marketplace.editor.featureSections.outputStyle.emptyTitle',
    descriptionKey: 'marketplace.editor.featureSections.outputStyle.emptyDescription',
  },
} as const satisfies Record<MarketplaceDetailEmptyResource, {
  icon: React.ComponentType<{ className?: string }>;
  titleKey: string;
  descriptionKey: string;
}>;

const MarketplaceDetailFeatureEmptyState: React.FC<{
  resource: MarketplaceDetailEmptyResource;
}> = ({ resource }) => {
  const { t } = useI18n();
  const config = marketplaceDetailEmptyStateConfig[resource];

  return (
    <EmptyState
      icon={config.icon}
      title={t(config.titleKey)}
      description={t(config.descriptionKey)}
    />
  );
};

const LazyMarkdownPanel: React.FC<{
  title: string;
  targetClient: MarketplaceTargetClient;
  packageId: string;
  resource: 'readme' | 'root';
}> = ({ title, targetClient, packageId, resource }) => {
  const [content, setContent] = React.useState<string | null>(null);
  const [error, setError] = React.useState(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient,
    packageId,
    resourceType: `detail-${resource}`,
  }, '');

  React.useLayoutEffect(() => {
    setContent(null);
    setError(false);
  }, [identityGeneration]);

  const load = React.useCallback(async () => {
    setContent(null);
    setError(false);
    await session.query(
      identityGeneration,
      'detail-markdown',
      () => (
        resource === 'readme'
          ? getMarketplaceReadme(targetClient, packageId)
          : getRootDocument(targetClient, packageId)
      ),
      {
        onSuccess: result => setContent(result.content),
        onError: () => setError(true),
      },
    );
  }, [identityGeneration, packageId, targetClient, resource, session]);
  React.useEffect(() => {
    void load();
  }, [load]);
  if (error) return <MarketplaceResourceLoadError onRetry={() => { void load(); }} />;
  return content === null
    ? <LoadingSpinner className="h-full" />
    : <MarketplaceMarkdownDetailPanel title={title} content={content} />;
};

const LazyHooksPanel: React.FC<{
  targetClient: MarketplaceTargetClient;
  packageId: string;
}> = ({ targetClient, packageId }) => {
  const [hooks, setHooks] = React.useState<MarketplaceFeatureContentItem[] | null>(null);
  const [error, setError] = React.useState(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient,
    packageId,
    resourceType: 'detail-hooks',
  }, '');

  React.useLayoutEffect(() => {
    setHooks(null);
    setError(false);
  }, [identityGeneration]);

  const load = React.useCallback(async () => {
    setHooks(null);
    setError(false);
    await session.query(
      identityGeneration,
      'detail-hooks',
      () => getHooks(targetClient, packageId),
      {
        onSuccess: (resource) => {
          setHooks(resource.sources.flatMap((source) => (
            source.nativeContent && typeof source.nativeContent === 'object'
              ? [{
                id: source.sourceId,
                name: source.path || source.sourceId,
                path: source.path,
                data: { hooks: source.nativeContent },
              }]
              : []
          )));
        },
        onError: () => setError(true),
      },
    );
  }, [identityGeneration, packageId, targetClient, session]);
  React.useEffect(() => {
    void load();
  }, [load]);
  if (error) return <MarketplaceResourceLoadError onRetry={() => { void load(); }} />;
  return hooks === null
    ? <LoadingSpinner className="h-full" />
    : <MarketplaceHooksWorkflow targetClient={targetClient} hooks={hooks} />;
};

const LazyMCPPanel: React.FC<{
  targetClient: MarketplaceTargetClient;
  packageId: string;
}> = ({ targetClient, packageId }) => {
  const [servers, setServers] = React.useState<MarketplaceFeatureContentItem[] | null>(null);
  const [error, setError] = React.useState(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient,
    packageId,
    resourceType: 'detail-mcp',
  }, '');

  React.useLayoutEffect(() => {
    setServers(null);
    setError(false);
  }, [identityGeneration]);

  const load = React.useCallback(async () => {
    setServers(null);
    setError(false);
    await session.query(
      identityGeneration,
      'detail-mcp',
      async () => {
        const summaries = await listMCPServers(targetClient, packageId);
        return summaries;
      },
      {
        onSuccess: (details) => {
          setServers(details.map(detail => ({
            id: JSON.stringify([detail.name, detail.ownerFilePath]),
            name: detail.name,
            path: detail.path,
            data: detail.server,
            ownerFilePath: detail.ownerFilePath,
            baseEntryFingerprint: detail.baseEntryFingerprint,
          })));
        },
        onError: () => setError(true),
      },
    );
  }, [identityGeneration, packageId, targetClient, session]);
  React.useEffect(() => {
    void load();
  }, [load]);
  if (error) return <MarketplaceResourceLoadError onRetry={() => { void load(); }} />;
  if (!servers) return <LoadingSpinner className="h-full" />;
  if (servers.length === 0) return <MarketplaceDetailFeatureEmptyState resource="mcp" />;
  return <MarketplaceMCPWorkflow servers={servers} />;
};

const LazyDocumentsPanel: React.FC<{
  targetClient: MarketplaceTargetClient;
  packageId: string;
  resourceType: 'commands' | 'subagents' | 'output-styles';
  title: string;
}> = ({ targetClient, packageId, resourceType, title }) => {
  const { t } = useI18n();
  const [documents, setDocuments] = React.useState<Awaited<ReturnType<typeof listDocuments>> | null>(null);
  const [selected, setSelected] = React.useState<Awaited<ReturnType<typeof loadDocument>> | null>(null);
  const [listError, setListError] = React.useState(false);
  const [selectedPath, setSelectedPath] = React.useState<string | null>(null);
  const [sidebarSearch, setSidebarSearch] = React.useState('');
  const [contentError, setContentError] = React.useState(false);
  const [isContentLoading, setIsContentLoading] = React.useState(false);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient,
    packageId,
    resourceType: `detail-${resourceType}`,
  }, '');

  React.useLayoutEffect(() => {
    setDocuments(null);
    setSelected(null);
    setListError(false);
    setSelectedPath(null);
    setSidebarSearch('');
    setContentError(false);
    setIsContentLoading(false);
  }, [identityGeneration]);

  const loadList = React.useCallback(async () => {
    setDocuments(null);
    setListError(false);
    await session.query(
      identityGeneration,
      'detail-document-list',
      () => listDocuments(targetClient, packageId, resourceType),
      {
        onSuccess: setDocuments,
        onError: () => setListError(true),
      },
    );
  }, [identityGeneration, packageId, targetClient, resourceType, session]);
  const loadSelected = React.useCallback(async (path: string) => {
    setSelectedPath(path);
    setSelected(null);
    setContentError(false);
    setIsContentLoading(true);
    await session.query(
      identityGeneration,
      'detail-document-content',
      () => loadDocument(targetClient, packageId, resourceType, path),
      {
        onSuccess: setSelected,
        onError: () => setContentError(true),
        onSettled: () => setIsContentLoading(false),
      },
    );
  }, [identityGeneration, packageId, targetClient, resourceType, session]);
  React.useEffect(() => {
    void loadList();
  }, [loadList]);
  const sidebarItems = React.useMemo<DocumentListSidebarItem[]>(
    () => (documents ?? []).map(document => ({
      id: document.path,
      label: document.title,
      description: document.path,
    })),
    [documents],
  );
  const selectDocument = React.useCallback((path: string | null) => {
    if (path) {
      void loadSelected(path);
    }
  }, [loadSelected]);
  if (listError) return <MarketplaceResourceLoadError onRetry={() => { void loadList(); }} />;
  if (!documents) return <LoadingSpinner className="h-full" />;
  if (documents.length === 0) {
    return <MarketplaceDetailFeatureEmptyState resource={resourceType} />;
  }
  return (
    <div className="flex h-full min-h-0 min-w-0">
      <div className="h-full w-80 min-w-0 shrink-0">
        <DocumentListSidebar
          title={title}
          icon={getDocumentWorkbenchIcon(resourceType === 'commands' ? 'slash-commands' : resourceType)}
          items={sidebarItems}
          selectedId={selectedPath}
          onSelect={selectDocument}
          labels={{
            searchPlaceholder: t('marketplace.editor.documents.sidebar.searchPlaceholder'),
            loading: t('marketplace.editor.documents.sidebar.loading'),
            empty: t('marketplace.editor.documents.sidebar.empty'),
            dirty: t('marketplace.editor.documents.sidebar.dirty'),
          }}
          autoSelectFirst={false}
          showSearch
          searchValue={sidebarSearch}
          onSearchChange={setSidebarSearch}
          getDirty={() => false}
        />
      </div>
      <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
        {contentError && selectedPath
          ? <MarketplaceResourceLoadError onRetry={() => { void loadSelected(selectedPath); }} />
          : isContentLoading
            ? <LoadingSpinner className="h-full" />
            : selected
          ? <MarketplaceMarkdownDetailPanel title={selected.title || title} content={selected.content ?? ''} />
          : null}
      </div>
    </div>
  );
};

export interface MarketplaceDetailPageProps {
  navigationSlot?: React.ReactNode;
}

export const MarketplaceDetailPage: React.FC<MarketplaceDetailPageProps> = ({ navigationSlot }) => {
  const { t } = useI18n();
  const { platformRole } = useAuth();
  const navigate = useNavigate();
  const { targetClient, packageId } = useParams();
  const [activeTab, setActiveTab] = React.useState<MarketplaceDetailTab>('basic-info');
  const [detail, setDetail] = React.useState<MarketplacePackageDetail | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [activeAction, setActiveAction] = React.useState<MarketplacePackageAction | null>(null);
  const permissions = React.useMemo(
    () => resolveMarketplacePermissions(platformRole),
    [platformRole],
  );
  const resolvedTargetClient = isTargetClient(targetClient) ? targetClient : null;
  const resolvedPackageId = packageId ?? '';
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient: resolvedTargetClient,
    packageId: resolvedPackageId,
    resourceType: 'detail-package',
  }, '');

  React.useLayoutEffect(() => {
    setActiveTab('basic-info');
    setDetail(null);
    setError(null);
    setIsLoading(true);
    setActiveAction(null);
  }, [identityGeneration]);

  React.useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError(null);
      if (!resolvedTargetClient || !resolvedPackageId) {
        setError('marketplace.errors.packageNotFound');
        setIsLoading(false);
        return;
      }
      await session.query(
        identityGeneration,
        'detail-package',
        () => getPackage(resolvedTargetClient, resolvedPackageId),
        {
          onSuccess: setDetail,
          onError: (loadError) => {
            setError(loadError instanceof Error ? loadError.message : String(loadError));
          },
          onSettled: () => setIsLoading(false),
        },
      );
    };
    void load();
  }, [
    identityGeneration,
    resolvedPackageId,
    resolvedTargetClient,
    session,
  ]);

  const tabs = React.useMemo(
    () => detail ? [
      { id: 'basic-info' as const, name: t('marketplace.detail.tabs.basicInfo'), icon: Info, count: 0 },
      ...getMarketplaceDetailFeatureItems(detail, t),
    ] : [{ id: 'basic-info' as const, name: t('marketplace.detail.tabs.basicInfo'), icon: Info, count: 0 }],
    [
      detail,
      t,
    ],
  );
  const visibleActiveAction = activeAction
    && canRunMarketplacePackageAction(activeAction, permissions)
    ? activeAction
    : null;

  React.useEffect(() => {
    setActiveAction(current => (
      current && (
        (current === 'install' && !permissions.canInstall)
        || (current === 'delete' && !permissions.canDelete)
        || (current === 'export' && !permissions.canExport)
      )
        ? null
        : current
    ));
  }, [
    permissions.canDelete,
    permissions.canExport,
    permissions.canInstall,
  ]);

  const detailMatchesRoute = detail?.targetClient === targetClient && detail.packageId === packageId;

  if (isLoading || (!error && !detailMatchesRoute)) {
    return <MarketplaceShellAdapter navigationSlot={navigationSlot} surface={{
      kind: 'state',
      content: <LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />,
    }} />;
  }

  if (error || !detail) {
    return <MarketplaceShellAdapter navigationSlot={navigationSlot} surface={{
      kind: 'state',
      content: (
        <div className="flex h-full flex-col items-center justify-center gap-4 text-sm text-muted-foreground">
          <p>{t('marketplace.errors.packageNotFound')}</p>
          <Button onClick={() => navigate(ROUTES.marketplace.packages)}>
            {t('marketplace.detail.actions.backToCenter')}
          </Button>
        </div>
      ),
    }} />;
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'basic-info':
        return (
          <MarketplaceBasicInfoPanel
            detail={detail}
            onOpenVariant={(variantTargetClient, variantPackageId, variantPackageFormat) => {
              navigate(ROUTES.marketplace.packageDetail(
                variantTargetClient,
                variantPackageId,
                variantPackageFormat,
              ));
            }}
          />
        );
      case 'readme':
        return (
          <LazyMarkdownPanel
            title={t('marketplace.detail.readme.title')}
            targetClient={detail.targetClient}
            packageId={detail.packageId}
            resource="readme"
          />
        );
      case 'agents-md':
        return (
          <LazyMarkdownPanel
            title={t(getMarketplaceFeatureLabelKey(detail.targetClient, 'agentsMd'))}
            targetClient={detail.targetClient}
            packageId={detail.packageId}
            resource="root"
          />
        );
      case 'hooks':
        return <LazyHooksPanel targetClient={detail.targetClient} packageId={detail.packageId} />;
      case 'mcp':
        return <LazyMCPPanel targetClient={detail.targetClient} packageId={detail.packageId} />;
      case 'agent':
        return (
          <LazyDocumentsPanel
            targetClient={detail.targetClient}
            packageId={detail.packageId}
            resourceType="subagents"
            title={t('marketplace.features.subagents')}
          />
        );
      case 'commands':
        return (
          <LazyDocumentsPanel
            targetClient={detail.targetClient}
            packageId={detail.packageId}
            resourceType="commands"
            title={t('marketplace.features.slashCommands')}
          />
        );
      case 'output-style':
        return (
          <LazyDocumentsPanel
            targetClient={detail.targetClient}
            packageId={detail.packageId}
            resourceType="output-styles"
            title={t('marketplace.features.outputStyle')}
          />
        );
      case 'skills':
        return (
          <MarketplaceDetailFilesSection
            key={`${detail.targetClient}:${detail.packageId}:skills`}
            mode="skills"
            targetClient={detail.targetClient}
            packageId={detail.packageId}
          />
        );
      case 'files':
        return (
          <MarketplaceDetailFilesSection
            key={`${detail.targetClient}:${detail.packageId}:package`}
            mode="package"
            targetClient={detail.targetClient}
            packageId={detail.packageId}
            rootLabel={detail.registryPath}
          />
        );
      default:
        return null;
    }
  };
  const openAction = (action: MarketplacePackageAction) => {
    if (!canRunMarketplacePackageAction(action, permissions)) return;
    setActiveAction(action);
  };

  const detailHeader = (
    <MarketplacePackageDetailHeader
      detail={detail}
      permissions={permissions}
      breadcrumbs={[
        { label: t('marketplace.breadcrumbs.root'), to: ROUTES.marketplace.root },
        { label: t('marketplace.center.header.title'), to: ROUTES.marketplace.packages },
      ]}
      onBack={() => navigate(ROUTES.marketplace.packages)}
      onEdit={() => {
        if (permissions.canEdit) {
          navigate(ROUTES.marketplace.packageEdit(
            detail.targetClient,
            detail.packageId,
            detail.packageFormat,
          ));
        }
      }}
      onExport={() => openAction('export')}
      onInstall={() => openAction('install')}
      onDelete={() => openAction('delete')}
    />
  );

  return (
    <MarketplaceShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'settings',
        header: detailHeader,
        navigation: {
          content: ({ collapsed }) => (
            <MarketplaceDetailTopTabs
              detail={detail}
              tabs={tabs}
              activeTab={activeTab}
              onChange={tab => setActiveTab(tab)}
              collapsed={collapsed}
            />
          ),
          accessibleLabel: t('marketplace.detail.sidebar.info.title'),
          preset: 'detail-navigation',
          header: {
            leading: <Info className="h-4 w-4 text-primary" aria-hidden="true" />,
            title: t('marketplace.detail.sidebar.info.title'),
          },
        },
        main: {
          accessibleLabel: t('marketplace.detail.main.label'),
          content: (
            <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
              {renderContent()}
              {permissions.canInstall ? (
        <MarketplaceInstallDialog
          open={visibleActiveAction === 'install'}
          item={detail}
          onItemRefresh={item => setDetail(current => (
            current ? { ...current, ...item } : current
          ))}
          onOpenChange={open => setActiveAction(open ? 'install' : null)}
        />
      ) : null}
              {permissions.canExport ? (
        <MarketplaceExportDialog
          open={visibleActiveAction === 'export'}
          detail={detail}
          onOpenChange={open => setActiveAction(open ? 'export' : null)}
        />
      ) : null}
              {permissions.canDelete ? (
        <MarketplaceDeleteDialog
          open={visibleActiveAction === 'delete'}
          detail={detail}
          onOpenChange={open => setActiveAction(open ? 'delete' : null)}
          onDeleted={() => navigate(ROUTES.marketplace.packages)}
        />
              ) : null}
            </div>
          ),
        },
      }}
    />
  );
};
