import { StrictMode, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@/__tests__/utils/render';
import { WorkspaceProvider, useWorkspace } from './WorkspaceProvider';
import { loadWorkspaceTabs } from '../storage/workspaceTabsStorage';
import {
  loadWorkspaceLayoutPreferences,
  saveWorkspaceLayoutPreferences,
} from '../storage/workspaceLayoutStorage';
import type { WorkspaceLayoutPreferences } from './workspaceStateTypes';
import {
  WORKSPACE_SHELL_LAYOUT_DEFAULTS,
  workspaceShellLayoutStorage,
} from '../storage/workspaceShellLayoutStorage';
import { useWorkspaceAiChatSelection } from '../integrations/ai-chat/WorkspaceAiChatSelectionContext';
import type { UseWorkspaceRuntimeReturn } from '../hooks/useWorkspaceRuntime';

const createLayoutPreferences = (
  overrides: Partial<WorkspaceLayoutPreferences> = {},
): WorkspaceLayoutPreferences => ({
  companionActiveTab: 'ai-chat',
  companionTerminalPlacement: 'side',
  expandedNavigationItems: ['claude-code'],
  fileTreeShowHiddenEntries: false,
  ...overrides,
});

const {
  apiErrorHandler,
  useThreadEventsMock,
  workspaceChangeMock,
  workspaceReloadMock,
  useWorkspaceRuntimeMock,
  workspaceRuntimeMockState,
} = vi.hoisted(() => ({
  apiErrorHandler: {
    current: null as ((event: {
      status: number;
      errorCode?: string;
      responseUrl: string;
    }) => void) | null,
  },
  useThreadEventsMock: vi.fn(),
  workspaceChangeMock: vi.fn(),
  useWorkspaceRuntimeMock: vi.fn(),
  workspaceReloadMock: vi.fn(),
  workspaceRuntimeMockState: {
    runtimeBaseUrl: null as string | null,
    accessRole: 'owner' as 'owner' | 'manager' | 'reader' | null,
    allowedOperations: [] as string[],
    isAuthorizationResolved: true,
    isLoading: false,
    error: null as string | null,
    errorCode: null as string | null,
  },
}));
const updateRecentWorkspaceMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/recentWorkspaceApi', () => ({
  updateRecentWorkspace: updateRecentWorkspaceMock,
}));

vi.mock('@/shared/api/apiClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/apiClient')>();
  return {
    ...actual,
    subscribeApiError: vi.fn((handler: typeof apiErrorHandler.current) => {
      apiErrorHandler.current = handler;
      return () => {
        if (apiErrorHandler.current === handler) {
          apiErrorHandler.current = null;
        }
      };
    }),
  };
});

vi.mock('@/features/ai-chat/public', () => ({
  useThreadEvents: useThreadEventsMock,
}));

vi.mock('../integrations/ai-chat/WorkspaceAiChatIntegration', async () => {
  const {
    WorkspaceAiChatSelectionProvider,
  } = await import('../integrations/ai-chat/WorkspaceAiChatSelectionContext');

  return {
    WorkspaceAiChatIntegration: ({ children }: { children: ReactNode }) => (
      <WorkspaceAiChatSelectionProvider
        value={{
          canSelectCodeReference: false,
          selectCodeReference: vi.fn(),
        }}
      >
        <div data-testid="workspace-ai-chat-integration">{children}</div>
      </WorkspaceAiChatSelectionProvider>
    ),
  };
});

const loadFileTreeMock = vi.fn();
const saveFileContentMock = vi.fn();
const readFileContentMock = vi.fn();

vi.mock('../hooks/useWorkspaceRuntime', () => ({
  useWorkspaceRuntime: (workspaceId?: string) => {
    useWorkspaceRuntimeMock(workspaceId);
    return {
      workspaceId: workspaceId ?? null,
      runtimeBaseUrl: workspaceRuntimeMockState.runtimeBaseUrl,
      agenticTools: ['claude-code'],
      accessRole: workspaceRuntimeMockState.accessRole,
      allowedOperations: workspaceRuntimeMockState.allowedOperations,
      runtimeStatus: null,
      isLoading: workspaceRuntimeMockState.isLoading,
      isAuthorizationResolved: workspaceRuntimeMockState.isAuthorizationResolved,
      error: workspaceRuntimeMockState.error,
      errorCode: workspaceRuntimeMockState.errorCode,
      reload: workspaceReloadMock,
      changeWorkspace: workspaceChangeMock,
    };
  },
}));

vi.mock('../features/file-management/hooks/useWorkspaceFileTreeAdapter', () => ({
  useWorkspaceFileTreeAdapter: ({ showHiddenEntries }: { showHiddenEntries: boolean }) => ({
    state: {
      nodes: [],
      selectedFile: null,
      selectedFiles: new Set<string>(),
      lastSelectedFile: null,
      isLoading: false,
      error: null,
      expandedNodes: new Set<string>(),
      pendingAction: null,
      draggedNode: null,
      dropTarget: null,
      showHiddenEntries,
    },
    actions: {
      loadFileTree: loadFileTreeMock,
      saveFileContent: saveFileContentMock,
      readFileContent: readFileContentMock,
    },
  }),
}));

const LayoutProbe = () => {
  const { state, dispatch } = useWorkspace();

  return (
    <div>
      <div data-testid="layout-state">
        {JSON.stringify({
          currentFeature: state.currentFeature,
          companionActiveTab: state.companionActiveTab,
          companionTerminalPlacement: state.companionTerminalPlacement,
          expandedNavigationItems: state.expandedNavigationItems,
          fileTreeShowHiddenEntries: state.fileTreeShowHiddenEntries,
        })}
      </div>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES', payload: true })}
      >
        show-hidden-entries
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_COMPANION_ACTIVE_TAB', payload: 'terminal' })}
      >
        select-terminal-tab
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_COMPANION_TERMINAL_PLACEMENT', payload: 'bottom' })}
      >
        dock-terminal-bottom
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_CURRENT_FEATURE', payload: 'version-control' })}
      >
        switch-to-version-control
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_CURRENT_FEATURE', payload: 'file-management' })}
      >
        switch-to-file-management
      </button>
    </div>
  );
};

const getLayoutState = () => JSON.parse(screen.getByTestId('layout-state').textContent ?? '{}');

const TabIsolationProbe = () => {
  const {
    fileManagementTabsRestoreStatus,
    workspace,
    fileEditor,
    openFileInTab,
    permissions,
    state,
    dispatch,
  } = useWorkspace();

  return (
    <div>
      <div data-testid="current-tabs">
        {JSON.stringify({
          currentFeature: state.currentFeature,
          selectedGitContextId: state.versionControl.selectedGitContextId,
          fileManagementTabsRestoreStatus,
          openTabs: workspace.openTabs.map((tab) => tab.path),
          tabContents: workspace.openTabs.map((tab) => tab.content),
          activeTabId: workspace.activeTabId,
          modifiedTabs: fileEditor.modifiedTabs,
          canRead: permissions.canRead,
          canWrite: permissions.canWrite,
        })}
      </div>
      <div data-testid="all-tabs">
        {JSON.stringify({
          fileManagementTabs: state.fileManagement.openTabs.map((tab) => tab.path),
        })}
      </div>
      <button type="button" onClick={() => openFileInTab('/src/App.tsx', 'app')}>
        open-file-management-tab
      </button>
      <button type="button" onClick={() => openFileInTab('/src/Other.ts', 'other')}>
        open-second-file-management-tab
      </button>
      <button
        type="button"
        onClick={() => {
          fileEditor.updateTabContent('/src/App.tsx', 'unsaved draft');
          fileEditor.setTabModified('/src/App.tsx', true);
        }}
      >
        modify-file-management-tab
      </button>
      <button
        type="button"
        onClick={() => dispatch({
          type: 'REORDER_FILE_TABS',
          payload: {
            tabIds: ['/src/Other.ts', '/src/App.tsx'],
          },
        })}
      >
        reorder-file-management-tabs
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_SELECTED_GIT_CONTEXT', payload: 'worktree:feature-auth' })}
      >
        switch-to-worktree
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_SELECTED_GIT_CONTEXT', payload: 'primary' })}
      >
        switch-to-primary
      </button>
    </div>
  );
};

const getCurrentTabsState = () => JSON.parse(screen.getByTestId('current-tabs').textContent ?? '{}');
const getAllTabsState = () => JSON.parse(screen.getByTestId('all-tabs').textContent ?? '{}');

const AiChatSelectionProbe = () => {
  const { canSelectCodeReference } = useWorkspaceAiChatSelection();
  return (
    <div data-testid="can-select-code-reference">
      {String(canSelectCodeReference)}
    </div>
  );
};

describe('WorkspaceProvider layout persistence', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    workspaceRuntimeMockState.runtimeBaseUrl = null;
    loadFileTreeMock.mockReset();
    saveFileContentMock.mockReset();
    readFileContentMock.mockReset();
    updateRecentWorkspaceMock.mockReset().mockResolvedValue(undefined);
    useThreadEventsMock.mockReset();
    workspaceReloadMock.mockReset().mockResolvedValue(undefined);
    workspaceChangeMock.mockReset().mockResolvedValue(undefined);
    useWorkspaceRuntimeMock.mockReset();
    apiErrorHandler.current = null;
    workspaceRuntimeMockState.accessRole = 'owner';
    workspaceRuntimeMockState.allowedOperations = [
      'workspace.detail.read',
      'workspace.content.write',
      'workspace.lifecycle.execute',
      'workspace.metadata.write',
      'workspace.access.manage',
      'workspace.attachment.write',
      'workspace.sensitive_settings.manage',
      'workspace.delete',
      'workspace.terminal.use',
      'workspace.agent_chat.use',
      'workspace.automation.execute',
      'workspace.browser_automation.use',
    ];
    workspaceRuntimeMockState.isAuthorizationResolved = true;
    workspaceRuntimeMockState.isLoading = false;
    workspaceRuntimeMockState.error = null;
    workspaceRuntimeMockState.errorCode = null;
  });

  it('uses the Entry Gate runtime snapshot without resolving another workspace', () => {
    const runtimeSnapshot = {
      workspaceId: 'ws-snapshot',
      workspaceName: 'Snapshot workspace',
      runtimeBaseUrl: 'http://runtime.snapshot',
      agenticTools: ['claude-code'],
      accessRole: 'owner',
      accessSource: null,
      accessSources: [],
      allowedOperations: ['workspace.detail.read'],
      runtimeStatus: null,
      isLoading: false,
      isAuthorizationResolved: true,
      error: null,
      errorCode: null,
      reload: workspaceReloadMock,
      changeWorkspace: workspaceChangeMock,
    } as UseWorkspaceRuntimeReturn;

    render(
      <WorkspaceProvider workspaceId="ws-snapshot" runtimeSnapshot={runtimeSnapshot}>
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-snapshot/home' },
    );

    expect(useWorkspaceRuntimeMock).toHaveBeenCalledWith(null);
  });

  it('records the workspace after entering it successfully', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-recent">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-recent/home' },
    );

    await waitFor(() => {
      expect(updateRecentWorkspaceMock).toHaveBeenCalledWith('ws-recent');
    });
  });

  it('restores saved layout preferences when mounting a workspace', async () => {
    saveWorkspaceLayoutPreferences('ws-1', createLayoutPreferences({
      companionActiveTab: 'terminal',
      companionTerminalPlacement: 'bottom',
      expandedNavigationItems: ['claude-code', 'container-management'],
      fileTreeShowHiddenEntries: true,
    }));

    render(
      <WorkspaceProvider workspaceId="ws-1">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        companionActiveTab: 'terminal',
        companionTerminalPlacement: 'bottom',
        expandedNavigationItems: ['claude-code', 'container-management'],
        fileTreeShowHiddenEntries: true,
      });
    });
  });

  it('persists layout via debounced write and restores it on remount', async () => {
    const firstRender = render(
      <WorkspaceProvider workspaceId="ws-unmount">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));
    fireEvent.click(screen.getByRole('button', { name: 'select-terminal-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'dock-terminal-bottom' }));

    await waitFor(
      () => {
        const persisted = loadWorkspaceLayoutPreferences('ws-unmount');
        expect(persisted).toMatchObject({
          fileTreeShowHiddenEntries: true,
          companionActiveTab: 'terminal',
          companionTerminalPlacement: 'bottom',
        });
      },
      { timeout: 2000 }
    );

    firstRender.unmount();

    render(
      <WorkspaceProvider workspaceId="ws-unmount">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        fileTreeShowHiddenEntries: true,
        companionActiveTab: 'terminal',
        companionTerminalPlacement: 'bottom',
      });
    });
  });

  it('keeps hidden-entry visibility when switching workspace pages inside the same provider', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-navigation">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));
    fireEvent.click(screen.getByRole('button', { name: 'switch-to-version-control' }));
    fireEvent.click(screen.getByRole('button', { name: 'switch-to-file-management' }));

    expect(getLayoutState()).toMatchObject({
      currentFeature: 'file-management',
      fileTreeShowHiddenEntries: true,
    });
  });

  it('does not load the file tree just because runtime and auth are ready', async () => {
    workspaceRuntimeMockState.runtimeBaseUrl = 'http://runtime.test';

    render(
      <WorkspaceProvider workspaceId="ws-file-tree-lazy">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-file-tree-lazy/codex/settings' },
    );

    await waitFor(() => {
      expect(screen.getByTestId('layout-state')).toBeInTheDocument();
    });

    expect(loadFileTreeMock).not.toHaveBeenCalled();
  });

  it('keeps the AI Chat selection boundary available while disabling chat without capability', () => {
    workspaceRuntimeMockState.runtimeBaseUrl = 'http://runtime.test';
    workspaceRuntimeMockState.allowedOperations = (
      workspaceRuntimeMockState.allowedOperations.filter(
        operation => operation !== 'workspace.agent_chat.use',
      )
    );
    workspaceRuntimeMockState.accessRole = 'reader';

    render(
      <WorkspaceProvider workspaceId="ws-no-chat">
        <AiChatSelectionProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-no-chat/files' },
    );

    expect(useThreadEventsMock).toHaveBeenCalledWith(
      'ws-no-chat',
      'http://runtime.test',
      false,
    );
    expect(screen.queryByTestId('workspace-ai-chat-integration')).not.toBeInTheDocument();
    expect(screen.getByTestId('can-select-code-reference')).toHaveTextContent('false');
  });

  it('refreshes active workspace authorization on focus, visible, and workspace denial events', async () => {
    const visibilityState = vi
      .spyOn(document, 'visibilityState', 'get')
      .mockReturnValue('visible');
    render(
      <WorkspaceProvider workspaceId="ws-refresh">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-refresh/files' },
    );

    fireEvent(window, new Event('focus'));
    await waitFor(() => {
      expect(workspaceReloadMock).toHaveBeenCalledTimes(1);
    });
    await Promise.resolve();

    fireEvent(document, new Event('visibilitychange'));
    await waitFor(() => {
      expect(workspaceReloadMock).toHaveBeenCalledTimes(2);
    });
    await Promise.resolve();

    apiErrorHandler.current?.({
      status: 403,
      errorCode: 'WORKSPACE_RUNTIME_ACTION_FORBIDDEN',
      responseUrl: '/api/v1/workspaces/ws-refresh/runtime/restart',
    });
    await waitFor(() => {
      expect(workspaceReloadMock).toHaveBeenCalledTimes(3);
    });
    await Promise.resolve();

    apiErrorHandler.current?.({
      status: 403,
      errorCode: 'PLATFORM_AUTHORIZATION_DENIED',
      responseUrl: '/api/v1/workspaces/ws-refresh',
    });
    await Promise.resolve();
    expect(workspaceReloadMock).toHaveBeenCalledTimes(3);
    visibilityState.mockRestore();
  });

  it('does not overwrite saved layout when mounted inside React.StrictMode', async () => {
    saveWorkspaceLayoutPreferences('ws-strict', createLayoutPreferences({
      companionActiveTab: 'terminal',
      companionTerminalPlacement: 'bottom',
      expandedNavigationItems: ['claude-code', 'container-management'],
      fileTreeShowHiddenEntries: true,
    }));

    render(
      <StrictMode>
        <WorkspaceProvider workspaceId="ws-strict">
          <LayoutProbe />
        </WorkspaceProvider>
      </StrictMode>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        companionActiveTab: 'terminal',
        companionTerminalPlacement: 'bottom',
        fileTreeShowHiddenEntries: true,
      });
    });

    await new Promise(resolve => setTimeout(resolve, 700));
    const persisted = loadWorkspaceLayoutPreferences('ws-strict');
    expect(persisted).toMatchObject({
      companionActiveTab: 'terminal',
      companionTerminalPlacement: 'bottom',
      expandedNavigationItems: ['claude-code', 'container-management'],
      fileTreeShowHiddenEntries: true,
    });
  });

  it('keeps layout preferences isolated across workspaces when switching', async () => {
    saveWorkspaceLayoutPreferences('ws-b', createLayoutPreferences({
      companionTerminalPlacement: 'bottom',
      expandedNavigationItems: ['container-management'],
    }));

    const view = render(
      <WorkspaceProvider workspaceId="ws-a">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-terminal-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        companionActiveTab: 'terminal',
        fileTreeShowHiddenEntries: true,
      });
    });

    view.rerender(
      <WorkspaceProvider workspaceId="ws-b">
        <LayoutProbe />
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        companionActiveTab: 'ai-chat',
        companionTerminalPlacement: 'bottom',
        expandedNavigationItems: ['container-management'],
        fileTreeShowHiddenEntries: false,
      });
    });

    view.rerender(
      <WorkspaceProvider workspaceId="ws-a">
        <LayoutProbe />
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        companionActiveTab: 'terminal',
        fileTreeShowHiddenEntries: true,
      });
    });
  });

  it('persists layout changes via debounced write without unmount', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-debounce">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    expect(loadWorkspaceLayoutPreferences('ws-debounce')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'select-terminal-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));

    await waitFor(
      () => {
        const persisted = loadWorkspaceLayoutPreferences('ws-debounce');
        expect(persisted).not.toBeNull();
        expect(persisted).toMatchObject({
          companionActiveTab: 'terminal',
          fileTreeShowHiddenEntries: true,
        });
      },
      { timeout: 2000 }
    );
  });

  it('falls back to default layout when persisted data is invalid', async () => {
    localStorage.setItem(
      'workspace_layout_ws-invalid',
      JSON.stringify({
        version: '1',
        data: {
          expandedNavigationItems: 'broken',
        },
      })
    );

    render(
      <WorkspaceProvider workspaceId="ws-invalid">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        companionActiveTab: 'ai-chat',
        companionTerminalPlacement: 'side',
        expandedNavigationItems: ['claude-code'],
        fileTreeShowHiddenEntries: false,
      });
    });
  });

  it('persists file-management tabs and restores them after remount', async () => {
    const firstRender = render(
      <WorkspaceProvider workspaceId="ws-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));

    expect(getAllTabsState()).toEqual({
      fileManagementTabs: ['/src/App.tsx'],
    });

    expect(getCurrentTabsState()).toMatchObject({
      currentFeature: 'file-management',
      openTabs: ['/src/App.tsx'],
      activeTabId: '/src/App.tsx',
    });

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-tabs')?.openTabs.map((tab) => tab.path)).toEqual([
        '/src/App.tsx',
      ]);
    });
    expect(localStorage.getItem('workspace_tabs_file-management_ws-tabs_ctx_primary')).not.toBeNull();

    firstRender.unmount();

    render(
      <WorkspaceProvider workspaceId="ws-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    await waitFor(() => {
      expect(getAllTabsState()).toEqual({
        fileManagementTabs: ['/src/App.tsx'],
      });
    });
  });

  it('retains open tabs and unsaved drafts after a write-to-read-only downgrade', async () => {
    const view = render(
      <WorkspaceProvider workspaceId="ws-read-only-downgrade">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-read-only-downgrade/files' },
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'modify-file-management-tab' }));
    expect(getCurrentTabsState()).toMatchObject({
      openTabs: ['/src/App.tsx'],
      tabContents: ['unsaved draft'],
      modifiedTabs: ['/src/App.tsx'],
      canRead: true,
      canWrite: true,
    });

    workspaceRuntimeMockState.allowedOperations = (
      workspaceRuntimeMockState.allowedOperations.filter(
        operation => operation !== 'workspace.content.write',
      )
    );
    view.rerender(
      <WorkspaceProvider workspaceId="ws-read-only-downgrade">
        <TabIsolationProbe />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(getCurrentTabsState()).toMatchObject({
        openTabs: ['/src/App.tsx'],
        tabContents: ['unsaved draft'],
        modifiedTabs: ['/src/App.tsx'],
        canRead: true,
        canWrite: false,
      });
    });
  });

  it('clears in-memory and persisted tabs after workspace read access is fully revoked', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          gcTime: Infinity,
          retry: false,
        },
      },
    });
    const view = render(
      <WorkspaceProvider workspaceId="ws-fully-revoked">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      {
        initialRoute: '/workspaces/ws-fully-revoked/files',
        queryClient,
      },
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'modify-file-management-tab' }));
    await waitFor(() => {
      expect(
        localStorage.getItem('workspace_tabs_file-management_ws-fully-revoked_ctx_primary'),
      ).not.toBeNull();
    });
    localStorage.setItem(
      'file_workbench_split_ws-fully-revoked',
      JSON.stringify({
        version: '1',
        data: {
          direction: 'horizontal',
          panes: [{ tabIds: ['/src/App.tsx'], activeTabId: '/src/App.tsx' }],
          sizes: [100],
        },
      }),
    );
    localStorage.setItem(
      'workspace.fileManagement.archiveOperations.v1',
      JSON.stringify([
        {
          operationId: 'revoked-primary',
          archiveName: 'primary.zip',
          paths: ['/src'],
          context: {
            workspaceId: 'ws-fully-revoked',
            contextId: null,
            runtimeBaseUrl: 'http://runtime.test',
          },
          startedAt: '2026-07-30T00:00:00.000Z',
        },
        {
          operationId: 'revoked-worktree',
          archiveName: 'worktree.zip',
          paths: ['/src'],
          context: {
            workspaceId: 'ws-fully-revoked',
            contextId: 'worktree:authorization',
            runtimeBaseUrl: 'http://runtime-restarted.test',
          },
          startedAt: '2026-07-30T00:00:00.000Z',
        },
        {
          operationId: 'other-workspace',
          archiveName: 'other.zip',
          paths: ['/src'],
          context: {
            workspaceId: 'ws-retained',
            contextId: null,
            runtimeBaseUrl: 'http://runtime.test',
          },
          startedAt: '2026-07-30T00:00:00.000Z',
        },
      ]),
    );
    localStorage.setItem(
      'workspace_layout_ws-fully-revoked',
      JSON.stringify({
        version: '1',
        data: createLayoutPreferences(),
      }),
    );
    workspaceShellLayoutStorage.save(
      'ws-fully-revoked',
      WORKSPACE_SHELL_LAYOUT_DEFAULTS,
    );
    workspaceShellLayoutStorage.save(
      'ws-retained',
      {
        ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
        navSidebarCollapsed: true,
      },
    );
    localStorage.setItem('selectedWorkspaceId', 'ws-fully-revoked');
    sessionStorage.setItem(
      'workspace-availability-return:ws-fully-revoked',
      '/workspaces/ws-fully-revoked/files',
    );
    queryClient.setQueryData(
      ['version-control', 'workspaces', 'ws-fully-revoked', 'primary', 'changes', 'status'],
      { files: ['secret.txt'] },
    );
    queryClient.setQueryData(
      ['version-control', 'workspaces', 'ws-retained', 'primary', 'changes', 'status'],
      { files: ['retained.txt'] },
    );
    queryClient.setQueryData(
      ['workspace-runtime', '/api/v1/workspaces/ws-fully-revoked-copy/files'],
      { files: ['prefix-neighbor.txt'] },
    );
    queryClient.setQueryData(
      ['workspace-availability', 'ws-fully-revoked'],
      { availability: 'ready' },
    );

    workspaceRuntimeMockState.allowedOperations = [];
    view.rerender(
      <WorkspaceProvider workspaceId="ws-fully-revoked">
        <TabIsolationProbe />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(getCurrentTabsState()).toMatchObject({
        openTabs: [],
        tabContents: [],
        modifiedTabs: [],
        activeTabId: null,
        canRead: false,
        canWrite: false,
      });
      expect(
        localStorage.getItem('workspace_tabs_file-management_ws-fully-revoked_ctx_primary'),
      ).toBeNull();
      expect(localStorage.getItem('file_workbench_split_ws-fully-revoked')).toBeNull();
      expect(localStorage.getItem('workspace_layout_ws-fully-revoked')).toBeNull();
      expect(workspaceShellLayoutStorage.load('ws-fully-revoked')).toBeNull();
      expect(workspaceShellLayoutStorage.load('ws-retained')).toMatchObject({
        navSidebarCollapsed: true,
      });
      expect(localStorage.getItem('selectedWorkspaceId')).toBeNull();
      expect(
        sessionStorage.getItem('workspace-availability-return:ws-fully-revoked'),
      ).toBeNull();
      expect(JSON.parse(
        localStorage.getItem('workspace.fileManagement.archiveOperations.v1') ?? '[]',
      )).toEqual([
        expect.objectContaining({ operationId: 'other-workspace' }),
      ]);
      expect(queryClient.getQueryData([
        'version-control',
        'workspaces',
        'ws-fully-revoked',
        'primary',
        'changes',
        'status',
      ])).toBeUndefined();
      expect(queryClient.getQueryData([
        'workspace-availability',
        'ws-fully-revoked',
      ])).toBeUndefined();
      expect(queryClient.getQueryData([
        'version-control',
        'workspaces',
        'ws-retained',
        'primary',
        'changes',
        'status',
      ])).toEqual({ files: ['retained.txt'] });
      expect(queryClient.getQueryData([
        'workspace-runtime',
        '/api/v1/workspaces/ws-fully-revoked-copy/files',
      ])).toEqual({ files: ['prefix-neighbor.txt'] });
      expect(screen.queryByTestId('workspace-ai-chat-integration')).not.toBeInTheDocument();
      expect(useThreadEventsMock).toHaveBeenLastCalledWith(
        'ws-fully-revoked',
        '',
        false,
      );
    });
  });

  it('retains another selected workspace after the active workspace is revoked', async () => {
    localStorage.setItem('selectedWorkspaceId', 'ws-retained');
    const view = render(
      <WorkspaceProvider workspaceId="ws-revoked">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-revoked/files' },
    );

    workspaceRuntimeMockState.allowedOperations = [];
    view.rerender(
      <WorkspaceProvider workspaceId="ws-revoked">
        <TabIsolationProbe />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(getCurrentTabsState()).toMatchObject({ canRead: false });
      expect(localStorage.getItem('selectedWorkspaceId')).toBe('ws-retained');
    });
  });

  it('exposes file-management tab restore status with workspace and context', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-restore-ready">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-restore-ready/files' }
    );

    await waitFor(() => {
      expect(getCurrentTabsState()).toMatchObject({
        fileManagementTabsRestoreStatus: {
          ready: true,
          workspaceId: 'ws-restore-ready',
          contextId: null,
        },
      });
    });
  });

  it('persists reordered file-management tabs across remounts', async () => {
    const firstRender = render(
      <WorkspaceProvider workspaceId="ws-reorder-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-second-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'reorder-file-management-tabs' }));

    expect(getAllTabsState()).toEqual({
      fileManagementTabs: ['/src/Other.ts', '/src/App.tsx'],
    });

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-reorder-tabs')?.openTabs.map((tab) => tab.path)).toEqual([
        '/src/Other.ts',
        '/src/App.tsx',
      ]);
    });

    firstRender.unmount();

    render(
      <WorkspaceProvider workspaceId="ws-reorder-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    await waitFor(() => {
      expect(getAllTabsState()).toEqual({
        fileManagementTabs: ['/src/Other.ts', '/src/App.tsx'],
      });
    });
  });

  it('restores file-management tabs separately for each git context', async () => {
    workspaceRuntimeMockState.runtimeBaseUrl = 'http://shared-runtime';

    render(
      <WorkspaceProvider workspaceId="ws-context-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/ws-test/files' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-context-tabs', 'primary')?.openTabs.map((tab) => tab.path)).toEqual([
        '/src/App.tsx',
      ]);
    });

    fireEvent.click(screen.getByRole('button', { name: 'switch-to-worktree' }));

    await waitFor(() => {
      expect(getCurrentTabsState()).toMatchObject({
        selectedGitContextId: 'worktree:feature-auth',
        openTabs: [],
        activeTabId: null,
      });
    });

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-context-tabs', 'worktree:feature-auth')?.openTabs.map((tab) => tab.path)).toEqual([
        '/src/App.tsx',
      ]);
    });

    fireEvent.click(screen.getByRole('button', { name: 'switch-to-primary' }));

    await waitFor(() => {
      expect(getCurrentTabsState()).toMatchObject({
        selectedGitContextId: 'primary',
        openTabs: ['/src/App.tsx'],
        activeTabId: '/src/App.tsx',
      });
    });
  });
});
