import React, { useCallback, useMemo, useState } from 'react';
import { FileCode2, Folder, GitBranch, Navigation, Settings2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  ProductShell,
  type ProductShellBody,
  type ProductShellColumnRegion,
  type ProductShellCompanionRegion,
  type ProductShellPreferencesAdapter,
} from '@/shared/components/shell';
import { useI18n } from '@/shared/hooks/useI18n';
import { VersionControlRefreshButton } from '@/shared/components/version-control';
import { WorkspaceRealtimeProvider } from '../realtime/WorkspaceRealtimeProvider';
import { useWorkspace } from '../providers/WorkspaceProvider';
import type { AgentSelectedFile } from '../features/agent-settings/model/documents';
import { WorkspaceSidebar } from './WorkspaceSidebar';
import {
  WorkspaceCompanionCollapsedContent,
  WorkspaceCompanionColumn,
  WorkspaceCompanionHeader,
} from './WorkspaceCompanionColumn';
import { WorkspaceFeatureContent } from './WorkspaceFeatureContent';
import { WorkspaceFeatureLoading } from '../components/WorkspaceFeatureLoading';
import { useWorkspaceDocumentSelection } from './hooks/useWorkspaceDocumentSelection';
import { useOptionalWorkspaceAiChatSelection } from '../integrations/ai-chat/WorkspaceAiChatSelectionContext';
import { useWorkspaceVersionControlSession } from '../integrations/version-control/workspaceVersionControlSession';
import { resolveWorkspaceShellSurface } from './workspaceShellSurfaceModel';
import {
  WORKSPACE_SHELL_LAYOUT_DEFAULTS,
  WORKSPACE_SHELL_LAYOUT_LIMITS,
  workspaceShellLayoutStorage,
} from '../storage/workspaceShellLayoutStorage';
const VersionControlProvider = React.lazy(() =>
  import('../features/version-control/VersionControlPage').then((module) => ({
    default: module.VersionControlProvider,
  })),
);

export interface WorkspaceShellAdapterProps {
  children?: React.ReactNode;
  userId?: string;
  navigationSlot: React.ReactNode;
  stateContent?: React.ReactNode;
}

const createWorkspacePreferencesAdapter = (
  workspaceId: string | null,
): ProductShellPreferencesAdapter | undefined => {
  if (!workspaceId) {
    return undefined;
  }

  return {
    identity: `workspace:${workspaceId}`,
    load: () => {
      const stored = workspaceShellLayoutStorage.load(workspaceId);
      if (!stored) {
        return null;
      }
      return {
        navigation: {
          collapsed: stored.navSidebarCollapsed,
          width: stored.navSidebarWidth,
        },
        navigator: {
          collapsed: stored.secondColumnCollapsed,
          width: stored.secondColumnWidth,
        },
        companion: {
          collapsed: stored.companionCollapsed,
          width: stored.companionWidth,
          height: stored.companionHeight,
          placement: stored.companionPlacement,
        },
      };
    },
    save: (preferences) => {
      const defaults = WORKSPACE_SHELL_LAYOUT_DEFAULTS;
      workspaceShellLayoutStorage.save(workspaceId, {
        navSidebarCollapsed: preferences.navigation?.collapsed ?? defaults.navSidebarCollapsed,
        navSidebarWidth: preferences.navigation?.width ?? defaults.navSidebarWidth,
        secondColumnCollapsed: preferences.navigator?.collapsed ?? defaults.secondColumnCollapsed,
        secondColumnWidth: preferences.navigator?.width ?? defaults.secondColumnWidth,
        companionCollapsed: preferences.companion?.collapsed ?? defaults.companionCollapsed,
        companionWidth: preferences.companion?.width ?? defaults.companionWidth,
        companionHeight: preferences.companion?.height ?? defaults.companionHeight,
        companionPlacement: preferences.companion?.placement ?? defaults.companionPlacement,
      });
    },
  };
};

const navigationBehavior = {
  collapsible: true,
  resizable: true,
  defaultWidth: 240,
  minWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.navSidebarWidth.min,
  maxWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.navSidebarWidth.max,
} as const;

const navigatorBehavior = {
  collapsible: true,
  resizable: true,
  defaultWidth: 270,
  minWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.secondColumnWidth.min,
  maxWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.secondColumnWidth.max,
} as const;

const companionSideBehavior = {
  collapsible: true,
  resizable: true,
  defaultWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.companionWidth.min,
  minWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.companionWidth.min,
  maxWidth: WORKSPACE_SHELL_LAYOUT_LIMITS.companionWidth.max,
} as const;

const companionBottomBehavior = {
  defaultHeight: WORKSPACE_SHELL_LAYOUT_DEFAULTS.companionHeight,
  minHeight: WORKSPACE_SHELL_LAYOUT_LIMITS.companionHeight.min,
  maxHeight: WORKSPACE_SHELL_LAYOUT_LIMITS.companionHeight.max,
  mainMinHeight: 320,
} as const;

export const WorkspaceShellAdapter: React.FC<WorkspaceShellAdapterProps> = ({
  children,
  userId = 'anonymous',
  navigationSlot,
  stateContent,
}) => {
  const { state, dispatch, permissions, workspaceRuntime } = useWorkspace();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const surface = resolveWorkspaceShellSurface({ state, permissions, workspaceRuntime });
  const [skillSelectedFile, setSkillSelectedFile] = useState<AgentSelectedFile | null>(null);
  const [isVersionControlRefreshing, setIsVersionControlRefreshing] = useState(false);
  const versionControlSession = useWorkspaceVersionControlSession({
    workspaceId: workspaceRuntime.workspaceId ?? '',
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? '',
    contextId: state.versionControl.selectedGitContextId,
  });
  const companionRevealRequestId = useOptionalWorkspaceAiChatSelection()?.companionRevealRequestId ?? 0;
  const documentSelection = useWorkspaceDocumentSelection({
    currentFeature: state.currentFeature,
    agentToolSubView: state.agentToolSettings.subView,
  });
  const preferences = useMemo(
    () => createWorkspacePreferencesAdapter(workspaceRuntime.workspaceId),
    [workspaceRuntime.workspaceId],
  );

  React.useEffect(() => {
    if (!surface.isAgentToolSkillsView) {
      setSkillSelectedFile(null);
    }
  }, [surface.isAgentToolSkillsView]);

  const handleVersionControlRefresh = useCallback(async () => {
    if (!workspaceRuntime.workspaceId || isVersionControlRefreshing) {
      return;
    }

    setIsVersionControlRefreshing(true);
    try {
      await versionControlSession.refresh(queryClient, ['changes', 'history', 'remote']);
    } catch {
      // Individual query error states remain the visible failure surface.
    } finally {
      setIsVersionControlRefreshing(false);
    }
  }, [
    isVersionControlRefreshing,
    queryClient,
    versionControlSession,
    workspaceRuntime.workspaceId,
  ]);

  if (stateContent) {
    return <ProductShell topBar={navigationSlot} body={{ kind: 'state', content: stateContent }} />;
  }

  const renderFeature = (column: 'second' | 'main', collapsed: boolean) => (
    <WorkspaceFeatureContent
      column={column}
      fallback={column === 'main' ? children : undefined}
      activeAgentToolId={surface.activeAgentToolId}
      isAgentToolFeatureActive={surface.isAgentToolFeatureActive}
      skillSelectedFile={skillSelectedFile}
      onSkillSelect={setSkillSelectedFile}
      documentSelectedId={documentSelection.selectedId}
      onDocumentSelect={documentSelection.handleSelect}
      onDocumentDirtyChange={documentSelection.handleDirtyChange}
      documentSelectionBlocked={documentSelection.selectionBlocked}
      columnCollapsed={collapsed}
    />
  );

  const navigation: ProductShellColumnRegion = {
    content: ({ collapsed }) => <WorkspaceSidebar collapsed={collapsed} />,
    behavior: navigationBehavior,
    presentation: {
      accessibleLabel: t('workspace.sidebar.title'),
      chrome: 'navigation',
      responsive: 'always',
      header: {
        leading: <Navigation className="h-4 w-4 text-sidebar-primary" aria-hidden="true" />,
        title: t('workspace.sidebar.title'),
      },
    },
  };

  const navigatorHeader = (() => {
    if (state.currentFeature === 'file-management') {
      return {
        leading: <Folder className="h-4 w-4 text-primary" aria-hidden="true" />,
        title: t('workspace.fileManagement.view.treeTitle'),
      };
    }
    if (state.currentFeature === 'version-control') {
      return {
        leading: <GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />,
        title: state.versionControl?.subView === 'changes'
          ? t('workspace.versionControl.sidebar.title.changes')
          : t('workspace.versionControl.sidebar.title.history'),
        actions: (
          <VersionControlRefreshButton
            onRefresh={() => { void handleVersionControlRefresh(); }}
            isRefreshing={isVersionControlRefreshing}
            disabled={!workspaceRuntime.workspaceId}
          />
        ),
      };
    }
    if (surface.isAgentToolFeatureActive) {
      return {
        leading: <FileCode2 className="h-4 w-4 text-primary" aria-hidden="true" />,
        title: t('workspace.layout.panelTitle'),
      };
    }
    return {
      leading: <Settings2 className="h-4 w-4 text-primary" aria-hidden="true" />,
      title: t('workspace.layout.panelTitle'),
    };
  })();

  const navigator: ProductShellColumnRegion | undefined = surface.shouldRenderNavigator ? {
    content: ({ collapsed }) => renderFeature('second', collapsed),
    behavior: navigatorBehavior,
    presentation: {
      accessibleLabel: t('workspace.layout.panelTitle'),
      chrome: 'navigator-muted',
      responsive: 'always',
      header: navigatorHeader,
    },
  } : undefined;

  const companion: ProductShellCompanionRegion | undefined = surface.shouldRenderCompanion && surface.companionActiveTab ? {
    content: ({ placement }) => (
      <WorkspaceCompanionColumn
        workspaceId={workspaceRuntime.workspaceId ?? ''}
        userId={userId}
        activeTab={surface.companionActiveTab}
        canUseAgentChat={permissions.canUseChat}
        canUseTerminal={permissions.canUseTerminal}
        isExpanded={state.chatExpanded}
        terminalPlacement={placement === 'bottom' ? 'bottom' : surface.companionPlacement}
        onActiveTabChange={(tab) => dispatch({ type: 'SET_COMPANION_ACTIVE_TAB', payload: tab })}
        onTerminalPlacementChange={(nextPlacement) => dispatch({ type: 'SET_COMPANION_TERMINAL_PLACEMENT', payload: nextPlacement })}
        onToggleExpand={() => dispatch({ type: 'TOGGLE_CHAT_EXPANDED' })}
      />
    ),
    placement: surface.companionPlacement,
    side: companionSideBehavior,
    bottom: companionBottomBehavior,
    presentation: {
      accessibleLabel: t('aiChat.companion.tabs.label'),
      chrome: 'plain-compact-rail',
      header: surface.companionPlacement === 'bottom' && surface.companionActiveTab === 'terminal'
        ? undefined
        : {
          title: (
            <WorkspaceCompanionHeader
              activeTab={surface.companionActiveTab}
              canUseAgentChat={permissions.canUseChat}
              canUseTerminal={permissions.canUseTerminal}
              isExpanded={state.chatExpanded}
              onActiveTabChange={(tab) => dispatch({ type: 'SET_COMPANION_ACTIVE_TAB', payload: tab })}
              onToggleExpand={() => dispatch({ type: 'TOGGLE_CHAT_EXPANDED' })}
            />
          ),
        },
      collapsedContent: <WorkspaceCompanionCollapsedContent />,
      collapseLabel: t('aiChat.companion.collapse'),
      expandLabel: t('aiChat.companion.expand'),
      resizeLabel: t('aiChat.companion.resizeTerminalDock'),
    },
    revealRequestId: companionRevealRequestId,
  } : undefined;

  const body: ProductShellBody = {
    kind: 'regions',
    navigation,
    navigator,
    main: {
      accessibleLabel: t('workspace.layout.mainContent'),
      content: renderFeature('main', false),
    },
    companion,
  };
  const display = surface.isMainContentExpanded
    ? {
      mode: 'main-expanded' as const,
      onExit: () => {
        if (state.currentFeature === 'file-management') {
          dispatch({ type: 'TOGGLE_FILE_MANAGEMENT_EDITOR_EXPANDED' });
        } else {
          dispatch({ type: 'SET_MAIN_CONTENT_EXPANDED', payload: false });
        }
      },
    }
    : surface.isCompanionFullscreen
      ? { mode: 'companion-fullscreen' as const, onExit: () => dispatch({ type: 'TOGGLE_CHAT_EXPANDED' }) }
      : undefined;

  const shell = (
    <ProductShell
      topBar={navigationSlot}
      body={body}
      preferences={preferences}
      display={display}
    />
  );

  const withVersionControl = state.currentFeature === 'version-control' ? (
    <React.Suspense fallback={<WorkspaceFeatureLoading labelKey="workspace.layout.loading.versionControl" />}>
      <VersionControlProvider>{shell}</VersionControlProvider>
    </React.Suspense>
  ) : shell;

  return permissions.canUseTerminal ? (
    <WorkspaceRealtimeProvider
      workspaceId={workspaceRuntime.workspaceId}
      runtimeUrl={workspaceRuntime.runtimeBaseUrl}
    >
      {withVersionControl}
    </WorkspaceRealtimeProvider>
  ) : withVersionControl;
};
