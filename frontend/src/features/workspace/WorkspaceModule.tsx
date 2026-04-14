/**
 * WorkspaceModule - 工作區模組主元件
 * 
 * 工作區模組的根元件，包含：
 * - 檔案管理
 * - 版本控制
 * - 工作區設定
 * - 容器管理
 * - 任務系統
 * - Claude Code 設定
 * - 預覽功能
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { WorkspaceProvider } from './providers/WorkspaceProvider';
import { WorkspaceShell } from './components/WorkspaceShell';
import { useNavigation } from '../../app/providers/NavigationProvider';

// 懶載入子功能
const FileManagement = React.lazy(() => import('./features/file-management'));
const VersionControl = React.lazy(() => import('./features/version-control/VersionControlFeature'));
const WorkspaceSettings = React.lazy(() => import('./features/workspace-settings/WorkspaceSettingsFeature'));
const ContainerManagement = React.lazy(() => import('./features/container-management/ContainerManagementFeature'));
const WorkspaceAutomation = React.lazy(() => import('./features/workspace-automation/WorkspaceAutomationFeature'));
const ClaudeCode = React.lazy(() => import('./features/claude-code/ClaudeCodeFeature'));

/**
 * WorkspaceModule 組件
 * 
 * 工作區模組的主要容器，負責：
 * 1. 提供工作區專用的狀態管理
 * 2. 管理子功能的路由
 * 3. 渲染工作區佈局
 */
export const WorkspaceModule: React.FC = () => {
  const { state } = useNavigation();

  return (
    <WorkspaceProvider workspaceId={state.selectedWorkspaceId || undefined}>
      <WorkspaceShell>
        <Routes>
          {/* 預設重定向到檔案管理 */}
          <Route path="/" element={<Navigate to="file-management" replace />} />
          
          {/* 檔案管理 */}
          <Route path="/file-management/*" element={
            <React.Suspense fallback={<div>載入檔案管理...</div>}>
              <FileManagement />
            </React.Suspense>
          } />
          
          {/* 版本控制 */}
          <Route path="/version-control/*" element={
            <React.Suspense fallback={<div>載入版本控制...</div>}>
              <VersionControl />
            </React.Suspense>
          } />

          {/* OpenSpec */}
          <Route path="/openspec" element={<Navigate to="/workspaces/openspec/in-progress" replace />} />
          <Route path="/openspec/*" element={<div />} />
          
          {/* 工作區設定 */}
          <Route path="/workspace-settings/*" element={
            <React.Suspense fallback={<div>載入工作區設定...</div>}>
              <WorkspaceSettings />
            </React.Suspense>
          } />
          
          {/* 容器管理 */}
          <Route path="/container-management/*" element={
            <React.Suspense fallback={<div>載入容器管理...</div>}>
              <ContainerManagement />
            </React.Suspense>
          } />
          
          {/* 工作區自動化 */}
          <Route path="/workspace-automation/*" element={
            <React.Suspense fallback={<div>載入自動化任務...</div>}>
              <WorkspaceAutomation />
            </React.Suspense>
          } />
          
          {/* Claude Code 設定 */}
          <Route path="/claude-code/*" element={
            <React.Suspense fallback={<div>載入 Claude Code 設定...</div>}>
              <ClaudeCode />
            </React.Suspense>
          } />
          <Route path="/claude-code-settings/*" element={<Navigate to="/workspaces/claude-code/settings" replace />} />
          
          {/* 預覽功能 - 由 WorkspaceShell 處理 */}
          <Route path="/preview/*" element={<div />} />

          {/* 404 */}
          <Route path="*" element={<div>功能不存在</div>} />
        </Routes>
      </WorkspaceShell>
    </WorkspaceProvider>
  );
};

export default WorkspaceModule;
