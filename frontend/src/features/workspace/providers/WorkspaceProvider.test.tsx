import { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { WorkspaceProvider, useWorkspace } from './WorkspaceProvider';
import { clearAllWorkspaceTabs, loadWorkspaceTabs } from '../utils/workspaceTabsStorage';
import {
  clearAllWorkspaceLayoutPreferences,
  getDefaultWorkspaceLayoutPreferences,
  loadWorkspaceLayoutPreferences,
  saveWorkspaceLayoutPreferences,
} from '../utils/workspaceLayoutStorage';

const { workspaceRuntimeMockState } = vi.hoisted(() => ({
  workspaceRuntimeMockState: {
    runtimeBaseUrl: null as string | null,
  },
}));

const loadFileTreeMock = vi.fn();
const saveFileContentMock = vi.fn();
const readFileContentMock = vi.fn();

vi.mock('../hooks/useWorkspaceRuntime', () => ({
  useWorkspaceRuntime: (workspaceId?: string) => ({
    workspaceId: workspaceId ?? null,
    runtimeBaseUrl: workspaceRuntimeMockState.runtimeBaseUrl,
    terminalExternalUrl: null,
    cliType: null,
    runtimeStatus: null,
    isLoading: false,
    error: null,
    reload: vi.fn(),
    changeWorkspace: vi.fn(),
  }),
}));

vi.mock('../hooks/useWorkspaceFileTreeAdapter', () => ({
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

vi.mock('@/features/auth/hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    getAccessToken: () => 'token',
  }),
}));

const LayoutProbe = () => {
  const { state, dispatch } = useWorkspace();

  return (
    <div>
      <div data-testid="layout-state">
        {JSON.stringify({
          currentFeature: state.currentFeature,
          sidebarCollapsed: state.sidebarCollapsed,
          sidebarWidth: state.sidebarWidth,
          secondColumnCollapsed: state.secondColumnCollapsed,
          secondColumnWidth: state.secondColumnWidth,
        rightChatCollapsed: state.rightChatCollapsed,
        rightChatWidth: state.rightChatWidth,
        expandedNavigationItems: state.expandedNavigationItems,
        fileTreeShowHiddenEntries: state.fileTreeShowHiddenEntries,
      })}
      </div>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_SIDEBAR_COLLAPSED', payload: true })}
      >
        collapse-sidebar
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_SIDEBAR_WIDTH', payload: 350 })}
      >
        widen-sidebar
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES', payload: true })}
      >
        show-hidden-entries
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
  const { workspace, fileEditor, openFileInTab, state, dispatch } = useWorkspace();

  return (
    <div>
      <div data-testid="current-tabs">
        {JSON.stringify({
          currentFeature: state.currentFeature,
          tabScope: workspace.tabScope,
          selectedGitContextId: state.versionControl.selectedGitContextId,
          openTabs: workspace.openTabs.map((tab) => tab.path),
          activeTabId: workspace.activeTabId,
          modifiedTabs: fileEditor.modifiedTabs,
        })}
      </div>
      <div data-testid="all-tabs">
        {JSON.stringify({
          fileManagementTabs: state.fileManagement.openTabs.map((tab) => tab.path),
          openSpecTabs: state.openspec.openTabs.map((tab) => tab.path),
        })}
      </div>
      <button type="button" onClick={() => openFileInTab('/src/App.tsx', 'app', 'file-management')}>
        open-file-management-tab
      </button>
      <button type="button" onClick={() => openFileInTab('/src/Other.ts', 'other', 'file-management')}>
        open-second-file-management-tab
      </button>
      <button
        type="button"
        onClick={() => dispatch({
          type: 'REORDER_FILE_TABS',
          payload: {
            scope: 'file-management',
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
      <button
        type="button"
        onClick={() => openFileInTab('/openspec/changes/demo/tasks.md', 'tasks', 'openspec')}
      >
        open-openspec-tab
      </button>
      <button
        type="button"
        onClick={() => openFileInTab('/openspec/changes/demo/design.md', 'design', 'openspec')}
      >
        open-second-openspec-tab
      </button>
      <button
        type="button"
        onClick={() => dispatch({
          type: 'REORDER_FILE_TABS',
          payload: {
            scope: 'openspec',
            tabIds: ['/openspec/changes/demo/design.md', '/openspec/changes/demo/tasks.md'],
          },
        })}
      >
        reorder-openspec-tabs
      </button>
    </div>
  );
};

const getCurrentTabsState = () => JSON.parse(screen.getByTestId('current-tabs').textContent ?? '{}');
const getAllTabsState = () => JSON.parse(screen.getByTestId('all-tabs').textContent ?? '{}');

describe('WorkspaceProvider layout persistence', () => {
  beforeEach(() => {
    clearAllWorkspaceLayoutPreferences();
    clearAllWorkspaceTabs();
    workspaceRuntimeMockState.runtimeBaseUrl = null;
    loadFileTreeMock.mockReset();
    saveFileContentMock.mockReset();
    readFileContentMock.mockReset();
  });

  it('restores saved layout preferences when mounting a workspace', async () => {
    saveWorkspaceLayoutPreferences('ws-1', {
      ...getDefaultWorkspaceLayoutPreferences(),
      sidebarCollapsed: true,
      secondColumnCollapsed: true,
      rightChatCollapsed: true,
      sidebarWidth: 310,
      secondColumnWidth: 410,
      rightChatWidth: 520,
      expandedNavigationItems: ['claude-code', 'container-management'],
      fileTreeShowHiddenEntries: true,
    });

    render(
      <WorkspaceProvider workspaceId="ws-1">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: true,
        secondColumnCollapsed: true,
        rightChatCollapsed: true,
        sidebarWidth: 310,
        secondColumnWidth: 410,
        rightChatWidth: 520,
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
      { initialRoute: '/workspaces/file-management' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'collapse-sidebar' }));
    fireEvent.click(screen.getByRole('button', { name: 'widen-sidebar' }));
    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));

    // 等防抖寫入完成（500ms），確認 localStorage 已經有資料
    await waitFor(
      () => {
        const persisted = loadWorkspaceLayoutPreferences('ws-unmount');
        expect(persisted).toMatchObject({
          sidebarCollapsed: true,
          sidebarWidth: 350,
          fileTreeShowHiddenEntries: true,
        });
      },
      { timeout: 2000 }
    );

    firstRender.unmount();

    render(
      <WorkspaceProvider workspaceId="ws-unmount">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: true,
        sidebarWidth: 350,
        fileTreeShowHiddenEntries: true,
      });
    });
  });

  it('keeps hidden-entry visibility when switching workspace pages inside the same provider', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-navigation">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));
    fireEvent.click(screen.getByRole('button', { name: 'switch-to-version-control' }));
    fireEvent.click(screen.getByRole('button', { name: 'switch-to-file-management' }));

    expect(getLayoutState()).toMatchObject({
      currentFeature: 'file-management',
      fileTreeShowHiddenEntries: true,
    });
  });

  it('does not overwrite saved layout when mounted inside React.StrictMode', async () => {
    // 預先存入使用者之前儲存的偏好
    saveWorkspaceLayoutPreferences('ws-strict', {
      ...getDefaultWorkspaceLayoutPreferences(),
      sidebarCollapsed: true,
      sidebarWidth: 360,
      rightChatCollapsed: true,
      rightChatWidth: 520,
      expandedNavigationItems: ['claude-code', 'container-management'],
      fileTreeShowHiddenEntries: true,
    });

    render(
      <StrictMode>
        <WorkspaceProvider workspaceId="ws-strict">
          <LayoutProbe />
        </WorkspaceProvider>
      </StrictMode>,
      { initialRoute: '/workspaces/file-management' }
    );

    // UI 應該顯示 saved 的值
    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: true,
        sidebarWidth: 360,
        rightChatCollapsed: true,
        rightChatWidth: 520,
        fileTreeShowHiddenEntries: true,
      });
    });

    // 500ms 之後防抖 effect 會寫回一次 localStorage，驗證寫入的是 saved 值而不是 initialState（regression guard）
    await new Promise(resolve => setTimeout(resolve, 700));
    const persisted = loadWorkspaceLayoutPreferences('ws-strict');
    expect(persisted).toMatchObject({
      sidebarCollapsed: true,
      sidebarWidth: 360,
      rightChatCollapsed: true,
      rightChatWidth: 520,
      expandedNavigationItems: ['claude-code', 'container-management'],
      fileTreeShowHiddenEntries: true,
    });
  });

  it('keeps layout preferences isolated across workspaces when switching', async () => {
    saveWorkspaceLayoutPreferences('ws-b', {
      ...getDefaultWorkspaceLayoutPreferences(),
      rightChatCollapsed: true,
      rightChatWidth: 610,
      expandedNavigationItems: ['container-management'],
    });

    const view = render(
      <WorkspaceProvider workspaceId="ws-a">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'collapse-sidebar' }));
    fireEvent.click(screen.getByRole('button', { name: 'widen-sidebar' }));
    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: true,
        sidebarWidth: 350,
      });
    });

    view.rerender(
      <WorkspaceProvider workspaceId="ws-b">
        <LayoutProbe />
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: false,
        rightChatCollapsed: true,
        rightChatWidth: 610,
        expandedNavigationItems: ['container-management'],
      });
    });

    view.rerender(
      <WorkspaceProvider workspaceId="ws-a">
        <LayoutProbe />
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: true,
        sidebarWidth: 350,
      });
    });
  });

  it('persists layout changes via debounced write without unmount', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-debounce">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    // 初始狀態 localStorage 沒有資料（載入流程 saved === null）
    expect(loadWorkspaceLayoutPreferences('ws-debounce')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'collapse-sidebar' }));
    fireEvent.click(screen.getByRole('button', { name: 'widen-sidebar' }));
    fireEvent.click(screen.getByRole('button', { name: 'show-hidden-entries' }));

    // 防抖 effect 使用 setTimeout(500ms)，waitFor 預設 1s timeout 可涵蓋
    await waitFor(
      () => {
        const persisted = loadWorkspaceLayoutPreferences('ws-debounce');
        expect(persisted).not.toBeNull();
        expect(persisted).toMatchObject({
          sidebarCollapsed: true,
          sidebarWidth: 350,
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
          sidebarCollapsed: 'broken',
        },
      })
    );

    render(
      <WorkspaceProvider workspaceId="ws-invalid">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    await waitFor(() => {
      expect(getLayoutState()).toMatchObject({
        sidebarCollapsed: false,
        sidebarWidth: 240,
        secondColumnCollapsed: false,
        secondColumnWidth: 320,
        rightChatCollapsed: false,
        rightChatWidth: 400,
        expandedNavigationItems: ['claude-code'],
      });
    });
  });

  it('keeps file management and openspec tabs isolated and restores them independently', async () => {
    const firstRender = render(
      <WorkspaceProvider workspaceId="ws-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-openspec-tab' }));

    expect(getAllTabsState()).toEqual({
      fileManagementTabs: ['/src/App.tsx'],
      openSpecTabs: ['/openspec/changes/demo/tasks.md'],
    });

    expect(getCurrentTabsState()).toMatchObject({
      currentFeature: 'file-management',
      tabScope: 'file-management',
      openTabs: ['/src/App.tsx'],
      activeTabId: '/src/App.tsx',
    });

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-tabs', 'file-management')?.openTabs.map((tab) => tab.path)).toEqual([
        '/src/App.tsx',
      ]);
      expect(loadWorkspaceTabs('ws-tabs', 'openspec')?.openTabs.map((tab) => tab.path)).toEqual([
        '/openspec/changes/demo/tasks.md',
      ]);
    });

    firstRender.unmount();

    render(
      <WorkspaceProvider workspaceId="ws-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/openspec' }
    );

    await waitFor(() => {
      expect(getAllTabsState()).toEqual({
        fileManagementTabs: ['/src/App.tsx'],
        openSpecTabs: ['/openspec/changes/demo/tasks.md'],
      });
    });

    expect(loadWorkspaceTabs('ws-tabs', 'openspec')?.activeTabId).toBe(
      '/openspec/changes/demo/tasks.md'
    );
  });

  it('persists reordered file-management tabs without changing openspec tab order', async () => {
    const firstRender = render(
      <WorkspaceProvider workspaceId="ws-reorder-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-second-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-openspec-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-second-openspec-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'reorder-file-management-tabs' }));

    expect(getAllTabsState()).toEqual({
      fileManagementTabs: ['/src/Other.ts', '/src/App.tsx'],
      openSpecTabs: ['/openspec/changes/demo/tasks.md', '/openspec/changes/demo/design.md'],
    });

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-reorder-tabs', 'file-management')?.openTabs.map((tab) => tab.path)).toEqual([
        '/src/Other.ts',
        '/src/App.tsx',
      ]);
    });

    firstRender.unmount();

    render(
      <WorkspaceProvider workspaceId="ws-reorder-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    await waitFor(() => {
      expect(getAllTabsState()).toEqual({
        fileManagementTabs: ['/src/Other.ts', '/src/App.tsx'],
        openSpecTabs: ['/openspec/changes/demo/tasks.md', '/openspec/changes/demo/design.md'],
      });
    });
  });

  it('reorders openspec tabs without changing file-management tab order', async () => {
    render(
      <WorkspaceProvider workspaceId="ws-reorder-openspec-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-second-file-management-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-openspec-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'open-second-openspec-tab' }));
    fireEvent.click(screen.getByRole('button', { name: 'reorder-openspec-tabs' }));

    expect(getAllTabsState()).toEqual({
      fileManagementTabs: ['/src/App.tsx', '/src/Other.ts'],
      openSpecTabs: ['/openspec/changes/demo/design.md', '/openspec/changes/demo/tasks.md'],
    });
  });

  it('reloads the file tree when switching workspaces even if the runtime base URL is unchanged', async () => {
    workspaceRuntimeMockState.runtimeBaseUrl = 'http://shared-runtime';

    const view = render(
      <WorkspaceProvider workspaceId="ws-a">
        <LayoutProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    await waitFor(() => {
      expect(loadFileTreeMock).toHaveBeenCalledTimes(1);
    });

    view.rerender(
      <WorkspaceProvider workspaceId="ws-b">
        <LayoutProbe />
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(loadFileTreeMock).toHaveBeenCalledTimes(2);
    });
  });

  it('restores file-management tabs separately for each git context', async () => {
    workspaceRuntimeMockState.runtimeBaseUrl = 'http://shared-runtime';

    render(
      <WorkspaceProvider workspaceId="ws-context-tabs">
        <TabIsolationProbe />
      </WorkspaceProvider>,
      { initialRoute: '/workspaces/file-management' }
    );

    await waitFor(() => {
      expect(loadFileTreeMock).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-context-tabs', 'file-management', 'primary')?.openTabs.map((tab) => tab.path)).toEqual([
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

    await waitFor(() => {
      expect(loadFileTreeMock).toHaveBeenCalledTimes(2);
    });

    fireEvent.click(screen.getByRole('button', { name: 'open-file-management-tab' }));

    await waitFor(() => {
      expect(loadWorkspaceTabs('ws-context-tabs', 'file-management', 'worktree:feature-auth')?.openTabs.map((tab) => tab.path)).toEqual([
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
