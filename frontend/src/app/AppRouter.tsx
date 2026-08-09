/// <reference types="vite/client" />
import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import {
  PublicRoute,
  RequireAuth,
  RequirePlatformAdmin,
  RequirePlatformMember,
  RequirePlatformOperation,
  loadLoginPage,
  loadRegisterPage,
} from '@/features/auth/public';
import { useI18n } from '@/shared/hooks/useI18n';
import { ROUTES } from '@/shared/constants/routes';
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';
import { useApp } from '@/app/providers/AppProvider';
import { loadKnowledgeBaseModule } from '@/features/knowledge-base/public';
import { loadMarketplaceModule } from '@/features/marketplace/public';
import { loadUserManagementModule } from '@/features/user-management/public';
import { loadPlatformResourcesModule } from '@/features/platform-resources/public';
import { loadAutomationModule } from '@/features/workspace-automation/public';
import { loadWorkspaceWizardPage } from '@/features/workspace-wizard/public';
import { WorkspaceDeepLinkRoute, WorkspaceRoute } from './routes/WorkspaceRoute';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';
import { projectPlatformIdentityEntry } from '@/shared/components/entry/platformIdentityEntryProjection';

const MarketplaceModule = React.lazy(loadMarketplaceModule);
const WorkspaceWizardPage = React.lazy(loadWorkspaceWizardPage);
const AutomationModule = React.lazy(loadAutomationModule);
const KnowledgeBaseModule = React.lazy(loadKnowledgeBaseModule);
const UserManagementModule = React.lazy(loadUserManagementModule);
const PlatformResourcesModule = React.lazy(loadPlatformResourcesModule);
const ProfilePage = React.lazy(() => import('../pages/ProfilePage'));
const SettingsPage = React.lazy(() => import('../pages/SettingsPage'));
const LoginPage = React.lazy(loadLoginPage);
const RegisterPage = React.lazy(loadRegisterPage);
const appLoadingProjection = projectPlatformIdentityEntry({ status: 'checking' });

export const AppRouter: React.FC = () => {
  const { t } = useI18n();
  const { state: appState } = useApp();
  const navigationSlot = <GlobalNavigation />;

  return (
    <div className="w-full h-full">
      <Suspense
        fallback={(
          <EntryFrame
            isPending
            transitionKey="app-router"
            projection={appLoadingProjection}
            navigationSlot={navigationSlot}
            onAction={() => undefined}
          >
            {null}
          </EntryFrame>
        )}
      >
        <Routes>
          <Route path={ROUTES.root} element={<Navigate to={ROUTES.login} replace />} />

          <Route
            path={ROUTES.login}
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path={ROUTES.register}
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />

          <Route
            path={ROUTES.workspace.wizard}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformMember navigationSlot={navigationSlot}>
                  <WorkspaceWizardPage
                    navigationSlot={navigationSlot}
                    userId={appState.user?.id}
                  />
                </RequirePlatformMember>
              </RequireAuth>
            )}
          />
          <Route
            path={`${ROUTES.workspace.root}/*`}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformMember navigationSlot={navigationSlot}>
                  <WorkspaceRoute />
                </RequirePlatformMember>
              </RequireAuth>
            )}
          />
          <Route
            path="/workspace/*"
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformMember navigationSlot={navigationSlot}>
                  <WorkspaceDeepLinkRoute />
                </RequirePlatformMember>
              </RequireAuth>
            )}
          />

          <Route
            path={`${ROUTES.marketplace.root}/*`}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformMember navigationSlot={navigationSlot}>
                  <MarketplaceModule
                    navigationSlot={navigationSlot}
                    userId={appState.user.id}
                  />
                </RequirePlatformMember>
              </RequireAuth>
            )}
          />

          <Route
            path={`${ROUTES.automation}/*`}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformMember navigationSlot={navigationSlot}>
                  <AutomationModule navigationSlot={navigationSlot} />
                </RequirePlatformMember>
              </RequireAuth>
            )}
          />

          <Route
            path={`${ROUTES.knowledgeBase.root}/*`}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformMember navigationSlot={navigationSlot}>
                  <KnowledgeBaseModule navigationSlot={navigationSlot} />
                </RequirePlatformMember>
              </RequireAuth>
            )}
          />

          <Route
            path={`${ROUTES.userManagement.root}/*`}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformAdmin navigationSlot={navigationSlot}>
                  <UserManagementModule navigationSlot={navigationSlot} />
                </RequirePlatformAdmin>
              </RequireAuth>
            )}
          />

          <Route
            path={`${ROUTES.platformResources.root}/*`}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <RequirePlatformOperation
                  navigationSlot={navigationSlot}
                  operationId={OPERATION_IDS.platformResourcesRead}
                >
                  <PlatformResourcesModule navigationSlot={navigationSlot} />
                </RequirePlatformOperation>
              </RequireAuth>
            )}
          />

          <Route
            path={ROUTES.profile}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <ProfilePage />
              </RequireAuth>
            )}
          />
          <Route
            path={ROUTES.settings}
            element={(
              <RequireAuth navigationSlot={navigationSlot}>
                <SettingsPage />
              </RequireAuth>
            )}
          />


          <Route path="*" element={<div>{t('common.notFound')}</div>} />
        </Routes>
      </Suspense>
    </div>
  );
};

export default AppRouter;
