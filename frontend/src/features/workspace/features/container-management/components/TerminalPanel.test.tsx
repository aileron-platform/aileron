import React from 'react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { TerminalPanel } from './TerminalPanel';

const mocks = vi.hoisted(() => ({
  ensureConnected: vi.fn(),
  createTab: vi.fn(),
  closeTab: vi.fn(),
  switchTab: vi.fn(),
  sendInput: vi.fn(),
  sendResize: vi.fn(),
  attachXterm: vi.fn(() => vi.fn()),
  clearTerminal: vi.fn(),
  ensureDefaultTab: vi.fn(),
  state: {
    status: 'open',
    isSynced: true,
    tabs: [
      { tabId: 'tab-1', workingDirectory: '/workspace/project/frontend' },
      { tabId: 'tab-2', workingDirectory: '/workspace/project/backend' },
    ],
    activeTabId: 'tab-1',
    error: null,
  },
}));

vi.mock('@/features/workspace/realtime/useTerminalStream', () => ({
  useTerminalStream: () => ({
    state: mocks.state,
    ensureConnected: mocks.ensureConnected,
    createTab: mocks.createTab,
    closeTab: mocks.closeTab,
    switchTab: mocks.switchTab,
    sendInput: mocks.sendInput,
    sendResize: mocks.sendResize,
    attachXterm: mocks.attachXterm,
    clearTerminal: mocks.clearTerminal,
    ensureDefaultTab: mocks.ensureDefaultTab,
  }),
}));

vi.mock('./TerminalTab', () => ({
  TerminalTab: ({
    tabId,
    isVisible,
    terminalTheme,
  }: {
    tabId: string;
    isVisible?: boolean;
    terminalTheme?: string;
  }) => (
    <div
      data-testid={`terminal-tab-${tabId}`}
      data-visible={String(isVisible)}
      data-terminal-theme={terminalTheme}
    />
  ),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.test',
    },
    state: { versionControl: { selectedGitContextId: null } },
  }),
}));

vi.mock('../../../integrations/version-control/workspaceVersionControlSession', () => {
  return {
    useWorkspaceVersionControlSession: () => ({
      history: {
        useContextsQuery: () => ({ data: { contexts: [] } }),
      },
    }),
  };
});

describe('TerminalPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.classList.remove('dark');
    window.localStorage.removeItem('workspace.terminal.theme');
    mocks.state.status = 'open';
    mocks.state.isSynced = true;
    mocks.state.tabs = [
      { tabId: 'tab-1', workingDirectory: '/workspace/project/frontend' },
      { tabId: 'tab-2', workingDirectory: '/workspace/project/backend' },
    ];
    mocks.state.activeTabId = 'tab-1';
    mocks.state.error = null;
  });

  it('renders full mode with the layout selector', () => {
    const { container } = render(<TerminalPanel variant="full" />);

    expect(screen.getByTestId('terminal-layout-selector')).toBeInTheDocument();
    expect(container.querySelector('svg.lucide-square-terminal')).toBeInTheDocument();
  });

  it('keeps the full mode action menu at the far right of the header actions', () => {
    render(<TerminalPanel variant="full" />);

    const fullscreenButton = screen.getByLabelText('workspace.containerManagement.terminal.actions.enterFullscreen');
    const actionMenuButton = screen.getByLabelText('workspace.containerManagement.terminal.menus.actions');

    expect(
      fullscreenButton.compareDocumentPosition(actionMenuButton) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('renders compact mode without the layout selector and only shows the active tab', () => {
    render(<TerminalPanel variant="compact" />);

    expect(screen.queryByTestId('terminal-layout-selector')).not.toBeInTheDocument();
    expect(screen.getByTestId('compact-terminal-second-layer')).toBeInTheDocument();
    expect(screen.getByTestId('terminal-tab-tab-1')).toHaveAttribute('data-visible', 'true');
    expect(screen.queryByTestId('terminal-tab-tab-2')).not.toBeInTheDocument();
  });

  it('uses the feature-level terminal icon in the compact terminal header', () => {
    render(<TerminalPanel variant="compact" />);

    expect(
      screen.getByTestId('compact-terminal-header-icon').querySelector('svg'),
    ).toHaveClass('lucide-square-terminal');
    expect(
      screen.getByTestId('compact-terminal-header-icon').querySelector('svg.lucide-terminal'),
    ).not.toBeInTheDocument();
  });

  it('aligns the compact terminal icon with the companion feature header icon slot', () => {
    render(<TerminalPanel variant="compact" />);

    expect(screen.getByTestId('compact-terminal-header-icon')).toHaveClass('h-7', 'w-7');
  });

  it('places dock and undock actions in the compact terminal header', () => {
    const onTerminalPlacementChange = vi.fn();
    const { rerender } = render(
      <TerminalPanel
        variant="compact"
        terminalPlacement="side"
        onTerminalPlacementChange={onTerminalPlacementChange}
      />,
    );

    fireEvent.click(screen.getByLabelText('aiChat.companion.dockTerminal'));
    expect(onTerminalPlacementChange).toHaveBeenCalledWith('bottom');

    rerender(
      <TerminalPanel
        variant="compact"
        terminalPlacement="bottom"
        onTerminalPlacementChange={onTerminalPlacementChange}
      />,
    );

    fireEvent.click(screen.getByLabelText('aiChat.companion.undockTerminal'));
    expect(onTerminalPlacementChange).toHaveBeenCalledWith('side');
  });

  it('ensures the terminal connection on mount without disconnecting on unmount', () => {
    const view = render(<TerminalPanel variant="compact" />);

    expect(mocks.ensureConnected).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(mocks.ensureConnected).toHaveBeenCalledTimes(1);
  });

  it('requests a new terminal from compact empty state through the manager queue', () => {
    mocks.state.tabs = [];
    mocks.state.activeTabId = null;

    render(<TerminalPanel variant="compact" />);
    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.containerManagement.terminal.tabs.add',
    }));

    expect(mocks.createTab).toHaveBeenCalledWith({
      workingDirectory: '/workspace',
      size: undefined,
    });
  });

  it('restarts the active terminal in its current working directory with the workspace default as fallback', async () => {
    const user = userEvent.setup();
    render(<TerminalPanel variant="compact" />);

    await user.click(
      screen.getByLabelText('workspace.containerManagement.terminal.menus.actions'),
    );
    const restartAction = await screen.findByText(
      'workspace.containerManagement.terminal.actions.restart',
    );
    const timeout = vi.spyOn(window, 'setTimeout').mockImplementation((callback) => {
      if (typeof callback === 'function') callback();
      return 1;
    });
    await user.click(restartAction);

    expect(mocks.closeTab).toHaveBeenCalledWith('tab-1');
    expect(mocks.createTab).toHaveBeenCalledWith({
      workingDirectory: '/workspace/project/frontend',
      size: undefined,
      fallbackWorkingDirectory: '/workspace',
    });
    timeout.mockRestore();
  });

  it('requests a default terminal through the manager without panel-local queues', () => {
    mocks.state.tabs = [];
    mocks.state.activeTabId = null;

    render(<TerminalPanel variant="compact" />);

    expect(mocks.ensureDefaultTab).toHaveBeenCalledWith('/workspace', undefined);
  });

  it('follows the resolved system theme before the user chooses a terminal theme', () => {
    document.documentElement.classList.add('dark');

    render(<TerminalPanel variant="full" />);

    expect(screen.getByLabelText('workspace.containerManagement.terminal.theme.label')).toBeInTheDocument();
    expect(screen.queryAllByRole('button', {
      name: /workspace\.containerManagement\.terminal\.theme\.options\./,
    })).toHaveLength(2);
    expect(screen.getByLabelText('workspace.containerManagement.terminal.theme.options.dark')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('terminal-tab-tab-1')).toHaveAttribute('data-terminal-theme', 'dark');
  });

  it('persists a chosen terminal theme instead of continuing to follow the system theme', () => {
    document.documentElement.classList.add('dark');

    const view = render(<TerminalPanel variant="full" />);

    expect(screen.getByTestId('terminal-tab-tab-1')).toHaveAttribute('data-terminal-theme', 'dark');

    fireEvent.click(screen.getByLabelText('workspace.containerManagement.terminal.theme.options.light'));

    expect(screen.getByLabelText('workspace.containerManagement.terminal.theme.options.light')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('terminal-tab-tab-1')).toHaveAttribute('data-terminal-theme', 'light');
    expect(window.localStorage.getItem('workspace.terminal.theme')).toBe('light');

    view.unmount();
    document.documentElement.classList.remove('dark');
  });

  it('uses the persisted terminal theme even when the system theme is different', () => {
    window.localStorage.setItem('workspace.terminal.theme', 'dark');

    render(<TerminalPanel variant="full" />);

    expect(screen.getByLabelText('workspace.containerManagement.terminal.theme.options.dark')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('terminal-tab-tab-1')).toHaveAttribute('data-terminal-theme', 'dark');
  });
});
