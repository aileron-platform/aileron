/// <reference types="vite/client" />
import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { LoadingSpinner } from '../shared/components/ui/LoadingSpinner';
import { RequireAuth, PublicRoute } from '../features/auth/components/RequireAuth';
import { useI18n } from '@/shared/hooks/useI18n';

const WorkspaceModule = React.lazy(() => import('../features/workspace/WorkspaceModule'));
const MarketplaceModule = React.lazy(() => import('../features/marketplace/MarketplaceModule'));
const WorkspaceWizardPage = React.lazy(() => import('../features/workspace-wizard/WorkspaceWizardPage'));
const AutomationModule = React.lazy(() => import('../features/automation/AutomationModule'));
const KnowledgeBaseModule = React.lazy(() => import('../features/knowledge-base/KnowledgeBaseModule'));
const ProfilePage = React.lazy(() => import('../pages/ProfilePage'));
const SettingsPage = React.lazy(() => import('../pages/SettingsPage'));
const LoginPage = React.lazy(() => import('../features/auth/pages/LoginPage'));
const RegisterPage = React.lazy(() => import('../features/auth/pages/RegisterPage'));
const CallbackPage = React.lazy(() => import('../features/auth/pages/CallbackPage'));
const ClaudeToolWidgetDemo = React.lazy(() => import('../pages/ClaudeToolWidgetDemo'));

export const AppRouter: React.FC = () => {
  const { t } = useI18n();

  return (
    <div className="w-full h-full">
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />

          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />

          <Route path="/callback" element={<CallbackPage />} />

          <Route
            path="/workspaces/workspace-wizard"
            element={(
              <RequireAuth>
                <WorkspaceWizardPage />
              </RequireAuth>
            )}
          />
          <Route
            path="/workspaces/*"
            element={(
              <RequireAuth>
                <WorkspaceModule />
              </RequireAuth>
            )}
          />

          <Route
            path="/marketplace/*"
            element={(
              <RequireAuth>
                <MarketplaceModule />
              </RequireAuth>
            )}
          />

          <Route
            path="/automation/*"
            element={(
              <RequireAuth>
                <AutomationModule />
              </RequireAuth>
            )}
          />

          <Route
            path="/knowledge-bases/*"
            element={(
              <RequireAuth>
                <KnowledgeBaseModule />
              </RequireAuth>
            )}
          />

          <Route
            path="/profile"
            element={(
              <RequireAuth>
                <ProfilePage />
              </RequireAuth>
            )}
          />
          <Route
            path="/settings"
            element={(
              <RequireAuth>
                <SettingsPage />
              </RequireAuth>
            )}
          />

          <Route
            path="/demo/claude-tool-widget"
            element={<ClaudeToolWidgetDemo />}
          />

          <Route path="*" element={<div>{t('common.notFound')}</div>} />
        </Routes>
      </Suspense>
    </div>
  );
};

export default AppRouter;
