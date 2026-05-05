/**
 * WorkspaceShell - workspace module shell.
 * Keeps the original four-column layout and interaction model.
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
import { GlobalNavigation } from '@/app/components/navigation/GlobalNavigation';
import { RuntimeErrorPage } from '@/shared/components/errors/RuntimeErrorPage';
import { getNavigationItems } from './navigation-constants';
import { normalizeAgentType, getAgentToolConfig } from '../features/agent-settings/utils';
import { useI18n } from '@/shared/hooks/useI18n';
import { WorkspaceRealtimeProvider } from '../realtime';
import type { AgentSelectedFile } from '../features/agent-settings/types';
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

const AgentFileManager = React.lazy(() =>
  import('../features/agent-settings/components/AgentFileManager'),
);

const AgentDocumentSidebar = React.lazy(() =>
  import('../features/agent-settings/components/AgentDocumentSidebar'),
);

const CodexDocumentSidebar = React.lazy(() =>
  import('../features/agent-settings/components/CodexDocumentSidebar'),
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
  import('../features/canvas/SessionResultFeature').then((module) => ({
    default: module.SessionResultFeature,
  })),
);

const WebCanvasFeature = React.lazy(() =>
  import('../features/canvas/WebCanvasFeature').then((module) => ({
    default: module.WebCanvasFeature,
  })),
);

const BrowserFeature = React.lazy(() =>
  import('../features/canvas').then((module) => ({
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
  const [skillSelectedFile, setSkillSelectedFile] = useState<AgentSelectedFile | null>(null);
  const [codexDocumentSelectedId, setCodexDocumentSelectedId] = useState<string | null>(null);
  const resolveDeleteFallback = useWorkspaceDeleteFallback();

  // Drag resize handler.
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
        // Calculate the total width of the other columns.
        const sidebarWidth = state.sidebarCollapsed ? 64 : state.sidebarWidth;
        const secondColumnWidth = state.secondColumnCollapsed ? 64 : state.secondColumnWidth;
        const mainContentMinWidth = 400; // Minimum main content width.
        const otherColumnsWidth = sidebarWidth + secondColumnWidth + mainContentMinWidth;

        // Calculate the max width from the viewport minus other columns.
        const maxWidth = Math.max(window.innerWidth - otherColumnsWidth - 16, 360);

        // Clamp between min and max width.
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

  // Resolve the active view mode.
  const cliType = normalizeAgentType(workspaceRuntime.cliType);
  const navigationItems = React.useMemo(() => getNavigationItems(cliType), [cliType]);
  const currentItem = navigationItems.find(item => item.id === state.currentFeature);

  // Claude Code subviews that use four-column mode.
  const isSlashCommandsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'slash-commands';
  const isOutputStylesView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'output-styles';
  const isSubagentsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'subagents';
  const isSkillsView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'skills';
  const isMemoryView = state.currentFeature === 'claude-code' && state.claudeCodeSettings.subView === 'memory';

  // Other agent tool subviews that use four-column mode.
  const AGENT_TOOL_FEATURES = ['gemini', 'opencode', 'codex'] as const;
  const isAgentToolFeatureActive = (AGENT_TOOL_FEATURES as readonly string[]).includes(state.currentFeature);
  const isCodexDocumentView = state.currentFeature === 'codex'
    && (state.agentToolSettings.subView === 'subagents'
      || state.agentToolSettings.subView === 'prompts'
      || state.agentToolSettings.subView === 'rules');
  const isAgentToolFourColumn = isAgentToolFeatureActive && (
    state.agentToolSettings.subView === 'skills'
    || isCodexDocumentView
    || (cliType === 'gemini' && (state.agentToolSettings.subView === 'slash-commands' || state.agentToolSettings.subView === 'subagents'))
  );
  const isAgentToolSkillsView = isAgentToolFeatureActive && state.agentToolSettings.subView === 'skills';

  const isFourColumnView = isSlashCommandsView || isOutputStylesView || isSubagentsView || isSkillsView || isMemoryView || isAgentToolFourColumn;
  const isFileManagementEditorExpanded =
    state.currentFeature === 'file-management' && state.fileManagementEditorExpanded;

  useEffect(() => {
    if (!isSkillsView && !isAgentToolSkillsView) {
      setSkillSelectedFile(null);
    }
  }, [isAgentToolSkillsView, isSkillsView]);

  useEffect(() => {
    setCodexDocumentSelectedId(null);
  }, [state.currentFeature, state.agentToolSettings.subView]);

  // Determine whether the current mode is three-column.
  const isThreeColumn = currentItem?.mode === 'three-column' && !isFourColumnView;

  const isAgentSettingsFeature = state.currentFeature === 'claude-code' || isAgentToolFeatureActive;

  // Resolve second-column content for the active feature.
  const getSecondColumnContent = () => {
    if (state.currentFeature === 'file-management') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {t('workspace.layout.loading.fileTree')}
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
              {t('workspace.layout.loading.versionControlSidebar')}
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
                {t('workspace.layout.loading.openspecCustomization')}
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
              {t('workspace.layout.loading.openspecNavigation')}
            </div>
          }
        >
          <OpenSpecSidebar />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'claude-code') {
      const subView = state.claudeCodeSettings.subView;
      const cliConfig = getAgentToolConfig('claude');
      if (subView === 'skills') {
        if (!workspaceRuntime.workspaceId) {
          return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {workspaceRuntime.isLoading ? t('workspace.layout.loading.workspace') : t('workspace.layout.loading.workspaceUnavailable')}
            </div>
          );
        }
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {t('workspace.layout.loading.skillsTree')}
              </div>
            }
          >
            <AgentFileManager
              config={cliConfig}
              collectionType="skills"
              onSelect={setSkillSelectedFile}
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
                {t('workspace.layout.loading.claudeSidebar')}
              </div>
            }
          >
            <MarkdownSidebar subView={subView} />
          </React.Suspense>
        );
      }
    }

    // Second column for other agent tools.
    if (isAgentToolFeatureActive) {
      const subView = state.agentToolSettings.subView;
      if (state.currentFeature === 'codex' && (subView === 'subagents' || subView === 'prompts' || subView === 'rules')) {
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {t('workspace.layout.loading.agentSettings')}
              </div>
            }
          >
            <CodexDocumentSidebar
              resource={subView}
              selectedId={codexDocumentSelectedId}
              onSelect={setCodexDocumentSelectedId}
            />
          </React.Suspense>
        );
      }
      if (cliType === 'gemini' && (subView === 'slash-commands' || subView === 'subagents')) {
        const cliConfig = getAgentToolConfig(cliType);
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {t('workspace.layout.loading.agentSettings')}
              </div>
            }
          >
            <AgentDocumentSidebar
              resource={subView}
              selectedId={codexDocumentSelectedId}
              onSelect={setCodexDocumentSelectedId}
              apiPrefix={cliConfig.apiPathPrefix}
              availableScopes={subView === 'slash-commands'
                ? cliConfig.capabilities.slashCommands?.scopes
                : cliConfig.capabilities.agentDefinitions?.scopes}
            />
          </React.Suspense>
        );
      }
      if (subView === 'skills') {
        const cliConfig = getAgentToolConfig(cliType);
        if (!workspaceRuntime.workspaceId) {
          return (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {workspaceRuntime.isLoading ? t('workspace.layout.loading.workspace') : t('workspace.layout.loading.workspaceUnavailable')}
            </div>
          );
        }
        return (
          <React.Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {t('workspace.layout.loading.skillsTree')}
              </div>
            }
          >
            <AgentFileManager
              config={cliConfig}
              collectionType="skills"
              onSelect={setSkillSelectedFile}
              workspaceId={workspaceRuntime.workspaceId}
            />
          </React.Suspense>
        );
      }
    }

    // Other features can add second-column content here.
    return null;
  };

  // Resolve third-column content for the active feature.
  const getThirdColumnContent = () => {
    if (state.currentFeature === 'version-control') {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {t('workspace.layout.loading.versionControlContent')}
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
              {t('workspace.layout.loading.workspaceSettings')}
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
                {t('workspace.layout.loading.openspecCustomizationEditor')}
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
              {t('workspace.layout.loading.openspecDocuments')}
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
              {t('workspace.layout.loading.containerManagement')}
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
              {t('workspace.layout.loading.automationTasks')}
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
              {t('workspace.layout.loading.claudeSettings')}
            </div>
          }
        >
          <ClaudeCodeFeature
            subView={state.claudeCodeSettings.subView}
            skillSelectedFile={skillSelectedFile}
            onSkillSelect={setSkillSelectedFile}
          />
        </React.Suspense>
      );
    }
    if (isAgentToolFeatureActive) {
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {t('workspace.layout.loading.agentSettings')}
            </div>
          }
        >
          <AgentSettingsFeature
            cliType={cliType}
            subView={state.agentToolSettings.subView}
            skillSelectedFile={skillSelectedFile}
            onSkillSelect={setSkillSelectedFile}
            documentSelectedId={codexDocumentSelectedId}
            onDocumentSelect={setCodexDocumentSelectedId}
          />
        </React.Suspense>
      );
    }
    if (state.currentFeature === 'canvas') {
      const subView = state.canvas.subView;
      return (
        <React.Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {t('workspace.canvas.header.loading')}
            </div>
          }
        >
          {subView === 'session-result' ? (
            <SessionResultFeature />
          ) : (
            <WebCanvasFeature />
          )}
        </React.Suspense>
      );
    }
    // Other features can add third-column content here.
    return null;
  };

  // Render the shell content area.
  const renderContent = () => {
    const mainColumns = (
      <>
        {/* First column: feature navigation list. */}
        <div className={`bg-background border-r border-border transition-all duration-300 ${(state.chatExpanded || isFileManagementEditorExpanded) ? 'hidden' : ''
          } flex flex-col relative`}
          style={{
            width: state.sidebarCollapsed ? '64px' : `${state.sidebarWidth}px`
          }}>
          <WorkspaceSidebar />

          {/* Resize divider for the left navigation. */}
          {!state.sidebarCollapsed && (
            <div
              className={`absolute top-0 right-0 w-1 h-full cursor-col-resize transition-colors ${isDragging === 'sidebar' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
                }`}
              onMouseDown={(e) => handleMouseDown(e, 'sidebar')}
            />
          )}
        </div>

        {/* Second column: feature-specific content for selected layout modes. */}
        {(!isThreeColumn || isFourColumnView) && !isFileManagementEditorExpanded && (
          <div
            data-testid="workspace-second-column"
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

            {/* Resize divider for the second column. */}
            {!state.secondColumnCollapsed && (
              <div
                className={`absolute top-0 right-0 w-1 h-full cursor-col-resize transition-colors ${isDragging === 'secondColumn' ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20'
                  }`}
                onMouseDown={(e) => handleMouseDown(e, 'secondColumn')}
              />
            )}
          </div>
        )}

        <div
          data-testid="workspace-third-column"
          className="bg-background border-r border-border transition-all duration-300 flex flex-col relative"
          style={{ flex: '1 1 0', minWidth: isFileManagementEditorExpanded ? '0' : '400px' }}
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
      </>
    );

    const wrappedMainColumns = state.currentFeature === 'version-control' ? (
      <React.Suspense
        fallback={
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            {t('workspace.layout.loading.versionControl')}
          </div>
        }
      >
        <VersionControlContainer>{mainColumns}</VersionControlContainer>
      </React.Suspense>
    ) : (
      mainColumns
    );

    return (
      <div className="flex flex-1 w-full overflow-hidden layout-container relative">
        <div className={state.chatExpanded ? 'hidden' : 'contents'}>
          {wrappedMainColumns}
        </div>
        <div
          className={`bg-background transition-all duration-300 relative ${isFileManagementEditorExpanded
            ? 'hidden'
            : state.chatExpanded
            ? 'fixed inset-0 z-40'
            : `flex-shrink-0 ${state.rightChatCollapsed ? 'w-12' : ''}`
            }`}
          style={state.chatExpanded
            ? undefined
            : { width: state.rightChatCollapsed ? '48px' : `${state.rightChatWidth}px` }}
        >
          <ChatPanel />
        </div>
      </div>
    );
  };

  // Retry runtime connection after an error.
  const handleRetryConnection = useCallback(async () => {
    await workspaceRuntime.reload();
  }, [workspaceRuntime]);

  // Create a new workspace.
  const handleCreateWorkspace = useCallback(() => {
    navigate('/workspaces/workspace-wizard');
  }, [navigate]);

  // Delete the current workspace.
  const { toast } = useToast();
  const handleDeleteWorkspace = useCallback(async () => {
    if (!workspaceRuntime.workspaceId) {
      return;
    }

    // Confirmation dialog.
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
      logger.error('deleteWorkspaceFailed', { error });
      toast({
        title: t('workspace.workspaceSettings.reset.delete.error.title'),
        description: error instanceof Error ? error.message : t('workspace.workspaceSettings.reset.delete.error.description'),
        variant: 'destructive',
      });
    }
  }, [resolveDeleteFallback, t, toast, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  // Show the runtime error page when runtime failed and is not loading.
  const shouldShowRuntimeError = workspaceRuntime.error &&
    !workspaceRuntime.isLoading &&
    !workspaceRuntime.runtimeBaseUrl;

  if (shouldShowRuntimeError) {
    return (
      <div className="h-screen w-screen flex flex-col bg-background">
        {/* Header keeps GlobalNavigation at the top. */}
        <GlobalNavigation />

        {/* Runtime error page. */}
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
      <ClaudeCodeProvider
        isActive={isAgentSettingsFeature}
        activeSubView={state.currentFeature === 'claude-code' ? state.claudeCodeSettings.subView : null}
      >
        <ChatPanelStateProvider>
          <OpenSpecWorkspaceProvider>
            <div className="h-screen w-screen flex flex-col bg-background">
              {/* Hide the header when the file editor expands so the third column fills the screen. */}
              {!isFileManagementEditorExpanded && <GlobalNavigation />}

              {/* Main layout area fills the remaining space. */}
              {renderContent()}
            </div>
          </OpenSpecWorkspaceProvider>
        </ChatPanelStateProvider>
      </ClaudeCodeProvider>
    </WorkspaceRealtimeProvider>
  );
};

export default WorkspaceShell;
