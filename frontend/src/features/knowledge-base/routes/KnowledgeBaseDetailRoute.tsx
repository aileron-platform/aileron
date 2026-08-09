import React from 'react';
import { ArrowLeft, Database, Loader2, RefreshCcw } from 'lucide-react';
import { Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { AuthorizationDeniedState } from '@/features/auth/public';
import { subscribeApiError } from '@/shared/api/apiClient';
import { isKnowledgeBaseAuthorizationDenialCode } from '@/shared/authorization/authorizationErrorCodes';
import { FeatureShellBreadcrumbBar } from '@/shared/components/shell';
import { Button } from '@/shared/components/ui/button';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { formatKnowledgeBaseFileSize } from '../model/formatKnowledgeBaseFileSize';
import { KnowledgeBaseWorkspacesTab } from '../components/KnowledgeBaseWorkspacesTab';
import { KnowledgeBaseFilesTab } from '../components/KnowledgeBaseFilesTab';
import { KnowledgeBaseSettingsTab } from '../components/KnowledgeBaseSettingsTab';
import { KnowledgeBaseSharingTab } from '../components/KnowledgeBaseSharingTab';
import { KnowledgeBaseSidebar } from '../components/KnowledgeBaseSidebar';
import { KNOWLEDGE_BASE_NAVIGATION_ITEMS } from '../components/knowledgeBaseNavigation';
import { resolveKnowledgeBaseActiveNav } from '../model/knowledgeBaseShellModel';
import { resolveKnowledgeBasePermissions } from '../model/knowledgeBasePermissions';
import { useKnowledgeBase } from '../providers/KnowledgeBaseProvider';
import { KnowledgeBaseShellAdapter } from '../components/KnowledgeBaseShellAdapter';

const KnowledgeBaseVersionControlTab = React.lazy(() =>
  import('../components/KnowledgeBaseVersionControlTab').then(({ KnowledgeBaseVersionControlTab: Component }) => ({
    default: Component,
  })),
);

type DetailLoadStatus = 'loading' | 'ready' | 'denied' | 'error';

const isKnowledgeBaseAccessDeniedError = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }
  const candidate = error as { errorCode?: unknown; status?: unknown };
  return candidate.status === 403
    || isKnowledgeBaseAuthorizationDenialCode(candidate.errorCode);
};

interface KnowledgeBaseDetailRouteProps {
  navigationSlot?: React.ReactNode;
}

export const KnowledgeBaseDetailRoute: React.FC<KnowledgeBaseDetailRouteProps> = ({ navigationSlot }) => {
  const { t } = useI18n();
  const location = useLocation();
  const { knowledgeBaseId } = useParams<{ knowledgeBaseId: string }>();
  const {
    detailById,
    sharesById,
    workspaceUsageById,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseWorkspaceUsage,
  } = useKnowledgeBase();
  const [detailLoadState, setDetailLoadState] = React.useState<{
    knowledgeBaseId: string | null;
    status: DetailLoadStatus;
  }>({
    knowledgeBaseId: null,
    status: 'loading',
  });
  const [detailReloadGeneration, setDetailReloadGeneration] = React.useState(0);
  const readyKnowledgeBaseIdRef = React.useRef<string | null>(null);
  const detailRefreshInFlightRef = React.useRef(false);
  const detailRefreshRequestIdRef = React.useRef(0);

  React.useEffect(() => {
    if (!knowledgeBaseId) {
      return;
    }
    let active = true;
    const preserveCurrentContent =
      readyKnowledgeBaseIdRef.current === knowledgeBaseId;
    if (!preserveCurrentContent) {
      setDetailLoadState({ knowledgeBaseId, status: 'loading' });
    }
    const requestId = detailRefreshRequestIdRef.current + 1;
    detailRefreshRequestIdRef.current = requestId;
    detailRefreshInFlightRef.current = true;

    void loadKnowledgeBaseDetail(knowledgeBaseId)
      .then((loadedDetail) => {
        if (!active) {
          return;
        }
        const loadedPermissions = resolveKnowledgeBasePermissions(
          loadedDetail.accessRole,
          loadedDetail.allowedOperations,
        );
        if (!loadedPermissions.canRead) {
          readyKnowledgeBaseIdRef.current = null;
          setDetailLoadState({ knowledgeBaseId, status: 'denied' });
          return;
        }
        readyKnowledgeBaseIdRef.current = knowledgeBaseId;
        setDetailLoadState({ knowledgeBaseId, status: 'ready' });
        if (loadedPermissions.canManage) {
          void Promise.allSettled([
            loadKnowledgeBaseShares(knowledgeBaseId),
            loadKnowledgeBaseWorkspaceUsage(knowledgeBaseId),
          ]);
        }
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        if (isKnowledgeBaseAccessDeniedError(error)) {
          readyKnowledgeBaseIdRef.current = null;
          setDetailLoadState({ knowledgeBaseId, status: 'denied' });
        } else if (!preserveCurrentContent) {
          setDetailLoadState({ knowledgeBaseId, status: 'error' });
        }
      })
      .finally(() => {
        if (detailRefreshRequestIdRef.current === requestId) {
          detailRefreshInFlightRef.current = false;
        }
      });

    return () => {
      active = false;
    };
  }, [
    knowledgeBaseId,
    detailReloadGeneration,
    loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares,
    loadKnowledgeBaseWorkspaceUsage,
  ]);

  React.useEffect(() => {
    const refresh = () => {
      if (!detailRefreshInFlightRef.current) {
        setDetailReloadGeneration((current) => current + 1);
      }
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refresh();
      }
    };
    const unsubscribeApiError = subscribeApiError((event) => {
      if (isKnowledgeBaseAuthorizationDenialCode(event.errorCode)) {
        refresh();
      }
    });

    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      unsubscribeApiError();
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const detail = knowledgeBaseId ? detailById[knowledgeBaseId] : undefined;
  const permissions = resolveKnowledgeBasePermissions(
    detail?.accessRole,
    detail?.allowedOperations,
  );
  const shares = knowledgeBaseId ? sharesById[knowledgeBaseId] ?? [] : [];
  const workspaceUsage = knowledgeBaseId ? workspaceUsageById[knowledgeBaseId] : undefined;

  if (!knowledgeBaseId) {
    return (
      <KnowledgeBaseShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          content: <Navigate to={ROUTES.knowledgeBase.root} replace />,
        }}
      />
    );
  }

  const activeDetailStatus = detailLoadState.knowledgeBaseId === knowledgeBaseId
    ? detailLoadState.status
    : 'loading';
  if (activeDetailStatus === 'loading') {
    return (
      <KnowledgeBaseShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          content: (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {t('knowledgeBase.detail.loading')}
            </div>
          ),
        }}
      />
    );
  }
  if (activeDetailStatus === 'error') {
    return (
      <KnowledgeBaseShellAdapter
        navigationSlot={navigationSlot}
        surface={{
          kind: 'state',
          content: (
            <div
              role="alert"
              className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-muted-foreground"
            >
              <span>{t('knowledgeBase.list.loadFailed')}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setDetailReloadGeneration((current) => current + 1)}
              >
                <RefreshCcw className="mr-1.5 h-3.5 w-3.5" />
                {t('knowledgeBase.list.refreshAction')}
              </Button>
            </div>
          ),
        }}
      />
    );
  }
  const accessRole = permissions.accessRole;
  if (
    activeDetailStatus === 'denied'
    || !permissions.canRead
    || !accessRole
    || !detail
  ) {
    return (
      <KnowledgeBaseShellAdapter
        navigationSlot={navigationSlot}
        surface={{ kind: 'state', content: <AuthorizationDeniedState /> }}
      />
    );
  }

  const activeNav = resolveKnowledgeBaseActiveNav(location.pathname);
  const activeNavItem = KNOWLEDGE_BASE_NAVIGATION_ITEMS.find((item) => item.id === activeNav.featureId);
  const activeSubItem = activeNavItem?.subItems?.find((item) => item.id === activeNav.subItemId);
  const activeLabelKey = activeSubItem?.labelKey ?? activeNavItem?.labelKey;
  const activeLabel = activeLabelKey ? t(activeLabelKey) : undefined;
  const storageInfo = `${formatKnowledgeBaseFileSize(detail.currentSizeBytes)} / ${
    formatKnowledgeBaseFileSize(detail.effectiveQuotaBytes)
  }`;

  const header = (
    <FeatureShellBreadcrumbBar
      items={[
        { label: t('knowledgeBase.detail.breadcrumbRoot'), to: ROUTES.knowledgeBase.root },
        { label: detail.name, to: ROUTES.knowledgeBase.files(knowledgeBaseId) },
      ]}
      title={activeLabel}
      icon={Database}
      actions={(
        <Button asChild variant="outline" size="sm" className="h-7 gap-1 px-2 text-xs">
          <Link to={ROUTES.knowledgeBase.root}>
            <ArrowLeft className="h-3.5 w-3.5" />
            {t('knowledgeBase.detail.actions.backToList')}
          </Link>
        </Button>
      )}
    />
  );
  const navigation = {
    accessibleLabel: t('knowledgeBase.detail.breadcrumbRoot'),
    title: detail.name,
    icon: Database,
    content: ({ collapsed }: { collapsed: boolean }) => <KnowledgeBaseSidebar
      knowledgeBaseId={knowledgeBaseId}
      accessRole={accessRole}
      accessSource={detail.accessSource}
      storageInfo={storageInfo}
      ownerLabel={detail.ownerId}
      shareCount={shares.length > 0 ? shares.length : null}
      attachmentCount={workspaceUsage?.attachmentCount ?? null}
      collapsed={collapsed}
    />,
  };
  const renderSimpleSurface = (content: React.ReactNode, accessibleLabel = activeLabel ?? t('knowledgeBase.detail.breadcrumbRoot')) => (
    <KnowledgeBaseShellAdapter
      navigationSlot={navigationSlot}
      surface={{
        kind: 'regions',
        header,
        navigation,
        main: { content, accessibleLabel },
      }}
    />
  );

  return (
    <Routes>
      <Route
        index
        element={renderSimpleSurface(
          <Navigate to={ROUTES.knowledgeBase.files(knowledgeBaseId)} replace />,
        )}
      />
      <Route
        path="files"
        element={(
          <KnowledgeBaseFilesTab
            key={knowledgeBaseId}
            knowledgeBaseId={knowledgeBaseId}
            canWrite={permissions.canWrite}
            renderRegions={({ navigator, navigatorActions, main }) => (
              <KnowledgeBaseShellAdapter
                navigationSlot={navigationSlot}
                surface={{
                  kind: 'regions',
                  header,
                  navigation,
                  navigator: {
                    content: navigator,
                    accessibleLabel: t('knowledgeBase.files.toolbarTitle'),
                    title: t('knowledgeBase.files.toolbarTitle'),
                    icon: Database,
                    actions: navigatorActions,
                  },
                  main: {
                    content: main,
                    accessibleLabel: t('knowledgeBase.navigation.files'),
                  },
                }}
              />
            )}
          />
        )}
      />
      <Route
        path="version-control"
        element={renderSimpleSurface(
          <Navigate to={ROUTES.knowledgeBase.versionControlChanges(knowledgeBaseId)} replace />,
        )}
      />
      {(['changes', 'history'] as const).map((mode) => (
        <Route
          key={mode}
          path={`version-control/${mode}`}
          element={(
            <React.Suspense fallback={(
              <KnowledgeBaseShellAdapter
                navigationSlot={navigationSlot}
                surface={{
                  kind: 'state',
                  content: <div className="p-4 text-sm text-muted-foreground">{t('knowledgeBase.versionControl.loading')}</div>,
                }}
              />
            )}>
              <KnowledgeBaseVersionControlTab
                knowledgeBaseId={knowledgeBaseId}
                accessRole={accessRole}
                allowedOperations={detail.allowedOperations}
                mode={mode}
                versionControlEnabled={detail.versionControlEnabled}
                renderRegions={({
                  navigator,
                  navigatorTitle,
                  navigatorIcon,
                  navigatorInfo,
                  navigatorActions,
                  main,
                }) => (
                  <KnowledgeBaseShellAdapter
                    navigationSlot={navigationSlot}
                    surface={{
                      kind: 'regions',
                      header,
                      navigation,
                      navigator: {
                        content: navigator,
                        accessibleLabel: navigatorTitle,
                        title: navigatorTitle,
                        icon: navigatorIcon,
                        info: navigatorInfo,
                        actions: navigatorActions,
                      },
                      main: {
                        content: main,
                        accessibleLabel: t('knowledgeBase.navigation.versionControl'),
                      },
                    }}
                  />
                )}
              />
            </React.Suspense>
          )}
        />
      ))}
      <Route
        path="sharing"
        element={renderSimpleSurface(
          <KnowledgeBaseSharingTab
            knowledgeBaseId={knowledgeBaseId}
            canManage={permissions.canManageShares}
          />,
          t('knowledgeBase.navigation.sharing'),
        )}
      />
      <Route
        path="workspaces"
        element={renderSimpleSurface(
          <KnowledgeBaseWorkspacesTab knowledgeBaseId={knowledgeBaseId} />,
          t('knowledgeBase.navigation.workspaces'),
        )}
      />
      <Route
        path="settings"
        element={renderSimpleSurface(
          <KnowledgeBaseSettingsTab
            knowledgeBaseId={knowledgeBaseId}
            canManage={permissions.canManageSettings}
            canManageVisibility={permissions.canManageVisibility}
            canDelete={permissions.canDelete}
          />,
          t('knowledgeBase.navigation.settings'),
        )}
      />
      <Route
        path="*"
        element={renderSimpleSurface(
          <div className="p-6 text-sm text-muted-foreground">{t('common.notFound')}</div>,
          t('common.notFound'),
        )}
      />
    </Routes>
  );
};
