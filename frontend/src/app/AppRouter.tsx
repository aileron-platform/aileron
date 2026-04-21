/**
 * AppRouter - 全域路由管理
 *
 * 負責整個應用程式的路由配置和模組載入
 * 支援懶載入和程式碼分割
 */

/// <reference types="vite/client" />
import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { LoadingSpinner } from '../shared/components/ui/LoadingSpinner';
import { RequireAuth, PublicRoute } from '../features/auth/components/RequireAuth';

// 懶載入模組
const WorkspaceModule = React.lazy(() => import('../features/workspace/WorkspaceModule'));
const TemplateManagementModule = React.lazy(() => import('../features/template-management/TemplateManagementModule'));
const WorkspaceWizardPage = React.lazy(() => import('../features/workspace-wizard/WorkspaceWizardPage'));
const AutomationModule = React.lazy(() => import('../features/automation/AutomationModule'));
const ProfilePage = React.lazy(() => import('../pages/ProfilePage'));
const SettingsPage = React.lazy(() => import('../pages/SettingsPage'));
const LoginPage = React.lazy(() => import('../features/auth/pages/LoginPage'));
const RegisterPage = React.lazy(() => import('../features/auth/pages/RegisterPage'));
const CallbackPage = React.lazy(() => import('../features/auth/pages/CallbackPage'));
const ClaudeToolWidgetDemo = React.lazy(() => import('../pages/ClaudeToolWidgetDemo'));

/**
 * AppRouter 組件
 * 
 * 應用程式的路由管理器，負責：
 * 1. 定義應用程式的路由結構
 * 2. 管理模組的懶載入
 * 3. 處理路由重定向和錯誤頁面
 */
export const AppRouter: React.FC = () => {
  return (
    <div className="w-full h-full">
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          {/* 首頁導向登入 */}
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* 認證頁面 - 使用 PublicRoute 以便已認證用戶重定向 */}
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

          {/* OAuth2/OIDC 回調頁面 */}
          <Route path="/callback" element={<CallbackPage />} />

          {/* 工作區模組 */}
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

          {/* 範本管理模組 */}
          <Route
            path="/templates/*"
            element={(
              <RequireAuth>
                <TemplateManagementModule />
              </RequireAuth>
            )}
          />

          {/* 自動化中心模組 */}
          <Route
            path="/automation/*"
            element={(
              <RequireAuth>
                <AutomationModule />
              </RequireAuth>
            )}
          />

          {/* 獨立頁面 */}
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

          {/* ClaudeToolWidget 示範頁面 */}
          <Route
            path="/demo/claude-tool-widget"
            element={<ClaudeToolWidgetDemo />}
          />

          {/* 404 頁面 */}
          <Route path="*" element={<div>頁面不存在</div>} />
        </Routes>
      </Suspense>
    </div>
  );
};

export default AppRouter;
