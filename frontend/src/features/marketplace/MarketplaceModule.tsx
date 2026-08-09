import React from 'react';
import { Routes, Route, Navigate, Outlet, useParams } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import { projectPlatformIdentityEntry } from '@/shared/components/entry/platformIdentityEntryProjection';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import { ROUTES } from '@/shared/constants/routes';
import { MarketplaceCenterPage } from './features/marketplace-center/MarketplaceCenterPage';
import { MarketplaceDetailPage } from './features/marketplace-detail/MarketplaceDetailPage';
import { MarketplaceEditorPage } from './features/marketplace-editor/MarketplaceEditorPage';
import { MarketplaceSettingsPage } from './features/marketplace-settings/MarketplaceSettingsPage';
import { MarketplaceShellAdapter } from './components/MarketplaceShellAdapter';
import { AuthorizationDeniedState, useAuth } from '@/features/auth/public';

const isMarketplaceProvider = (value: string | undefined): value is MarketplaceProvider =>
  value === 'claude-code' || value === 'codex';

const MarketplaceRedirectSurface: React.FC<{
  navigationSlot: React.ReactNode;
  to: string;
}> = ({ navigationSlot, to }) => (
  <MarketplaceShellAdapter
    navigationSlot={navigationSlot}
    surface={{
      kind: 'state',
      content: <Navigate to={to} replace />,
    }}
  />
);

const MarketplacePackageRouteGuard: React.FC<{
  navigationSlot: React.ReactNode;
}> = ({ navigationSlot }) => {
  const { provider, packageId } = useParams();

  if (!isMarketplaceProvider(provider) || !packageId) {
    return <MarketplaceRedirectSurface navigationSlot={navigationSlot} to={ROUTES.marketplace.packages} />;
  }

  return <Outlet />;
};

interface MarketplaceErrorBoundaryProps {
  children: React.ReactNode;
  fallback: React.ReactNode;
}

interface MarketplaceErrorBoundaryState {
  hasError: boolean;
}

class MarketplaceErrorBoundary extends React.Component<MarketplaceErrorBoundaryProps, MarketplaceErrorBoundaryState> {
  state: MarketplaceErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): MarketplaceErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown): void {
    console.error('Marketplace module render failed', error);
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      return this.props.fallback;
    }

    return this.props.children;
  }
}

const MarketplaceErrorFallback: React.FC = () => {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-foreground">{t('marketplace.errors.module.title')}</h2>
        <p className="text-sm text-muted-foreground">{t('marketplace.errors.module.description')}</p>
      </div>
      <Button size="sm" onClick={() => window.location.assign(ROUTES.marketplace.packages)}>
        {t('marketplace.errors.module.action')}
      </Button>
    </div>
  );
};

interface MarketplaceModuleProps {
  navigationSlot: React.ReactNode;
  userId: string | null;
}

const MarketplaceAdminRoute: React.FC<{
  navigationSlot: React.ReactNode;
  children: React.ReactNode;
}> = ({ navigationSlot, children }) => {
  const { isPlatformAdmin, isLoading } = useAuth();

  if (isLoading) {
    return (
      <EntryFrame
        isPending
        transitionKey="platform-identity"
        projection={projectPlatformIdentityEntry({ status: 'checking' })}
        navigationSlot={navigationSlot}
        onAction={() => undefined}
      >
        {null}
      </EntryFrame>
    );
  }

  if (!isPlatformAdmin) {
    return (
      <MarketplaceShellAdapter
        navigationSlot={navigationSlot}
        surface={{ kind: 'state', content: <AuthorizationDeniedState /> }}
      />
    );
  }

  return children;
};

export const MarketplaceModule: React.FC<MarketplaceModuleProps> = ({ navigationSlot, userId }) => {
  const { t } = useI18n();

  return (
    <MarketplaceErrorBoundary
      fallback={(
        <MarketplaceShellAdapter
          navigationSlot={navigationSlot}
          surface={{ kind: 'state', content: <MarketplaceErrorFallback /> }}
        />
      )}
    >
      <React.Suspense
        fallback={(
          <MarketplaceShellAdapter
            navigationSlot={navigationSlot}
            surface={{
              kind: 'state',
              content: <LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />,
            }}
          />
        )}
      >
          <Routes>
            <Route index element={<MarketplaceRedirectSurface navigationSlot={navigationSlot} to="packages" />} />
            <Route path="packages">
              <Route
                index
                element={<MarketplaceCenterPage navigationSlot={navigationSlot} />}
              />
              <Route
                path="settings"
                element={<MarketplaceSettingsPage navigationSlot={navigationSlot} userId={userId} />}
              />
              <Route
                path="new"
                element={<MarketplaceRedirectSurface navigationSlot={navigationSlot} to={ROUTES.marketplace.packages} />}
              />
              <Route
                path="new/:section"
                element={<MarketplaceRedirectSurface navigationSlot={navigationSlot} to={ROUTES.marketplace.packages} />}
              />
              <Route path=":provider/:packageId" element={<MarketplacePackageRouteGuard navigationSlot={navigationSlot} />}>
                <Route
                  index
                  element={<MarketplaceDetailPage navigationSlot={navigationSlot} />}
                />
                <Route
                  path="edit"
                  element={(
                    <MarketplaceAdminRoute navigationSlot={navigationSlot}>
                      <MarketplaceEditorPage mode="edit" navigationSlot={navigationSlot} />
                    </MarketplaceAdminRoute>
                  )}
                />
                <Route
                  path="edit/:section"
                  element={(
                    <MarketplaceAdminRoute navigationSlot={navigationSlot}>
                      <MarketplaceEditorPage mode="edit" navigationSlot={navigationSlot} />
                    </MarketplaceAdminRoute>
                  )}
                />
              </Route>
            </Route>
            <Route path="*" element={<MarketplaceRedirectSurface navigationSlot={navigationSlot} to="packages" />} />
          </Routes>
      </React.Suspense>
    </MarketplaceErrorBoundary>
  );
};
