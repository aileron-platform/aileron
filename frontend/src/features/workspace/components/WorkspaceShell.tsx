/**
 * WorkspaceShell - 工作區模組專用外殼
 * 保留原始設計的四欄佈局與互動邏輯
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { ChevronLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { WorkspaceSidebar } from './WorkspaceSidebar';
import { ClaudeCodeProvider } from '../features/claude-code/components';
import { OpenSpecWorkspaceProvider } from '../features/openspec/OpenSpecWorkspaceContext';
import ChatPanel from './ChatPanel/ChatPanel';
import { ChatPanelStateProvider } from './ChatPanel/chatPanelStateContext';
import { GlobalNavigation } from '@/shared/components/navigation/GlobalNavigation';
import { RuntimeErrorPage } from '@/shared/components/errors/RuntimeErrorPage';
import { getNavigationItems } from './navigation-constants';
import { normalizeAgentType, getAgentToolConfig } from '../features/agent-settings/utils';
import { useI18n } from '@/shared/hooks/useI18n';
import { WorkspaceRealtimeProvider } from '../realtime';
import type { SelectedFile } from '../features/claude-code/components/ClaudeCodeFileManager';
import { workspaceLifecycleApi } from '../services/workspaceLifecycleApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { createLogger } from '@/shared/services/logger';
import { useWorkspaceDeleteFallback } from '../hooks/useWorkspaceDeleteFallback';

const logger = createLogger('WorkspaceShell');

const FileManagementView = React.lazy(() =>
  import('../features/file-management/components/FileManagementView').then((module) => ({
    default: module.FileManagementView,
  })),
);

const FileManagementFeature = React.lazy(() =>
  import('../features/file-management/FileManagementFeature').then((module) => ({
    default: module.FileManagementFeature,
  })),
);

const VersionControlSidebar = React.lazy(() =>
  import('../features/version-control/VersionControlFeature').then((module) => ({
    default: module.VersionControlFeature.Sidebar,
  })),
);

const VersionControlMainContent = React.lazy(() =>
  import('../features/version-control/VersionControlFeature').then((module) => ({
    default: module.VersionControlFeature.MainContent,
  })),
);

const VersionControlContainer = React.lazy(() =>
  import('../features/version-control/VersionControlFeature').then((module) => ({
    default: module.VersionControlFeature.Container,
  })),
);

const WorkspaceSettingsMainContent = React.lazy(() =>
  import('../features/workspace-settings/WorkspaceSettingsFeature').then((module) => ({
    default: module.WorkspaceSettingsFeature.MainContent,
  })),
);

const ContainerManagementMainContent = React.lazy(() =>
  import('../features/container-management/ContainerManagementFeature').then((module) => ({
    default: module.ContainerManagementFeature.MainContent,
  })),
);

const WorkspaceAutomationMainContent = React.lazy(() =>
  import('../features/workspace-automation/WorkspaceAutomationFeature'),
);

const ClaudeCodeFeature = React.lazy(() =>
  import('../features/claude-code/ClaudeCodeFeature'),
);

const AgentSettingsFeature = React.lazy(() =>
  import('../features/agent-settings/AgentSettingsFeature'),
);

const MarkdownSidebar = React.lazy(() =>
  import('../features/claude-code/components').then((module) => ({
    default: module.MarkdownSidebar,
  })),
);

const ClaudeCodeFileManager = React.lazy(() =>
  import('../features/claude-code/components/ClaudeCodeFileManager'),
);

const OpenSpecSidebar = React.lazy(() =>
  import('../features/openspec/components/OpenSpecSidebar'),
);

const OpenSpecCustomizationSidebar = React.lazy(() =>
  import('../features/openspec/components/OpenSpecCustomizationSidebar'),
);

const OpenSpecCustomizationFeature = React.lazy(() =>
  import('../features/openspec/components/OpenSpecCustomizationFeature'),
);



const SessionResultFeature = React.lazy(() =>
  import('../features/preview/SessionResultFeature').then((module) => ({
    default: module.SessionResultFeature,
  })),
);

const WebPreviewFeature = React.lazy(() =>
  import('../features/preview/WebPreviewFeature').then((module) => ({
    default: module.WebPreviewFeature,
  })),
);

const BrowserFeature = React.lazy(() =>
  import('../features/preview').then((module) => ({
    default: module.BrowserFeature,
  })),
);

interface WorkspaceShellProps {
  children: React.ReactNode;
  secondColumn?: React.ReactNode;
}

export const WorkspaceShell: React.FC<WorkspaceShellProps> = ({ children, secondColumn }) => {
  const { state, dispatch, workspaceRuntime } = useWorkspace();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [isDragging, setIsDragging] = useState<string | null>(null);
  const dragStateRef = useRef<{
    type: 'sidebar' | 'secondColumn' | 'rightChat';
    startX: number;
    startWidth: number;
  } | null>(null);
  const [skillSelectedFile, setSkillSelectedFile] = useState<SelectedFile | null>(null);
  const [scriptSelectedFile, setScriptSelectedFile] = useState<SelectedFile | null>(null);
  const resolveDeleteFallback = useWorkspaceDeleteFallback();

  // 拖曳處理函數
  const handleMouseDown = useCallback((e: React.MouseEvent, type: 'sidebar' | 'secondColumn' | 'rightChat') => {
    e.preventDefault();
    const startWidth =
      type === 'sidebar'
        ? state.sidebarWidth
        : type === 'secondColumn'
          ? state.secondColumnWidth
          : state.rightChatWidth;

    dragStateRef.current = {
      type,
      startX: e.clientX,
      startWidth,
    };
    setIsDragging(type);
  }, [state.sidebarWidth, state.secondColumnWidth, state.rightChatWidth]);

  useEffect(() => {
    if (!isDragging) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = dragStateRef.current;
      if (!dragState) {
        return;
      }
      const deltaX = event.clientX - dragState.startX;

      if (dragState.type === 'sidebar') {
        const newWidth = Math.max(dragState.startWidth + deltaX, 200);
        dispatch({ type: 'SET_SIDEBAR_WIDTH', payload: newWidth });
      } else if (dragState.type === 'secondColumn') {
        const newWidth = Math.max(dragState.startWidth + deltaX, 250);
        dispatch({ type: 'SET_SECOND_COLUMN_WIDTH', payload: newWidth });
      } else if (dragState.type === 'rightChat') {
        // 計算其他欄位的總寬度
        const sidebarWidth = state.sidebarCollapsed ? 64 : state.sidebarWidth;
        const secondColumnWidth = state.secondColumnCollapsed ? 64 : state.secondColumnWidth;
        const mainContentMinWidth = 400; // 主內容區最小寬度
        const otherColumnsWidth = sidebarWidth + secondColumnWidth + mainContentMinWidth;

        // 計算最大寬度（視窗寬度減去其他欄位，並保留一些邊距）
        const maxWidth = Math.max(window.innerWidth - otherColumnsWidth - 16, 360);

        // 限制在最小和最大寬度之間
        const newWidth = Math.max(
          Math.min(dragState.startWidth - deltaX, maxWidth),
          360
        );
        dispatch({ type: 'SET_RIGHT_CHAT_WIDTH', payload: newWidth });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(null);
      dragStateRef.current = null;
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      dragStateRef.current = null;
    };
  }, [isDragging, dispatch]);

  // 根據原始邏輯判斷當前視圖模式
  const cliType = normalizeAgentType(workspaceRuntime.cliType);
  const navigationItems = React.useMemo(() => getNavigationItems(cliType), [cliType]);
  const currentItem = navigationItems.find(item => item.id === state.currentFeature);

  // Claude Code 設定中的特殊子視圖是四欄模式
  const isSlashCommandsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'slash-commands';
  const isOutputStylesView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'output-styles';
  const isSubagentsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'subagents';
  const isSkillsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'skills';
  const isScriptsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'scripts';
  const isMemoryView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'memory';

  // 其他 Agent 工具的四欄子視圖
  const AGENT_TOOL_FEATURES = ['gemini', 'opencode', 'codex'] as const;
  const isAgentToolFeatureActive = (AGENT_TOOL_FEATURES as readonly string[]).includes(state.currentFeature);
  const isAgentToolFourColumn = isAgentToolFeatureActive && ['slash-commands', 'skills'].includes(state.agentToolSettings.subView);

  const isFourColumnView = isSlashCommandsView || isOutputStylesView || isSubagentsView || isSkillsView || isScriptsView || isMemoryView || isAgentToolFourColumn;

  useEffect(() => {
    if (!isSkillsView) {
      setSkillSelectedFile(null);
    }
  }, [isSkillsView]);

  useEffect(() => {
    if (!isScriptsView) {
      setScriptSelectedFile(null);
    }
  }, [isScriptsView]);

  // 判斷是否為三欄模式
  const isThreeColumn = currentItem?.mode === 'three-column' && !isFourColumnView;

  const isAgentSettingsFeature = state.currentFeature === 'claude-code' || isAgentToolFeatureActive;

  // 根據當前功能決定第二欄內容
  const getSecondColumnContent = () => {
    if (state.currentFeature === 'file-management') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入檔案樹...
            </div>
          }
        >
          <FileManagementView />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'version-control') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入版本控制側欄...
            </div>
          }
        >
          <VersionControlSidebar />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'openspec') {
      if (state.openspec.subView === 'customization') {
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入 OpenSpec 自定流程...
              </div>
            }
          >
            <OpenSpecCustomizationSidebar />
          </React.Suspense>
        );
      }
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入 OpenSpec 導覽...
            </div>
          }
        >
          <OpenSpecSidebar />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'claude-code') {
      const subView = state.claudeCodeSettings.subView;
      if (subView === 'skills') {
        // 確保 workspaceId 存在才渲染 ClaudeCodeFileManager
        if (!workspaceRuntime.workspaceId) {
          return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {workspaceRuntime.isLoading ? '載入工作區...' : '無法載入工作區'}
            </div>
          );
        }
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入Skills檔案樹...
              </div>
            }
          >
            <ClaudeCodeFileManager
              collectionType="skills"
              onSelect={setSkillSelectedFile}
              workspaceId={workspaceRuntime.workspaceId}
            />
          </React.Suspense>
        );
      }

      if (subView === 'scripts') {
        // 確保 workspaceId 存在才渲染 ClaudeCodeFileManager
        if (!workspaceRuntime.workspaceId) {
          return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {workspaceRuntime.isLoading ? '載入工作區...' : '無法載入工作區'}
            </div>
          );
        }
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入Scripts檔案樹...
              </div>
            }
          >
            <ClaudeCodeFileManager
              collectionType="scripts"
              onSelect={setScriptSelectedFile}
              workspaceId={workspaceRuntime.workspaceId}
            />
          </React.Suspense>
        );
      }
      if (subView === 'slash-commands' || subView === 'output-styles' || subView === 'subagents' || subView === 'memory') {
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入 Claude Code 側欄...
              </div>
            }
          >
            <MarkdownSidebar subView={subView} />
          </React.Suspense>
        );
      }
    }

    // 其他 Agent 工具的第二欄
    if (isAgentToolFeatureActive) {
      const subView = state.agentToolSettings.subView;
      if (subView === 'skills') {
        if (!workspaceRuntime.workspaceId) {
          return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {workspaceRuntime.isLoading ? '載入工作區...' : '無法載入工作區'}
            </div>
          );
        }
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入Skills檔案樹...
              </div>
            }
          >
            <ClaudeCodeFileManager
              collectionType="skills"
              onSelect={setSkillSelectedFile}
              workspaceId={workspaceRuntime.workspaceId}
            />
          </React.Suspense>
        );
      }
      if (subView === 'slash-commands') {
        const cliConfig = getAgentToolConfig(cliType);
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入側欄...
              </div>
            }
          >
            <MarkdownSidebar subView={subView} availableScopes={cliConfig.availableScopes} />
          </React.Suspense>
        );
      }
    }

    // 其他功能的第二欄內容可以在這裡添加
    return null;
  };

  // 根據當前功能決定第三欄內容
  const getThirdColumnContent = () => {
    if (state.currentFeature === 'version-control') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入版本控制內容...
            </div>
          }
        >
          <VersionControlMainContent />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'workspace-settings') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入工作區設定...
            </div>
          }
        >
          <WorkspaceSettingsMainContent />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'openspec') {
      if (state.openspec.subView === 'customization') {
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                載入 OpenSpec 自定流程編輯器...
              </div>
            }
          >
            <OpenSpecCustomizationFeature />
          </React.Suspense>
        );
      }
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入 OpenSpec 文件...
            </div>
          }
        >
          <FileManagementFeature />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'container-management') {
      const subView = state.containerManagement.subView;
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入容器管理...
            </div>
          }
        >
          {subView === 'browser' ? (
            <BrowserFeature />
          ) : (
            <ContainerManagementMainContent />
          )}
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'workspace-automation') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入自動化任務...
            </div>
          }
        >
          <WorkspaceAutomationMainContent />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'claude-code') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入 Claude Code 設定...
            </div>
          }
        >
          <ClaudeCodeFeature
            subView={state.claudeCodeSettings.subView}
            skillSelectedFile={skillSelectedFile}
            onSkillSelect={setSkillSelectedFile}
            scriptSelectedFile={scriptSelectedFile}
            onScriptSelect={setScriptSelectedFile}
          />
        </React.Suspense>
      );
    }
    if (isAgentToolFeatureActive) {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入 Agent 設定...
            </div>
          }
        >
          <AgentSettingsFeature
            cliType={cliType}
            subView={state.agentToolSettings.subView}
          />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'preview') {
      const subView = state.preview.subView;
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              載入預覽功能...
            </div>
          }
        >
          {subView === 'session-result' ? (
            <SessionResultFeature />
          ) : (
            <WebPreviewFeature />
          )}
        </React.Suspense>
      );
    }
    // 其他功能的第三欄內容可以在這裡添加
    return null;
  };

  // 渲染內容區域
  const renderContent = () => {
    if (state.chatExpanded) {
      return (
        <div className="fixed inset-0 z-40 flex bg-background overflow-hidden">
          <div className="flex-1 overflow-hidden max-w-full">
            <ChatPanel />
          </div>
        </div>
      );
    }

    return (
      <div className="flex flex-1 w-full overflow-hidden layout-container relative">
        {/* 第一欄：功能導航列表 */}
        <div className={`bg-background border-r border-border transition-all duration-300 ${state.chatExpanded ? 'hidden' : ''
          } flex flex-col relative`}
          style={{
            width: state.sidebarCollapsed ? '64px' : `${state.sidebarWidth}px`
          }}>
          <WorkspaceSidebar />

          {/* 拖拽分隔線 - 左側導航 */}
          {!state.sidebarCollapsed && (
            <div
              className={`absolute top-0 right-0 w-1 h-full cursor-col-resize transition-colors ${isDragging === 'sidebar' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
                }`}
              onMouseDown={(e) => handleMouseDown(e, 'sidebar')}
            />
          )}
        </div>

        {/* 第二欄：功能特定內容（四欄模式或三欄模式的特定情況顯示） */}
        {(!isThreeColumn || isFourColumnView) && (
          <div
            className="bg-background border-r border-border overflow-hidden flex flex-col transition-all duration-300 relative"
            style={{
              width: state.secondColumnCollapsed ? '64px' : `${state.secondColumnWidth}px`,
              minWidth: state.secondColumnCollapsed ? '64px' : '250px'
            }}
          >
            <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
              {secondColumn || getSecondColumnContent() || (
                <div className="h-full flex flex-col">
                  <div className={`h-10 px-3 border-b border-border bg-card flex items-center ${state.secondColumnCollapsed ? 'justify-center' : 'justify-between'}`}>
                    {!state.secondColumnCollapsed && (
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-foreground">{t('workspace.layout.panelTitle')}</h3>
                      </div>
                    )}
                    <button
                      onClick={() => {
                        dispatch({ type: 'TOGGLE_SECOND_COLUMN' });
                      }}
                      className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground"
                      title={state.secondColumnCollapsed ? t('workspace.layout.expandSidebar') : t('workspace.layout.collapseSidebar')}
                    >
                      <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${state.secondColumnCollapsed ? 'rotate-180' : ''}`} />
                    </button>
                  </div>
                  <div className="flex-1 p-3">
                    <div className="text-xs text-muted-foreground">{t('workspace.layout.emptyHint')}</div>
                  </div>
                </div>
              )}
            </div>

            {/* 拖拽分隔線 - 第二欄 */}
            {!state.secondColumnCollapsed && (
              <div
                className={`absolute top-0 right-0 w-1 h-full cursor-col-resize transition-colors ${isDragging === 'secondColumn' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
                  }`}
                onMouseDown={(e) => handleMouseDown(e, 'secondColumn')}
              />
            )}
          </div>
        )}

        {/* 第三欄：主要內容區域 */}
        {state.chatExpanded ? (
          <div className="flex flex-1">
            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="flex-1 overflow-hidden">
                {getThirdColumnContent() || children}
              </div>
            </div>
            <div className="w-full max-w-5xl border-l border-border bg-background">
              <ChatPanel />
            </div>
          </div>
        ) : (
          <>
            <div
              className="bg-background border-r border-border transition-all duration-300 flex flex-col relative"
              style={{ flex: '1 1 0', minWidth: '400px' }}
            >
              <div className="flex-1 overflow-hidden flex flex-col">
                <div className="flex-1 overflow-hidden">
                  {getThirdColumnContent() || children}
                </div>
              </div>
              {!state.rightChatCollapsed && (
                <div
                  className={`absolute top-0 right-0 w-1 h-full cursor-col-resize transition-colors ${isDragging === 'rightChat' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
                    }`}
                  onMouseDown={(e) => handleMouseDown(e, 'rightChat')}
                />
              )}
            </div>
            <div
              className={`bg-background transition-all duration-300 relative flex-shrink-0 ${state.rightChatCollapsed ? 'w-12' : ''
                }`}
              style={{ width: state.rightChatCollapsed ? '48px' : `${state.rightChatWidth}px` }}
            >
              <ChatPanel />
            </div>
          </>
        )}
      </div>
    );
  };

  // 處理 Runtime 錯誤時的重試邏輯
  const handleRetryConnection = useCallback(async () => {
    await workspaceRuntime.reload();
  }, [workspaceRuntime]);

  // 處理建立新工作區
  const handleCreateWorkspace = useCallback(() => {
    navigate('/workspaces/workspace-wizard');
  }, [navigate]);

  // 處理刪除工作區
  const { toast } = useToast();
  const handleDeleteWorkspace = useCallback(async () => {
    if (!workspaceRuntime.workspaceId) {
      return;
    }

    // 確認對話框
    const confirmMessage = t('common.error.workspaceRuntime.deleteConfirmMessage');
    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      const deletedWorkspaceId = workspaceRuntime.workspaceId;
      const deletedRuntimeBaseUrl = workspaceRuntime.runtimeBaseUrl;

      await workspaceLifecycleApi.deleteWorkspace(deletedWorkspaceId);
      await resolveDeleteFallback({
        deletedWorkspaceId,
        deletedRuntimeBaseUrl,
      });

      toast({
        title: t('workspace.workspaceSettings.reset.delete.success.title'),
        description: t('workspace.workspaceSettings.reset.delete.success.description'),
        variant: 'default',
      });
    } catch (error) {
      logger.error('刪除工作區失敗', { error });
      toast({
        title: t('workspace.workspaceSettings.reset.delete.error.title'),
        description: error instanceof Error ? error.message : t('workspace.workspaceSettings.reset.delete.error.description'),
        variant: 'destructive',
      });
    }
  }, [resolveDeleteFallback, t, toast, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  // 如果有 runtime 錯誤且不在載入狀態，顯示錯誤頁面
  const shouldShowRuntimeError = workspaceRuntime.error &&
    !workspaceRuntime.isLoading &&
    !workspaceRuntime.runtimeBaseUrl;

  if (shouldShowRuntimeError) {
    return (
      <div className="h-screen w-screen flex flex-col bg-background">
        {/* Header - 保持 GlobalNavigation 在頂部 */}
        <GlobalNavigation />

        {/* Runtime 錯誤頁面 */}
        <RuntimeErrorPage
          error={workspaceRuntime.error!}
          isLoading={workspaceRuntime.isLoading}
          onRetry={handleRetryConnection}
          onCreateWorkspace={handleCreateWorkspace}
          onDeleteWorkspace={handleDeleteWorkspace}
          workspaceId={workspaceRuntime.workspaceId}
        />
      </div>
    );
  }

  logger.debug('Rendering with workspaceRuntime', {
    workspaceId: workspaceRuntime.workspaceId,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    terminalExternalUrl: workspaceRuntime.terminalExternalUrl,
  });

  return (
    <WorkspaceRealtimeProvider
      workspaceId={workspaceRuntime.workspaceId}
      runtimeBaseUrl={workspaceRuntime.runtimeBaseUrl}
      terminalExternalUrl={workspaceRuntime.terminalExternalUrl}
    >
      <ClaudeCodeProvider isActive={isAgentSettingsFeature}>
        <ChatPanelStateProvider>
          <OpenSpecWorkspaceProvider>
            <div className="h-screen w-screen flex flex-col bg-background">
              {/* Header - 保持與原始設計完全相同 */}
              <GlobalNavigation />

              {/* 主要Layout區域 - 填滿剩餘空間 */}
              {state.currentFeature === 'version-control' ? (
                <React.Suspense
                  fallback={
                    <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                      載入版本控制...
                    </div>
                  }
                >
                  <VersionControlContainer>{renderContent()}</VersionControlContainer>
                </React.Suspense>
              ) : (
                renderContent()
              )}
            </div>
          </OpenSpecWorkspaceProvider>
        </ChatPanelStateProvider>
      </ClaudeCodeProvider>
    </WorkspaceRealtimeProvider>
  );
};

export default WorkspaceShell;
