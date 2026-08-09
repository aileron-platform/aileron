import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@/__tests__/utils/render';
import { WorkspaceShell as WorkspaceShellSubject } from './WorkspaceShell';
import { workspaceShellLayoutStorage, WORKSPACE_SHELL_LAYOUT_DEFAULTS } from '../storage/workspaceShellLayoutStorage';

const WorkspaceShell = (
  props: Omit<React.ComponentProps<typeof WorkspaceShellSubject>, 'navigationSlot'>,
) => (
  <WorkspaceShellSubject
    {...props}
    navigationSlot={<div data-testid="global-navigation">global-navigation</div>}
  />
);

const getShellRegion = (region: 'navigation' | 'navigator' | 'main' | 'companion'): HTMLElement => {
  const element = screen.getByTestId('product-shell').querySelector(`[data-shell-region="${region}"]`);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing ProductShell region: ${region}`);
  }
  return element;
};

const initialInnerWidth = window.innerWidth;

const queryShellRegion = (region: 'navigation' | 'navigator' | 'main' | 'companion'): HTMLElement | null => {
  const element = screen.getByTestId('product-shell').querySelector(`[data-shell-region="${region}"]`);
  return element instanceof HTMLElement ? element : null;
};

const mocks = vi.hoisted(() => ({
  dispatchMock: vi.fn(),
  uploadFilesMock: vi.fn(async () => ({ success: true, message: 'ok', data: { uploadedPaths: [] } })),
  workspaceState: {
    companionActiveTab: 'ai-chat' as 'ai-chat' | 'terminal',
    companionTerminalPlacement: 'side' as 'side' | 'bottom',
    chatExpanded: false,
    fileManagementEditorExpanded: false,
    currentFeature: 'custom-feature',
    agentToolSettings: { subView: '' },
    versionControl: { subView: 'changes', selectedGitContextId: null },
    workspaceSettings: { subView: 'basic' },
    containerManagement: { subView: 'runtime' },
    expandedNavigationItems: [],
    fileTreeShowHiddenEntries: false,
  },
  workspaceRuntime: {
    workspaceId: 'ws-1',
    workspaceName: 'Workspace One',
    runtimeBaseUrl: 'http://runtime.test',
    agenticTools: ['claude-code'],
    runtimeStatus: 'running',
    isLoading: false,
    error: null,
    reload: vi.fn(),
  },
  allowedOperations: new Set<string>(),
}));

vi.mock('./WorkspaceCompanionColumn', () => ({
  WorkspaceCompanionHeader: () => <div data-testid="workspace-companion-header" />,
  WorkspaceCompanionCollapsedContent: () => null,
  WorkspaceCompanionColumn: ({
    activeTab,
    canUseAgentChat,
    canUseTerminal,
    isExpanded,
    terminalPlacement,
    onActiveTabChange,
    onTerminalPlacementChange,
    onToggleExpand,
    onToggleCollapse,
  }: {
    activeTab: 'ai-chat' | 'terminal';
    canUseAgentChat: boolean;
    canUseTerminal: boolean;
    isExpanded: boolean;
    terminalPlacement?: 'side' | 'bottom';
    onActiveTabChange: (tab: 'ai-chat' | 'terminal') => void;
    onTerminalPlacementChange?: (placement: 'side' | 'bottom') => void;
    onToggleExpand: () => void;
    onToggleCollapse?: () => void;
  }) => (
    <div
      data-testid="workspace-companion-column"
      data-active-tab={activeTab}
      data-can-use-agent-chat={String(canUseAgentChat)}
      data-can-use-terminal={String(canUseTerminal)}
      data-expanded={String(isExpanded)}
      data-terminal-placement={terminalPlacement}
    >
      <button type="button" onClick={() => onActiveTabChange('terminal')}>switch-terminal</button>
      <button type="button" onClick={() => onTerminalPlacementChange?.('bottom')}>dock-terminal</button>
      <button type="button" onClick={() => onTerminalPlacementChange?.('side')}>undock-terminal</button>
      <button type="button" onClick={onToggleExpand}>expand-companion</button>
      <button type="button" onClick={onToggleCollapse}>collapse-companion</button>
    </div>
  ),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('../providers/WorkspaceProvider', () => ({
  useWorkspace: () => {
    const hasOperation = (operation: string) => (
      mocks.allowedOperations.has(operation)
    );

    return {
      state: mocks.workspaceState,
      dispatch: mocks.dispatchMock,
      permissions: {
        accessRole: hasOperation('workspace.detail.read') ? 'owner' : null,
        canRead: hasOperation('workspace.detail.read'),
        canWrite: hasOperation('workspace.content.write'),
        canRunLifecycle: hasOperation('workspace.lifecycle.execute'),
        canUpdateMetadata: hasOperation('workspace.metadata.write'),
        canDelete: hasOperation('workspace.delete'),
        canManageSettings: hasOperation('workspace.access.manage'),
        canWriteAttachments: hasOperation('workspace.attachment.write'),
        canReadFirewall: hasOperation('workspace.firewall.read'),
        canManageFirewall: hasOperation('workspace.firewall.manage'),
        canUseChat: hasOperation('workspace.agent_chat.use'),
        canUseTerminal: hasOperation('workspace.terminal.use'),
        canUseBrowser: hasOperation('workspace.browser_automation.use'),
        canUseSensitiveSettings: hasOperation(
          'workspace.sensitive_settings.manage',
        ),
        hasOperation,
      },
      workspaceRuntime: mocks.workspaceRuntime,
      fileTreeActions: {
        uploadFiles: mocks.uploadFilesMock,
      },
    };
  },
}));

vi.mock('./WorkspaceSidebar', () => ({
  WorkspaceSidebar: () => <div data-testid="workspace-sidebar">sidebar</div>,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/features/auth/public', () => ({
  AuthorizationDeniedState: () => <div data-testid="authorization-denied" />,
}));

vi.mock('../features/agent-settings/AgentSettingsPage', () => ({
  default: ({
    toolId,
    documentSelectedId,
    onDocumentDirtyChange,
    documentSelectionBlocked,
  }: {
    toolId?: string;
    documentSelectedId?: string | null;
    onDocumentDirtyChange?: (dirty: boolean) => void;
    documentSelectionBlocked?: boolean;
  }) => (
    <div data-testid="agent-settings-feature" data-tool-id={toolId}>
      <span data-testid="selected-document-id">{documentSelectedId ?? 'no-document-selected'}</span>
      <span data-testid="document-selection-blocked">{documentSelectionBlocked ? 'blocked' : 'clear'}</span>
      <button type="button" onClick={() => onDocumentDirtyChange?.(true)}>dirty-on</button>
      <button type="button" onClick={() => onDocumentDirtyChange?.(false)}>dirty-off</button>
    </div>
  ),
}));

vi.mock('../features/agent-settings/components/CodexDocumentSidebar', () => ({
  default: ({ onSelect }: { onSelect: (id: string | null) => void }) => (
    <button type="button" data-testid="codex-document-sidebar" onClick={() => onSelect('user:opsx-apply.md')}>
      codex-document-sidebar
    </button>
  ),
}));

vi.mock('../features/agent-settings/components/AgentDocumentSidebar', () => ({
  default: ({ resource, onSelect }: { resource: string; onSelect: (id: string | null) => void }) => (
    <button
      type="button"
      data-testid={`agent-document-sidebar-${resource}`}
      onClick={() => onSelect('project:agent-selected.md')}
    >
      agent-document-sidebar
    </button>
  ),
}));

vi.mock('../features/browser/BrowserPage', () => ({
  default: () => <div data-testid="browser-feature">browser-feature</div>,
  BrowserPage: () => <div data-testid="browser-feature">browser-feature</div>,
}));

vi.mock('../features/canvas/WebCanvasPage', () => ({
  WebCanvasPage: () => <div data-testid="web-canvas-feature">web-canvas-feature</div>,
}));

vi.mock('../realtime/WorkspaceRealtimeProvider', () => ({
  WorkspaceRealtimeProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="workspace-realtime-provider">{children}</div>
  ),
}));

vi.mock('./WorkspaceRuntimeErrorPage', () => ({
  WorkspaceRuntimeErrorPage: ({ error }: { error: string }) => (
    <div data-testid="runtime-error-page">
      {error}
    </div>
  ),
}));

vi.mock('../features/version-control/VersionControlPage', () => ({
  VersionControlSidebar: () => <div data-testid="version-control-sidebar">version-control-sidebar</div>,
  VersionControlMainContent: () => <div data-testid="version-control-main">version-control-main</div>,
  VersionControlProvider: ({ children }: { children: React.ReactNode }) => <div data-testid="version-control-container">{children}</div>,
  default: () => <div>version-control-default</div>,
}));

describe('WorkspaceShell', () => {
  afterEach(() => {
    workspaceShellLayoutStorage.clear('ws-1');
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: initialInnerWidth,
    });
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1440,
    });
    mocks.dispatchMock.mockReset();
    mocks.uploadFilesMock.mockClear();
    mocks.workspaceState.currentFeature = 'custom-feature';
    mocks.workspaceState.companionActiveTab = 'ai-chat';
    mocks.workspaceState.companionTerminalPlacement = 'side';
    mocks.workspaceState.chatExpanded = false;
    mocks.workspaceState.fileManagementEditorExpanded = false;
    mocks.workspaceState.agentToolSettings.subView = '';
    mocks.workspaceState.versionControl.subView = 'changes';
    mocks.workspaceState.containerManagement.subView = 'runtime';
    mocks.workspaceRuntime.workspaceId = 'ws-1';
    mocks.workspaceRuntime.workspaceName = 'Workspace One';
    mocks.workspaceRuntime.runtimeBaseUrl = 'http://runtime.test';
    mocks.workspaceRuntime.agenticTools = ['claude-code'];
    mocks.workspaceRuntime.runtimeStatus = 'running';
    mocks.workspaceRuntime.isLoading = false;
    mocks.workspaceRuntime.error = null;
    mocks.allowedOperations.clear();
    [
      'workspace.detail.read',
      'workspace.content.write',
      'workspace.lifecycle.execute',
      'workspace.metadata.write',
      'workspace.delete',
      'workspace.access.manage',
      'workspace.attachment.write',
      'workspace.sensitive_settings.manage',
      'workspace.agent_chat.use',
      'workspace.terminal.use',
      'workspace.automation.execute',
      'workspace.browser_automation.use',
    ].forEach(operation => mocks.allowedOperations.add(operation));
    workspaceShellLayoutStorage.clear('ws-1');
  });

  it('keeps the companion mounted when switching into version-control', async () => {
    const originalInnerWidth = window.innerWidth;
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1440,
    });

    const view = render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.getByTestId('workspace-companion-column')).toBeInTheDocument();

    mocks.workspaceState.currentFeature = 'version-control';
    view.rerender(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('version-control-container')).toBeInTheDocument();
    }, { timeout: 10_000 });

    expect(screen.getByTestId('workspace-companion-column')).toBeInTheDocument();
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: originalInnerWidth,
    });
  });

  it('does not mount terminal realtime providers without terminal capability', () => {
    mocks.allowedOperations.delete('workspace.terminal.use');

    render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.queryByTestId('workspace-realtime-provider')).not.toBeInTheDocument();
    expect(screen.getByTestId('workspace-companion-column')).toHaveAttribute(
      'data-can-use-terminal',
      'false',
    );
    expect(screen.getByTestId('workspace-companion-column')).toHaveAttribute(
      'data-can-use-agent-chat',
      'true',
    );
  });

  it('does not mount companion content when chat and terminal capabilities are absent', () => {
    mocks.allowedOperations.delete('workspace.agent_chat.use');
    mocks.allowedOperations.delete('workspace.terminal.use');

    render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.queryByTestId('workspace-realtime-provider')).not.toBeInTheDocument();
    expect(screen.queryByTestId('workspace-companion-column')).not.toBeInTheDocument();
  });

  it('renders a terminal-only companion when chat capability is absent', () => {
    mocks.allowedOperations.delete('workspace.agent_chat.use');

    render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.getByTestId('workspace-companion-column')).toHaveAttribute(
      'data-active-tab',
      'terminal',
    );
    expect(screen.getByTestId('workspace-companion-column')).toHaveAttribute(
      'data-can-use-agent-chat',
      'false',
    );
    expect(screen.getByTestId('workspace-companion-column')).toHaveAttribute(
      'data-can-use-terminal',
      'true',
    );
  });

  it('renders Browser as an independent workspace feature', async () => {
    mocks.workspaceState.currentFeature = 'browser';

    render(<WorkspaceShell />);

    expect(await screen.findByTestId(
      'browser-feature',
      undefined,
      { timeout: 10_000 },
    )).toBeInTheDocument();
    expect(screen.queryByTestId('web-canvas-feature')).not.toBeInTheDocument();
  });

  it.each([
    ['workspace-settings', 'basic'],
    ['workspace-settings', 'access'],
    ['workspace-settings', 'knowledge-bases'],
    ['workspace-settings', 'reset'],
    ['container-management', 'runtime'],
    ['container-management', 'firewall'],
    ['workspace-automation', ''],
    ['canvas', ''],
    ['browser', ''],
    ['claude-code', 'claude-md'],
    ['claude-code', 'mcp'],
    ['claude-code', 'hooks'],
    ['claude-code', 'plugins'],
    ['claude-code', 'settings'],
    ['codex', 'agents-md'],
    ['codex', 'mcp'],
    ['codex', 'hooks'],
    ['codex', 'plugins'],
    ['codex', 'settings'],
    ['opencode', 'agents-md'],
    ['opencode', 'mcp'],
  ])('hides the empty second column for %s/%s', (feature, subView) => {
    mocks.workspaceState.currentFeature = feature;
    mocks.workspaceState.agentToolSettings.subView = subView;

    render(<WorkspaceShell />);

    expect(queryShellRegion('navigator')).not.toBeInTheDocument();
  });

  it('keeps the companion region constrained so its content remains visible', () => {
    render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(getShellRegion('companion')).toHaveClass('h-full', 'min-h-0');
  });

  it('keeps the companion mounted when toggling chatExpanded', () => {
    const view = render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.getByTestId('workspace-companion-column')).toBeInTheDocument();

    mocks.workspaceState.chatExpanded = true;
    view.rerender(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(screen.getByTestId('workspace-companion-column')).toBeInTheDocument();
  });

  it('renders the collapsed companion without mounting a chat session', () => {
    render(<WorkspaceShell />);
    fireEvent.click(screen.getByRole('button', { name: 'aiChat.companion.collapse' }));

    expect(getShellRegion('companion')).toHaveStyle({ width: '48px' });
    expect(screen.queryByTestId('workspace-companion-column')).not.toBeInTheDocument();
  });

  it('keeps the injected navigation as the first child in the normal shell', () => {
    render(<WorkspaceShell />);

    const navigation = screen.getByTestId('global-navigation');
    expect(screen.getByTestId('product-shell')).toHaveClass('h-screen', 'w-screen', 'flex', 'flex-col');
    expect(navigation.parentElement).toHaveAttribute('data-shell-top-bar');
    expect(navigation.parentElement?.parentElement?.firstElementChild).toBe(navigation.parentElement);
  });

  it('keeps the injected navigation in the runtime error branch', () => {
    mocks.workspaceRuntime.runtimeBaseUrl = null;
    mocks.workspaceRuntime.error = 'runtime-unavailable';

    render(<WorkspaceShell />);

    expect(screen.getByTestId('global-navigation')).toBeInTheDocument();
    expect(screen.getByTestId('runtime-error-page')).toHaveTextContent('runtime-unavailable');
  });

  it('positions the chat panel as a viewport overlay when expanded', () => {
    mocks.workspaceState.chatExpanded = true;

    render(<WorkspaceShell />);

    const chatColumn = getShellRegion('companion');
    expect(chatColumn).toHaveClass('fixed', 'inset-0', 'z-50');
    expect(chatColumn).not.toHaveClass('relative');
  });

  it('keeps fixed workspace columns from shrinking while resizing', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    render(<WorkspaceShell />);

    expect(getShellRegion('navigation')).toHaveClass('shrink-0');
    expect(getShellRegion('navigator')).toHaveClass('shrink-0');
    expect(getShellRegion('companion')).toHaveClass('shrink-0');
  });

  it('clamps the right chat column so nav, second column, companion, and main content fit', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    const originalInnerWidth = window.innerWidth;
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1440,
    });

    const { container } = render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    const resizeHandles = container.querySelectorAll('.cursor-col-resize');
    const rightChatResizeHandle = resizeHandles[2];
    expect(rightChatResizeHandle).toBeTruthy();

    fireEvent.mouseDown(rightChatResizeHandle, { clientX: 900 });
    fireEvent.mouseMove(document, { clientX: 600 });

    expect(getShellRegion('companion')).toHaveStyle({ width: '610px' });

    fireEvent.mouseUp(document);
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: originalInnerWidth,
    });
  });

  it('allows the left navigation and second column to shrink across a practical range', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    const { container } = render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    const resizeHandles = container.querySelectorAll('.cursor-col-resize');

    fireEvent.mouseDown(resizeHandles[0], { clientX: 240 });
    fireEvent.mouseMove(document, { clientX: 60 });
    expect(getShellRegion('navigation')).toHaveStyle({ width: '240px' });
    fireEvent.mouseUp(document);

    fireEvent.mouseDown(resizeHandles[1], { clientX: 560 });
    fireEvent.mouseMove(document, { clientX: 360 });
    expect(getShellRegion('navigator')).toHaveStyle({ width: '270px' });
    fireEvent.mouseUp(document);
  });

  it('continues resizing across multiple pointer moves and respects the dynamic maximum', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    const { container } = render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    const resizeHandles = container.querySelectorAll('.cursor-col-resize');

    fireEvent.mouseDown(resizeHandles[0], { clientX: 240 });
    fireEvent.mouseMove(document, { clientX: 320 });
    expect(getShellRegion('navigation')).toHaveStyle({ width: '320px' });

    fireEvent.mouseMove(document, { clientX: 600 });
    expect(getShellRegion('navigation')).toHaveStyle({ width: '500px' });

    fireEvent.mouseUp(document);
  });

  it('keeps column width transitions enabled while dragging a resize handle', () => {
    const { container } = render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    const leftNavigationColumn = getShellRegion('navigation');
    expect(leftNavigationColumn).toHaveClass('transition-[width]', 'duration-200');

    const resizeHandles = container.querySelectorAll('.cursor-col-resize');
    fireEvent.mouseDown(resizeHandles[0], { clientX: 240 });

    expect(leftNavigationColumn).toHaveClass('transition-[width]', 'duration-200');

    fireEvent.mouseUp(document);
  });

  it('blocks document selection while detail edits are dirty and clears the block after save', async () => {
    mocks.workspaceState.currentFeature = 'opencode';
    mocks.workspaceState.agentToolSettings.subView = 'slash-commands';
    mocks.workspaceRuntime.agenticTools = ['opencode'];

    render(<WorkspaceShell />);

    await screen.findByTestId('agent-settings-feature');
    fireEvent.click(screen.getByRole('button', { name: 'dirty-on' }));
    fireEvent.click(await screen.findByTestId('agent-document-sidebar-slash-commands'));

    expect(screen.getByTestId('selected-document-id')).toHaveTextContent('no-document-selected');
    expect(screen.getByTestId('document-selection-blocked')).toHaveTextContent('blocked');

    fireEvent.click(screen.getByRole('button', { name: 'dirty-off' }));

    expect(screen.getByTestId('document-selection-blocked')).toHaveTextContent('clear');
  });

  it('lets file management editor occupy the workspace when expanded', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.fileManagementEditorExpanded = true;

    render(
      <WorkspaceShell>
        <div data-testid="custom-main-content">main-content</div>
      </WorkspaceShell>,
    );

    expect(queryShellRegion('navigator')).not.toBeInTheDocument();
    expect(screen.queryByTestId('global-navigation')).not.toBeInTheDocument();
    expect(screen.getByTestId('custom-main-content')).toBeInTheDocument();
    expect(getShellRegion('main')).toHaveClass('min-w-0');
    expect(queryShellRegion('companion')).not.toBeInTheDocument();
  });

  it('passes Codex document sidebar selection into the settings content column', async () => {
    mocks.workspaceState.currentFeature = 'codex';
    mocks.workspaceState.agentToolSettings.subView = 'prompts';
    mocks.workspaceRuntime.agenticTools = ['codex'];

    render(<WorkspaceShell />);

    expect(await screen.findByTestId('agent-settings-feature')).toHaveTextContent('no-document-selected');

    fireEvent.click(await screen.findByTestId('codex-document-sidebar'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-settings-feature')).toHaveTextContent('user:opsx-apply.md');
    });
  });

  it('uses the selected Codex navigation feature instead of the runtime default tool', async () => {
    mocks.workspaceState.currentFeature = 'codex';
    mocks.workspaceState.agentToolSettings.subView = 'agents-md';
    mocks.workspaceRuntime.agenticTools = ['claude-code'];

    render(<WorkspaceShell />);

    expect(await screen.findByTestId('agent-settings-feature')).toHaveAttribute('data-tool-id', 'codex');
  });

  it('uses the outer Codex document sidebar for rules so the page does not render a nested sidebar', async () => {
    mocks.workspaceState.currentFeature = 'codex';
    mocks.workspaceState.agentToolSettings.subView = 'rules';
    mocks.workspaceRuntime.agenticTools = ['codex'];

    render(<WorkspaceShell />);

    expect(await screen.findByTestId('agent-settings-feature')).toBeInTheDocument();
    expect(getShellRegion('navigator')).toBeInTheDocument();
    expect(screen.getByTestId('codex-document-sidebar')).toBeInTheDocument();
  });

  it('uses the outer OpenCode document sidebar for slash commands', async () => {
    mocks.workspaceState.currentFeature = 'opencode';
    mocks.workspaceState.agentToolSettings.subView = 'slash-commands';
    mocks.workspaceRuntime.agenticTools = ['opencode'];

    render(<WorkspaceShell />);

    expect(await screen.findByTestId('agent-settings-feature')).toHaveTextContent('no-document-selected');
    expect(getShellRegion('navigator')).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId('agent-document-sidebar-slash-commands'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-settings-feature')).toHaveTextContent('project:agent-selected.md');
    });
  });

  it('uses the outer Claude document sidebar for output styles', async () => {
    mocks.workspaceState.currentFeature = 'claude-code';
    mocks.workspaceState.agentToolSettings.subView = 'output-styles';
    mocks.workspaceRuntime.agenticTools = ['claude-code'];

    render(<WorkspaceShell />);

    expect(await screen.findByTestId('agent-settings-feature')).toHaveTextContent('no-document-selected');
    expect(getShellRegion('navigator')).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId('agent-document-sidebar-output-styles'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-settings-feature')).toHaveTextContent('project:agent-selected.md');
    });
  });

  it('uses the outer OpenCode document sidebar for subagents', async () => {
    mocks.workspaceState.currentFeature = 'opencode';
    mocks.workspaceState.agentToolSettings.subView = 'subagents';
    mocks.workspaceRuntime.agenticTools = ['opencode'];

    render(<WorkspaceShell />);

    expect(await screen.findByTestId('agent-settings-feature')).toHaveTextContent('no-document-selected');
    expect(getShellRegion('navigator')).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId('agent-document-sidebar-subagents'));

    await waitFor(() => {
      expect(screen.getByTestId('agent-settings-feature')).toHaveTextContent('project:agent-selected.md');
    });
  });

  it('does not render the companion chat column on the AI Chat home feature', () => {
    mocks.workspaceState.currentFeature = 'ai-chat-home';

    render(<WorkspaceShell />);

    expect(queryShellRegion('companion')).not.toBeInTheDocument();
  });

  it('does not render the companion column on the container terminal page', () => {
    mocks.workspaceState.currentFeature = 'container-management';
    mocks.workspaceState.containerManagement.subView = 'terminal';

    render(<WorkspaceShell />);

    expect(queryShellRegion('companion')).not.toBeInTheDocument();
  });

  it('uses a two-column full terminal layout after selecting AI Agent Terminal navigation', () => {
    mocks.workspaceState.currentFeature = 'container-management';
    mocks.workspaceState.containerManagement.subView = 'terminal';
    mocks.workspaceState.companionActiveTab = 'terminal';

    render(<WorkspaceShell />);

    expect(screen.getByTestId('workspace-sidebar')).toBeInTheDocument();
    expect(getShellRegion('main')).toBeInTheDocument();
    expect(queryShellRegion('navigator')).not.toBeInTheDocument();
    expect(queryShellRegion('companion')).not.toBeInTheDocument();
  });

  it('persists companion tab selection through workspace state', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'ai-chat';

    render(<WorkspaceShell />);

    fireEvent.click(screen.getByText('switch-terminal'));

    expect(mocks.dispatchMock).toHaveBeenCalledWith({
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'terminal',
    });
  });

  it('toggles companion expanded state from the feature header', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.chatExpanded = false;

    render(<WorkspaceShell />);

    fireEvent.click(screen.getByText('expand-companion'));

    expect(mocks.dispatchMock).toHaveBeenCalledWith({
      type: 'TOGGLE_CHAT_EXPANDED',
    });
  });

  it('renders terminal as a bottom dock through the shared companion region', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 1000,
      height: 900,
      top: 0,
      left: 0,
      right: 1000,
      bottom: 900,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(queryShellRegion('companion')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-companion-column')).toBeInTheDocument();
    expect(getShellRegion('companion')).toHaveStyle({ height: '240px' });
    expect(
      within(getShellRegion('companion')).getByRole('separator', {
        name: 'aiChat.companion.resizeTerminalDock',
      }),
    ).toBeInTheDocument();
  });

  it('does not render the companion header when terminal is docked at the bottom', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    const companion = getShellRegion('companion');
    expect(within(companion).queryByTestId('shell-companion-header')).not.toBeInTheDocument();
    expect(within(companion).queryByTestId('workspace-companion-header')).not.toBeInTheDocument();
  });

  it('removes the companion header during a side-to-bottom Terminal transition', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'side';

    const view = render(<WorkspaceShell>main</WorkspaceShell>);
    expect(screen.getByTestId('workspace-companion-header')).toBeInTheDocument();

    mocks.workspaceState.companionTerminalPlacement = 'bottom';
    view.rerender(<WorkspaceShell>main</WorkspaceShell>);

    const companion = getShellRegion('companion');
    expect(within(companion).queryByTestId('workspace-companion-header')).not.toBeInTheDocument();
    expect(within(companion).queryByTestId('shell-companion-header')).not.toBeInTheDocument();
  });

  it('keeps the AI Chat companion header when the stored Terminal preference is bottom', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'ai-chat';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(screen.getByTestId('workspace-companion-header')).toBeInTheDocument();
    expect(getShellRegion('companion')).toHaveStyle({ width: '408px' });
  });

  it('resizes terminal dock height through shared shell state', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 1000,
      height: 900,
      top: 0,
      left: 0,
      right: 1000,
      bottom: 900,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    fireEvent.mouseDown(within(getShellRegion('companion')).getByRole('separator'), { clientY: 400 });
    fireEvent.mouseMove(document, { clientY: 450 });
    fireEvent.mouseUp(document);

    expect(getShellRegion('companion')).toHaveStyle({ height: '190px' });
  });

  it('switches back to side companion for ai chat while preserving bottom preference', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'ai-chat';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(screen.getByTestId('workspace-companion-column')).toBeInTheDocument();
    expect(queryShellRegion('main')).toBeInTheDocument();
  });

  it('dispatches terminal placement changes from the companion header', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'side';

    render(<WorkspaceShell>main</WorkspaceShell>);

    fireEvent.click(screen.getByRole('button', { name: 'dock-terminal' }));

    expect(mocks.dispatchMock).toHaveBeenCalledWith({
      type: 'SET_COMPANION_TERMINAL_PLACEMENT',
      payload: 'bottom',
    });
  });

  it('renders fullscreen overlay instead of bottom dock when expanded', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';
    mocks.workspaceState.chatExpanded = true;

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(getShellRegion('companion')).toHaveClass('fixed');
    expect(queryShellRegion('main')).not.toBeInTheDocument();
  });

  it('preserves ai chat fullscreen overlay when expanded', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'ai-chat';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';
    mocks.workspaceState.chatExpanded = true;

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(getShellRegion('companion')).toHaveClass('fixed');
    expect(screen.getByTestId('workspace-companion-column')).toHaveAttribute('data-active-tab', 'ai-chat');
  });

  it('does not render a companion region on the full terminal route', () => {
    mocks.workspaceState.currentFeature = 'container-management';
    mocks.workspaceState.containerManagement.subView = 'terminal';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(screen.getByTestId('workspace-realtime-provider')).toBeInTheDocument();
    expect(queryShellRegion('companion')).not.toBeInTheDocument();
  });

  it('does not render an empty companion region while workspace runtime is pending', () => {
    mocks.workspaceRuntime.workspaceId = null;
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(queryShellRegion('companion')).not.toBeInTheDocument();
  });

  it('clamps bottom dock resizing at the workspace maximum height', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 1000,
      height: 900,
      top: 0,
      left: 0,
      right: 1000,
      bottom: 900,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    fireEvent.mouseDown(within(getShellRegion('companion')).getByRole('separator'), {
      clientY: 600,
    });
    fireEvent.mouseMove(document, { clientY: 0 });
    fireEvent.mouseUp(document);

    expect(getShellRegion('companion')).toHaveStyle({ height: '520px' });
  });

  it('keeps the dock minimum height in extremely short layout containers', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 1000,
      height: 360,
      top: 0,
      left: 0,
      right: 1000,
      bottom: 360,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    workspaceShellLayoutStorage.save('ws-1', {
      ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
      companionHeight: 520,
    });
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(getShellRegion('companion')).toHaveStyle({ height: '160px' });
  });

  it('keeps the dock minimum height when the layout container height is zero', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 1000,
      height: 0,
      top: 0,
      left: 0,
      right: 1000,
      bottom: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    workspaceShellLayoutStorage.save('ws-1', {
      ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
      companionHeight: 520,
    });
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(getShellRegion('companion')).toHaveStyle({ height: '160px' });
  });

  it('re-clamps dock height when the viewport is resized', () => {
    let layoutHeight = 900;
    const rectSpy = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({
      width: 1000,
      height: layoutHeight,
      top: 0,
      left: 0,
      right: 1000,
      bottom: layoutHeight,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }));
    workspaceShellLayoutStorage.save('ws-1', {
      ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
      companionHeight: 520,
    });
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'terminal';
    mocks.workspaceState.companionTerminalPlacement = 'bottom';

    render(<WorkspaceShell>main</WorkspaceShell>);
    expect(getShellRegion('companion')).toHaveStyle({ height: '520px' });

    layoutHeight = 360;
    fireEvent.resize(window);

    expect(rectSpy).toHaveBeenCalled();
    expect(getShellRegion('companion')).toHaveStyle({ height: '160px' });
  });

  it('renders the nav sidebar and second column at the shared shell default widths', () => {
    mocks.workspaceState.currentFeature = 'file-management';

    render(<WorkspaceShell>main</WorkspaceShell>);

    const sidebarColumn = getShellRegion('navigation');
    expect(sidebarColumn).toHaveStyle({ width: '240px' });
    expect(getShellRegion('navigator')).toHaveStyle({ width: '270px' });
  });

  it('shrinks the nav sidebar when dragging its resize handle, clamped to the workspace minimum', () => {
    mocks.workspaceState.currentFeature = 'file-management';

    render(<WorkspaceShell>main</WorkspaceShell>);

    const sidebarColumn = getShellRegion('navigation');
    const handle = sidebarColumn.querySelector('[role="separator"]') as HTMLElement;
    fireEvent.mouseDown(handle, { clientX: 400 });
    fireEvent.mouseMove(document, { clientX: 0 });
    fireEvent.mouseUp(document);

    expect(sidebarColumn).toHaveStyle({ width: '240px' });
  });

  it('persists nav sidebar width to workspaceShellLayoutStorage after a debounced delay', () => {
    vi.useFakeTimers();
    mocks.workspaceState.currentFeature = 'file-management';

    render(<WorkspaceShell>main</WorkspaceShell>);

    const sidebarColumn = getShellRegion('navigation');
    const handle = sidebarColumn.querySelector('[role="separator"]') as HTMLElement;
    fireEvent.mouseDown(handle, { clientX: 400 });
    fireEvent.mouseMove(document, { clientX: 500 });
    fireEvent.mouseUp(document);

    vi.advanceTimersByTime(600);

    const saved = JSON.parse(localStorage.getItem('shell_layout_workspace_ws-1') ?? '{}');
    expect(saved.data.navSidebarWidth).toBe(340);
  });

  it('restores a persisted nav sidebar width on mount', () => {
    localStorage.setItem('shell_layout_workspace_ws-1', JSON.stringify({
      version: '1',
      data: {
        navSidebarCollapsed: false,
        navSidebarWidth: 300,
        secondColumnCollapsed: false,
        secondColumnWidth: 320,
        companionCollapsed: false,
        companionWidth: 408,
        companionHeight: 240,
        companionPlacement: 'side',
      },
    }));
    mocks.workspaceState.currentFeature = 'file-management';

    render(<WorkspaceShell>main</WorkspaceShell>);

    const sidebarColumn = getShellRegion('navigation');
    expect(sidebarColumn).toHaveStyle({ width: '300px' });
  });

  it('renders the companion side placement at the workspace minimum width of 408px, not the shared default', () => {
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.companionActiveTab = 'ai-chat';

    render(<WorkspaceShell>main</WorkspaceShell>);

    expect(getShellRegion('companion')).toHaveStyle({ width: '408px' });
  });

});
