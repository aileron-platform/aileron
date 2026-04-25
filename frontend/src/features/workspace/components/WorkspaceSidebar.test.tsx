import { render, screen, within } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceSidebar } from './WorkspaceSidebar';

const mocks = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  dispatchMock: vi.fn(),
  workspaceState: {
    currentFeature: 'openspec',
    sidebarCollapsed: false,
    expandedNavigationItems: ['openspec'],
    versionControl: { subView: 'changes' },
    openspec: { subView: 'in-progress' },
    workspaceSettings: { subView: 'general' },
    containerManagement: { subView: 'overview' },
    claudeCodeSettings: { subView: 'memory' },
    agentToolSettings: { subView: 'agents' },
    canvas: { subView: 'browser' },
  },
  summary: {
    workspaceId: 'ws-1',
    initialized: true,
    counts: {
      inProgress: 4,
      complete: 2,
      archived: 1,
    },
  },
}));

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
      cliType: 'claude-code',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../features/openspec/OpenSpecWorkspaceContext', () => ({
  useOpenSpecWorkspace: () => ({
    summary: mocks.summary,
  }),
}));

describe('WorkspaceSidebar', () => {
  beforeEach(() => {
    mocks.navigateMock.mockReset();
    mocks.dispatchMock.mockReset();
    mocks.workspaceState.currentFeature = 'openspec';
    mocks.workspaceState.sidebarCollapsed = false;
    mocks.workspaceState.expandedNavigationItems = ['openspec'];
    mocks.workspaceState.openspec.subView = 'in-progress';
    mocks.summary.initialized = true;
    mocks.summary.counts = {
      inProgress: 4,
      complete: 2,
      archived: 1,
    };
  });

  it('renders OpenSpec subview counts from summary data', () => {
    render(<WorkspaceSidebar />);

    const inProgressButton = screen.getByText('workspace.navigation.sub.openspec.inProgress').closest('button');
    const completeButton = screen.getByText('workspace.navigation.sub.openspec.complete').closest('button');
    const archivedButton = screen.getByText('workspace.navigation.sub.openspec.archived').closest('button');

    expect(inProgressButton).not.toBeNull();
    expect(completeButton).not.toBeNull();
    expect(archivedButton).not.toBeNull();

    expect(within(inProgressButton!).getByText('4')).toBeInTheDocument();
    expect(within(completeButton!).getByText('2')).toBeInTheDocument();
    expect(within(archivedButton!).getByText('1')).toBeInTheDocument();
  });
});
