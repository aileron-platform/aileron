import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceSidebar } from './WorkspaceSidebar';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';

const mocks = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  dispatchMock: vi.fn(),
  workspaceState: {
    currentFeature: 'file-management',
    expandedNavigationItems: [] as string[],
    versionControl: { subView: 'changes' },
    workspaceSettings: { subView: 'general' },
    containerManagement: { subView: 'overview' },
    agentToolSettings: { subView: 'agents' },
  },
  agenticTools: ['claude-code'] as string[],
  operations: new Set<string>(),
}));

const renderSidebar = () => render(
  <>
    <WorkspaceSidebar />
  </>,
);

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mocks.navigateMock,
  };
});

vi.mock('../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: mocks.workspaceState,
    dispatch: mocks.dispatchMock,
    workspaceRuntime: {
      agenticTools: mocks.agenticTools,
      workspaceId: 'ws-1',
    },
    permissions: {
      hasOperation: (operation: string) => mocks.operations.has(operation),
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('WorkspaceSidebar', () => {
  beforeEach(() => {
    mocks.navigateMock.mockReset();
    mocks.dispatchMock.mockReset();
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.expandedNavigationItems = [];
    mocks.agenticTools = ['claude-code'];
    mocks.operations.clear();
    Object.values(OPERATION_IDS).forEach(operation => mocks.operations.add(operation));
  });

  it('renders the supported Codex settings navigation for Codex workspaces', () => {
    mocks.agenticTools = ['codex'];
    mocks.workspaceState.currentFeature = 'codex';
    mocks.workspaceState.expandedNavigationItems = ['codex'];

    renderSidebar();

    expect(screen.getByText('workspace.navigation.main.codexSettings')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.agentsMd')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.claudeCodeSettings.skills')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.subagents')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.prompts')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.claudeCodeSettings.mcp')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.claudeCodeSettings.hooks')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.rules')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.plugins')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.settings')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.subViews.overview')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.subViews.config')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.subViews.permissionsProfiles')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.subViews.managedRequirements')).not.toBeInTheDocument();
  });

  it('renders provider icons for enabled agentic tool settings navigation items', () => {
    mocks.agenticTools = ['claude-code', 'codex', 'opencode'];

    renderSidebar();

    expect(screen.getByText('workspace.navigation.main.claudeCodeSettings')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.main.codexSettings')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.main.opencodeSettings')).toBeInTheDocument();
    expect(document.body.querySelector('img[src="/marketplace/providers/claude-code.png"]')).toBeInTheDocument();
    expect(document.body.querySelector('img[src="/marketplace/providers/codex.png"]')).toBeInTheDocument();
    expect(document.body.querySelector('img[src="/marketplace/providers/opencode.png"]')).toBeInTheDocument();
  });

  it('shows AI Agent as a top-level group with AI Chat and Terminal children', () => {
    mocks.agenticTools = [];
    mocks.workspaceState.expandedNavigationItems = ['ai-agent'];

    renderSidebar();

    expect(screen.getByText('workspace.navigation.main.aiAgent')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.aiAgent.aiChat')).toBeInTheDocument();
    const terminalNavigationItem = screen
      .getByText('workspace.navigation.sub.aiAgent.terminal')
      .closest('button');
    expect(terminalNavigationItem).toBeInTheDocument();
    expect(terminalNavigationItem?.querySelector('svg')).toHaveClass('lucide-square-terminal');
  });

  it('shows only runtime and firewall under Container Management', () => {
    mocks.agenticTools = [];
    mocks.workspaceState.expandedNavigationItems = ['container-management'];

    renderSidebar();

    expect(screen.getByText('workspace.navigation.sub.containerManagement.runtime')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.containerManagement.firewall')).toBeInTheDocument();
    expect(screen.queryByText('workspace.navigation.sub.containerManagement.terminal')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.navigation.sub.containerManagement.browser')).not.toBeInTheDocument();
  });

  it('shows Canvas and Browser as independent top-level navigation items', () => {
    mocks.agenticTools = [];

    renderSidebar();

    fireEvent.click(screen.getByText('workspace.navigation.main.canvas'));
    expect(mocks.navigateMock).toHaveBeenCalledWith('/workspaces/ws-1/canvas');

    fireEvent.click(screen.getByText('workspace.navigation.main.browser'));
    expect(mocks.navigateMock).toHaveBeenCalledWith('/workspaces/ws-1/browser');
  });

  it('toggles the AI Agent parent without navigating to an ai-agent route', () => {
    mocks.agenticTools = [];

    renderSidebar();

    fireEvent.click(screen.getByText('workspace.navigation.main.aiAgent'));

    expect(mocks.navigateMock).not.toHaveBeenCalledWith('/workspaces/ai-agent');
    expect(mocks.dispatchMock).toHaveBeenCalledWith({
      type: 'TOGGLE_NAVIGATION_ITEM',
      payload: 'ai-agent',
    });
  });

  it('marks AI Agent active when its terminal child route is active', () => {
    mocks.agenticTools = [];
    mocks.workspaceState.currentFeature = 'container-management';
    mocks.workspaceState.containerManagement.subView = 'terminal';

    renderSidebar();

    const aiAgentButton = screen.getByText('workspace.navigation.main.aiAgent').closest('button');
    expect(aiAgentButton).toHaveClass('bg-sidebar-primary');
  });

  it('keeps read-only navigation while filtering write and privileged operations', () => {
    mocks.operations.clear();
    mocks.operations.add(OPERATION_IDS.workspaceDetailRead);
    mocks.agenticTools = ['claude-code'];
    mocks.workspaceState.expandedNavigationItems = ['workspace-settings'];

    renderSidebar();

    expect(screen.getByText('workspace.navigation.main.fileManagement')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.main.versionControl')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.main.canvas')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.main.workspaceSettings')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.workspaceSettings.basic')).toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.sub.workspaceSettings.access')).toBeInTheDocument();
    expect(
      screen.getByText('workspace.navigation.sub.workspaceSettings.knowledgeBases'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('workspace.navigation.sub.workspaceSettings.reset'),
    ).not.toBeInTheDocument();
    expect(screen.getByText('workspace.navigation.main.claudeCodeSettings')).toBeInTheDocument();
    expect(screen.queryByText('workspace.navigation.main.aiAgent')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.navigation.main.automation')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.navigation.main.browser')).not.toBeInTheDocument();
    expect(
      screen.queryByText('workspace.navigation.main.containerManagement'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('workspace.navigation.sub.containerManagement.firewall'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('workspace.navigation.sub.containerManagement.runtime'),
    ).not.toBeInTheDocument();
  });

  it('shows only Firewall under Container Management for a firewall reader', () => {
    mocks.operations.clear();
    mocks.operations.add(OPERATION_IDS.workspaceDetailRead);
    mocks.operations.add(OPERATION_IDS.workspaceFirewallRead);
    mocks.agenticTools = [];
    mocks.workspaceState.expandedNavigationItems = ['container-management'];

    renderSidebar();

    expect(
      screen.getByText('workspace.navigation.main.containerManagement'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('workspace.navigation.sub.containerManagement.firewall'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('workspace.navigation.sub.containerManagement.runtime'),
    ).not.toBeInTheDocument();
  });
});
