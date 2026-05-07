import React from 'react';
import { Routes, Route, Navigate, Outlet, useParams } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceProvider } from '@/shared/types/marketplace';
import { MarketplaceShell } from './components/MarketplaceShell';
import { MarketplaceCenterView } from './features/marketplace-center/MarketplaceCenterView';
import { MarketplaceDetailView } from './features/marketplace-detail/MarketplaceDetailView';
import { MarketplaceEditorView } from './features/marketplace-editor/MarketplaceEditorView';
import { MarketplaceSettingsView } from './features/marketplace-settings/MarketplaceSettingsView';

const isMarketplaceProvider = (value: string | undefined): value is MarketplaceProvider =>
  value === 'claude-code' || value === 'codex' || value === 'gemini';

const MarketplacePackageRouteGuard: React.FC = () => {
  const { provider, packageId } = useParams();

  if (!isMarketplaceProvider(provider) || !packageId) {
    return <Navigate to="/marketplace/packages" replace />;
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
      <Button size="sm" onClick={() => window.location.assign('/marketplace/packages')}>
        {t('marketplace.errors.module.action')}
      </Button>
    </div>
  );
};

export const MarketplaceModule: React.FC = () => {
  const { t } = useI18n();

  return (
    <MarketplaceShell>
      <MarketplaceErrorBoundary fallback={<MarketplaceErrorFallback />}>
        <React.Suspense fallback={<LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />}>
          <Routes>
            <Route index element={<Navigate to="packages" replace />} />
            <Route path="packages">
              <Route index element={<MarketplaceCenterView />} />
              <Route path="settings" element={<MarketplaceSettingsView />} />
              <Route path="new" element={<MarketplaceEditorView mode="create" />} />
              <Route path=":provider/:packageId" element={<MarketplacePackageRouteGuard />}>
                <Route index element={<MarketplaceDetailView />} />
                <Route path="edit" element={<MarketplaceEditorView mode="edit" />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="packages" replace />} />
          </Routes>
        </React.Suspense>
      </MarketplaceErrorBoundary>
    </MarketplaceShell>
  );
};

export default MarketplaceModule;
