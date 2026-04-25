import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { WorkspaceShell } from './WorkspaceShell';

const mocks = vi.hoisted(() => ({
  dispatchMock: vi.fn(),
  uploadFilesMock: vi.fn(async () => ({ success: true, message: 'ok', data: { uploadedPaths: [] } })),
  chatMountCount: 0,
  workspaceState: {
    sidebarCollapsed: false,
    sidebarWidth: 240,
    secondColumnCollapsed: false,
    secondColumnWidth: 300,
    rightChatCollapsed: false,
    rightChatWidth: 420,
    chatExpanded: false,
    currentFeature: 'custom-feature',
    claudeCodeSettings: { subView: 'claude-md' },
    agentToolSettings: { subView: '' },
    openspec: { subView: 'in-progress' },
    versionControl: { subView: 'changes', selectedGitContextId: null },
    workspaceSettings: { subView: 'basic' },
    containerManagement: { subView: 'runtime' },
    canvas: { subView: 'web-canvas' },
    expandedNavigationItems: [],
    fileTreeShowHiddenEntries: false,
  },
  workspaceRuntime: {
    workspaceId: 'ws-1',
    runtimeBaseUrl: 'http://runtime.test',
    terminalExternalUrl: null,
    cliType: null,
    runtimeStatus: 'running',
    isLoading: false,
    error: null,
    reload: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: mocks.workspaceState,
    dispatch: mocks.dispatchMock,
    workspaceRuntime: mocks.workspaceRuntime,
    fileTreeActions: {
      uploadFiles: mocks.uploadFilesMock,
    },
  }),
}));

vi.mock('./WorkspaceSidebar', () => ({
  WorkspaceSidebar: () => <div data-testid="workspace-sidebar">sidebar</div>,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../features/claude-code/components', () => ({
  ClaudeCodeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  MarkdownSidebar: () => <div>markdown-sidebar</div>,
}));

vi.mock('../features/openspec/OpenSpecWorkspaceContext', () => ({
  OpenSpecWorkspaceProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../realtime', () => ({
  WorkspaceRealtimeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/shared/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <div data-testid="global-navigation">global-navigation</div>,
}));

vi.mock('@/shared/components/errors/RuntimeErrorPage', () => ({
  RuntimeErrorPage: () => <div>runtime-error</div>,
}));

vi.mock('../hooks/useWorkspaceDeleteFallback', () => ({
  useWorkspaceDeleteFallback: () => vi.fn(),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('../services/workspaceLifecycleApi', () => ({
  workspaceLifecycleApi: {
    deleteWorkspace: vi.fn(),
  },
}));

vi.mock('../features/version-control/VersionControlFeature', () => ({
  VersionControlFeature: {
    Sidebar: () => <div data-testid="version-control-sidebar">version-control-sidebar</div>,
    MainContent: () => <div data-testid="version-control-main">version-control-main</div>,
    Container: ({ children }: { children: React.ReactNode }) => <div data-testid="version-control-container">{children}</div>,
  },
  default: () => <div>version-control-default</div>,
}));

vi.mock('./ChatPanel/ChatPanel', async () => {
  const ReactModule = await vi.importActual<typeof import('react')>('react');
  const { useChatPanelStateContext } = await vi.importActual<typeof import('./ChatPanel/chatPanelStateContext')>('./ChatPanel/chatPanelStateContext');
  const MockChatPanel = () => {
    const React = ReactModule.default;
    const [state, actions] = useChatPanelStateContext();

    React.useEffect(() => {
      mocks.chatMountCount += 1;
    }, [React]);

    return (
      <label>
        chat-draft
        <input
          aria-label="chat-draft"
          value={state.draftMessage}
          onChange={(event) => actions.setDraftMessage(event.target.value)}
        />
      </label>
    );
  };

  return {
    __esModule: true,
    default: MockChatPanel,
  };
});

describe('WorkspaceShell', () => {
  beforeEach(() => {
    mocks.dispatchMock.mockReset();
    mocks.uploadFilesMock.mockClear();
    mocks.chatMountCount = 0;
    mocks.workspaceState.currentFeature = 'custom-feature';
    mocks.workspaceState.chatExpanded = false;
    mocks.workspaceState.rightChatCollapsed = false;
    mocks.workspaceState.canvas.subView = 'web-canvas';
    mocks.workspaceState.versionControl.subView = 'changes';
  });

  it('keeps chat draft and mount instance stable when switching into version-control', async () => {
    const view = render(
      <WorkspaceShell secondColumn={<div data-testid="custom-second-column">second-column</div>}>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    const draftInput = screen.getByLabelText('chat-draft');
    fireEvent.change(draftInput, { target: { value: 'persist me' } });

    expect(draftInput).toHaveValue('persist me');
    expect(mocks.chatMountCount).toBe(1);

    mocks.workspaceState.currentFeature = 'version-control';
    view.rerender(
      <WorkspaceShell secondColumn={<div data-testid="custom-second-column">second-column</div>}>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('version-control-container')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('chat-draft')).toHaveValue('persist me');
    expect(mocks.chatMountCount).toBe(1);
  });

  it('keeps chat draft and mount instance stable when toggling chatExpanded', () => {
    const view = render(
      <WorkspaceShell secondColumn={<div data-testid="custom-second-column">second-column</div>}>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    fireEvent.change(screen.getByLabelText('chat-draft'), { target: { value: 'fullscreen me' } });

    expect(screen.getByLabelText('chat-draft')).toHaveValue('fullscreen me');
    expect(mocks.chatMountCount).toBe(1);

    mocks.workspaceState.chatExpanded = true;
    view.rerender(
      <WorkspaceShell secondColumn={<div data-testid="custom-second-column">second-column</div>}>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.getByLabelText('chat-draft')).toHaveValue('fullscreen me');
    expect(mocks.chatMountCount).toBe(1);
  });
});
