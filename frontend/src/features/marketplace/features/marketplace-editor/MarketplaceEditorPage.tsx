import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Bot,
  Command,
  FileArchive,
  FileText,
  Info,
  Network,
  Package,
  Wand2,
  Zap,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import type {
  MarketplacePackageDetail,
} from '@/features/marketplace/model/marketplaceTypes';
import { MarketplaceEditorHeader } from './components/MarketplaceEditorHeader';
import { getPackage } from '../../api/marketplaceApi';
import {
  getMarketplaceEditorTabLabelKey,
  providerEditorTabs,
  type MarketplaceEditorTab,
} from './marketplaceEditorTabsModel';
import {
  buildMarketplaceEditorPath,
  resolveMarketplaceEditorSection,
} from './marketplaceEditorSectionModel';
import { MarketplaceBasicPage } from './resources/MarketplaceBasicPage';
import { MarketplaceDocumentResourcePage } from './resources/MarketplaceDocumentResourcePage';
import { MarketplaceFileResourcePage } from './resources/MarketplaceFileResourcePage';
import type { MarketplaceFileResourceRenderSurface } from './resources/MarketplaceFileResourcePage';
import { MarketplaceHooksPage } from './resources/MarketplaceHooksPage';
import { MarketplaceMCPPage } from './resources/MarketplaceMCPPage';
import { MarketplaceRootDocumentPage } from './resources/MarketplaceRootDocumentPage';
import {
  MARKETPLACE_TAB_TO_DOCUMENT_RESOURCE,
} from './resources/marketplaceDocumentSources';
import { useMarketplaceResourceSession } from '../../model/marketplaceResourceSession';
import type { MarketplacePackageMutationResult } from '../../model/marketplaceMutation';
import { MarketplaceShellAdapter } from '../../components/MarketplaceShellAdapter';
import type { DocumentWorkbenchRenderSurface } from '@/shared/components/document-workflow';

export interface MarketplaceEditorPageProps {
  mode: 'edit';
  navigationSlot?: React.ReactNode;
}

const tabIcons: Record<MarketplaceEditorTab, React.ComponentType<{ className?: string }>> = {
  basic: Info,
  agentsMd: FileText,
  skills: Wand2,
  commands: Command,
  agents: Bot,
  hooks: Zap,
  mcp: Network,
  outputStyle: Wand2,
  files: FileArchive,
};

export const MarketplaceEditorPage: React.FC<MarketplaceEditorPageProps> = ({ mode, navigationSlot }) => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const params = useParams();
  const provider = params.provider === 'codex' || params.provider === 'claude-code'
    ? params.provider
    : null;
  const packageId = params.packageId ?? '';
  const activeSection = provider ? resolveMarketplaceEditorSection(provider, params.section) : 'basic';
  const [currentPackage, setCurrentPackage] = React.useState<MarketplacePackageDetail | null>(null);
  const [isLoading, setIsLoading] = React.useState(mode === 'edit');
  const [loadErrorKey, setLoadErrorKey] = React.useState<string | null>(null);
  const {
    identityGeneration: packageIdentityGeneration,
    session: packageSession,
  } = useMarketplaceResourceSession({
    provider,
    packageId,
    resourceType: 'package',
  }, (
    currentPackage?.provider === provider && currentPackage.packageId === packageId
      ? currentPackage.revision
      : ''
  ));

  React.useLayoutEffect(() => {
    setCurrentPackage(null);
    setIsLoading(mode === 'edit');
    setLoadErrorKey(null);
  }, [mode, packageIdentityGeneration]);

  const handleMutation = React.useCallback(async (result: MarketplacePackageMutationResult) => {
    if (!provider) {
      return;
    }
    packageSession.acceptMutation(packageIdentityGeneration, result);
    setCurrentPackage((current) => (
      current?.provider === provider && current.packageId === packageId
        ? { ...current, revision: result.revision }
        : current
    ));
    const detail = await packageSession.run(
      packageIdentityGeneration,
      'package-detail',
      () => getPackage(provider, packageId),
    );
    setCurrentPackage((current) => (
      current?.provider === provider && current.packageId === packageId
        ? { ...detail, revision: result.revision }
        : current
    ));
  }, [
    packageId,
    packageIdentityGeneration,
    packageSession,
    provider,
  ]);

  React.useEffect(() => {
    if (mode !== 'edit' || !provider || !packageId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadErrorKey(null);
    void packageSession.query(
      packageIdentityGeneration,
      'package-detail',
      () => getPackage(provider, packageId),
      {
        onSuccess: (detail) => {
          setCurrentPackage(detail);
        },
        onError: () => {
          setCurrentPackage(null);
          setLoadErrorKey('marketplace.editor.loadError.description');
        },
        onSettled: () => {
          setIsLoading(false);
        },
      },
    );
  }, [
    mode,
    packageId,
    packageIdentityGeneration,
    packageSession,
    provider,
  ]);

  React.useEffect(() => {
    if (!provider || !packageId) return;
    const nextPath = buildMarketplaceEditorPath({
      provider,
      packageId,
      section: activeSection,
    });
    if (params.section !== activeSection) {
      navigate(nextPath, { replace: true });
    }
  }, [activeSection, navigate, packageId, params.section, provider]);

  if (!provider || !packageId) {
    return null;
  }

  if (loadErrorKey) {
    return (
      <MarketplaceShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          content: (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-foreground">{t('marketplace.editor.loadError.title')}</h2>
                <p className="text-sm text-muted-foreground">{t(loadErrorKey)}</p>
              </div>
              <Button size="sm" onClick={() => navigate(ROUTES.marketplace.packages)}>
                {t('marketplace.editor.loadError.action')}
              </Button>
            </div>
          ),
        }}
      />
    );
  }

  const currentPackageMatchesRoute = currentPackage?.provider === provider
    && currentPackage.packageId === packageId;

  if (isLoading || !currentPackage || !currentPackageMatchesRoute) {
    return (
      <MarketplaceShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          content: <LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />,
        }}
      />
    );
  }

  const visibleEditorTabs = providerEditorTabs[provider];
  const resolvedDisplayName = currentPackage.displayName || packageId || t('marketplace.editor.fields.displayNamePlaceholder');
  const navItems = visibleEditorTabs.map(tab => ({
    id: tab,
    icon: tabIcons[tab],
    labelKey: getMarketplaceEditorTabLabelKey(provider, tab),
    count: null,
  }));

  const editorHeader = (
    <MarketplaceEditorHeader
      breadcrumbs={[
        { label: t('marketplace.breadcrumbs.root'), to: ROUTES.marketplace.root },
        { label: t('marketplace.center.header.title'), to: ROUTES.marketplace.packages },
        {
          label: resolvedDisplayName,
          to: ROUTES.marketplace.packageDetail(provider, packageId),
        },
        { label: t(getMarketplaceEditorTabLabelKey(provider, activeSection)) },
      ]}
      onBack={() => navigate(ROUTES.marketplace.packages)}
    />
  );

  const navigationRegion = {
    content: ({ collapsed }: { collapsed: boolean }) => (
      <nav
        aria-label={t('marketplace.editor.navigation.label')}
        data-testid="marketplace-editor-nav"
        className="min-h-0 flex-1 overflow-y-auto p-2"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              title={t(item.labelKey)}
              aria-label={t(item.labelKey)}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => navigateSection(item.id as MarketplaceEditorTab)}
              className={[
                'mb-1 flex w-full items-center rounded-lg p-2 transition-colors',
                collapsed && 'justify-center',
                isActive
                  ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent',
              ].filter(Boolean).join(' ')}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed ? <span className="ml-2 flex-1 text-left text-sm">{t(item.labelKey)}</span> : null}
            </button>
          );
        })}
      </nav>
    ),
    accessibleLabel: t('marketplace.editor.navigation.label'),
    preset: 'editor-navigation' as const,
    header: {
      leading: <Package className="h-4 w-4 shrink-0 text-sidebar-primary" data-testid="marketplace-editor-nav-header-icon" />,
      title: resolvedDisplayName,
    },
  };

  const renderFileResourceSurface = (surface: MarketplaceFileResourceRenderSurface) => (
    <MarketplaceShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        header: editorHeader,
        navigation: navigationRegion,
        navigator: surface.navigator,
        main: surface.main,
      }}
    />
  );

  const renderDocumentResourceSurface = (surface: DocumentWorkbenchRenderSurface) => (
    <MarketplaceShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        header: editorHeader,
        navigation: navigationRegion,
        navigator: surface.navigator,
        main: surface.main,
      }}
    />
  );

  const navigateSection = (section: MarketplaceEditorTab) => {
    navigate(buildMarketplaceEditorPath({
      provider,
      packageId,
      section,
    }));
  };

  const renderActiveSection = () => {
    switch (activeSection) {
      case 'basic':
        return (
          <MarketplaceBasicPage
            key={`${currentPackage.provider}:${currentPackage.packageId}:basic`}
            packageDetail={currentPackage}
            onMutation={handleMutation}
          />
        );
      case 'agentsMd':
        return (
          <MarketplaceRootDocumentPage
            key={`${currentPackage.provider}:${currentPackage.packageId}:root-document`}
            packageDetail={currentPackage}
            onMutation={handleMutation}
          />
        );
      case 'commands':
      case 'agents':
      case 'outputStyle':
        return (
          <MarketplaceDocumentResourcePage
            key={`${provider}:${packageId}:${MARKETPLACE_TAB_TO_DOCUMENT_RESOURCE[activeSection]}`}
            provider={provider}
            packageId={packageId}
            resourceType={MARKETPLACE_TAB_TO_DOCUMENT_RESOURCE[activeSection]}
            initialRevision={currentPackage.revision}
            onMutation={handleMutation}
            renderSurface={renderDocumentResourceSurface}
          />
        );
      case 'mcp':
        return (
          <MarketplaceMCPPage
            key={`${currentPackage.provider}:${currentPackage.packageId}:mcp`}
            packageDetail={currentPackage}
            onMutation={handleMutation}
          />
        );
      case 'hooks':
        return (
          <MarketplaceHooksPage
            key={`${currentPackage.provider}:${currentPackage.packageId}:hooks`}
            packageDetail={currentPackage}
            onMutation={handleMutation}
          />
        );
      case 'skills':
        return (
          <MarketplaceFileResourcePage
            key={`${currentPackage.provider}:${currentPackage.packageId}:skills`}
            title={t('marketplace.editor.fileManager.skills.title')}
            resourceType="skills"
            packageDetail={currentPackage}
            onMutation={handleMutation}
            renderSurface={renderFileResourceSurface}
          />
        );
      case 'files':
        return (
          <MarketplaceFileResourcePage
            key={`${currentPackage.provider}:${currentPackage.packageId}:files`}
            title={t('marketplace.editor.fileManager.packageFiles.title')}
            resourceType="files"
            packageDetail={currentPackage}
            onMutation={handleMutation}
            renderSurface={renderFileResourceSurface}
          />
        );
      default:
        return null;
    }
  };

  const activeContent = renderActiveSection();
  const isProductShellResource = activeSection === 'skills'
    || activeSection === 'files'
    || activeSection === 'commands'
    || activeSection === 'agents'
    || activeSection === 'outputStyle';
  if (isProductShellResource) {
    return activeContent;
  }

  return (
    <MarketplaceShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        header: editorHeader,
        navigation: navigationRegion,
        main: {
          accessibleLabel: t('marketplace.editor.main.label'),
          content: (
            <div className="flex min-w-0 flex-1 overflow-auto">
              {activeContent}
            </div>
          ),
        },
      }}
    />
  );
};
