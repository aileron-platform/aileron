import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@/__tests__/utils/render';
import { render } from '@/__tests__/utils/render';
import { WorkspaceBasicSettings } from './WorkspaceBasicSettings';

const {
  getMock,
  putMock,
  toastMock,
  reloadMock,
  tMock,
  workspacePermissions,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
  toastMock: vi.fn(),
  reloadMock: vi.fn(),
  workspacePermissions: {
    accessRole: 'owner' as 'reader' | 'owner',
    canUpdateMetadata: true,
  },
  tMock: (key: string, options?: Record<string, unknown>) => {
    const translations = {
      'workspace.workspaceSettings.basic.metadata.provisioners.kubernetes': 'Kubernetes',
      'workspace.workspaceSettings.basic.metadata.provisioners.docker': 'Docker',
      'workspace.workspaceSettings.basic.metadata.phases.running': 'Running',
      'workspace.workspaceSettings.basic.metadata.phases.disabled': 'Disabled',
      'workspace.workspaceSettings.basic.metadata.notAvailable': 'Not Available',
      'workspace.workspaceSettings.basic.metadata.fields.access': 'Access',
      'workspace.workspaceSettings.basic.components.runtime': 'Runtime',
      'workspace.workspaceSettings.basic.components.browser': 'Browser',
      'workspace.workspaceSettings.basic.components.canvas': 'Canvas',
      'workspace.workspaceSettings.basic.fields.agenticTool.options.claudeCode': 'Claude Code',
      'workspace.workspaceSettings.basic.fields.agenticTool.options.codex': 'Codex',
      'workspace.workspaceSettings.basic.fields.agenticTool.options.opencode': 'OpenCode',
      'workspace.workspaceSettings.access.badges.owned': 'Owned',
      'workspace.workspaceSettings.access.badges.shared': `Shared · ${String(options?.role ?? '')}`,
      'workspace.workspaceSettings.access.roles.reader': 'reader',
    } as Record<string, string>;
    return translations[key] ?? key;
  },
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: getMock,
    put: putMock,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-123',
      reload: reloadMock,
    },
    permissions: workspacePermissions,
  }),
}));

const runtimeStatus = {
  status: 'running',
  runtimeUrl: '/workspaces/ws-123/runtime',
  browserUrl: '/workspaces/ws-123/browser',
  canvasUrl: '/workspaces/ws-123/canvas',
};

describe('WorkspaceBasicSettings', () => {
  beforeEach(() => {
    getMock.mockReset();
    putMock.mockReset();
    toastMock.mockReset();
    reloadMock.mockReset();
    workspacePermissions.accessRole = 'owner';
    workspacePermissions.canUpdateMetadata = true;
  });

  it('renders provisioner, namespace and component status metadata', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'K8s Workspace',
      description: 'desc',
      gitUrl: 'https://github.com/example/repo.git',
      branch: 'main',
      agenticTools: ['claude-code'],
      provisioner: 'kubernetes',
      targetNamespace: 'team-a',
      overallPhase: 'Running',
      runtimeStatus: {
        status: 'running',
        runtimeUrl: '/workspaces/ws-123/runtime',
        browserUrl: '/workspaces/ws-123/browser',
        canvasUrl: '/workspaces/ws-123/canvas',
      },
      components: {
        runtime: {
          phase: 'Running',
          lastRestartRequestedAt: '2026-04-08T10:00:00Z',
        },
        browser: {
          phase: 'Running',
        },
        canvas: {
          phase: 'Disabled',
        },
      },
    });

    render(<WorkspaceBasicSettings />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(await screen.findByText('Kubernetes')).toBeInTheDocument();
    expect(screen.getByText('team-a')).toBeInTheDocument();
    expect(screen.getByText('/workspaces/ws-123/runtime')).toBeInTheDocument();
    expect(screen.getByText('/workspaces/ws-123/browser')).toBeInTheDocument();
    expect(screen.getByText('/workspaces/ws-123/canvas')).toBeInTheDocument();
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0);
    expect(screen.getByText('Disabled')).toBeInTheDocument();
    expect(
      screen.queryByLabelText('workspace.workspaceSettings.basic.fields.repository.label')
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText('workspace.workspaceSettings.basic.fields.branch.label')
    ).not.toBeInTheDocument();
  });

  it('shows read-only shared access state for reader role', async () => {
    workspacePermissions.accessRole = 'reader';
    workspacePermissions.canUpdateMetadata = false;
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'Shared Workspace',
      accessRole: 'reader',
      accessSource: 'direct_share',
      owner: {
        id: 'owner-1',
        displayName: 'Workspace Owner',
        email: 'owner@example.com',
      },
      agenticTools: ['claude-code'],
      provisioner: 'docker',
      overallPhase: 'Running',
      runtimeStatus,
      components: {},
    });

    render(<WorkspaceBasicSettings />);

    expect(await screen.findByDisplayValue('Shared Workspace')).toBeDisabled();
    expect(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.basic.actions.save.label',
    })).toBeDisabled();
  });

  it('shows read-only project data and Runtime HOME capacity for a reader', async () => {
    workspacePermissions.accessRole = 'reader';
    workspacePermissions.canUpdateMetadata = false;
    getMock.mockImplementation(async (path: string) => {
      if (path === '/workspaces/ws-123/capacity?range=7d') {
        return {
          provisioner: 'kubernetes',
          timeZone: 'Asia/Taipei',
          items: [
            {
              storageKind: 'workspace_data',
              usedBytes: 5 * 1024 ** 3,
              allocatedBytes: 20 * 1024 ** 3,
              hostAvailableBytes: null,
              utilizationPercent: 25,
              risk: 'normal',
              measuredAt: '2026-08-01T01:00:00Z',
              history: [{ date: '2026-08-01', usedBytes: 5 * 1024 ** 3 }],
            },
            {
              storageKind: 'runtime_home',
              usedBytes: 1024 ** 3,
              allocatedBytes: 2 * 1024 ** 3,
              hostAvailableBytes: null,
              utilizationPercent: 50,
              risk: 'normal',
              measuredAt: '2026-08-01T01:00:00Z',
              history: [{ date: '2026-08-01', usedBytes: 1024 ** 3 }],
            },
          ],
        };
      }
      return {
        id: 'ws-123',
        name: 'Shared Workspace',
        accessRole: 'reader',
        accessSource: 'direct_share',
        owner: { id: 'owner-1', displayName: 'Workspace Owner' },
        agenticTools: ['claude-code'],
        provisioner: 'kubernetes',
        overallPhase: 'Running',
        runtimeStatus,
        components: {},
      };
    });

    render(<WorkspaceBasicSettings />);

    expect(await screen.findByText('workspace.workspaceSettings.basic.capacity.title'))
      .toBeInTheDocument();
    expect(screen.getByText('5.0 GiB')).toBeInTheDocument();
    expect(screen.getByText('1.0 GiB')).toBeInTheDocument();
    expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123/capacity?range=7d');
  });

  it('keeps basic settings usable when capacity is unavailable', async () => {
    getMock.mockImplementation(async (path: string) => {
      if (path.includes('/capacity')) throw new Error('capacity unavailable');
      return {
        id: 'ws-123',
        name: 'Workspace With Partial Data',
        agenticTools: ['claude-code'],
        provisioner: 'docker',
        overallPhase: 'Running',
        runtimeStatus,
        components: {},
      };
    });

    render(<WorkspaceBasicSettings />);

    expect(await screen.findByDisplayValue('Workspace With Partial Data')).toBeInTheDocument();
    expect(screen.getByText('workspace.workspaceSettings.basic.capacity.loadFailed'))
      .toBeInTheDocument();
  });

  it('saves selected agentic tools after adding and removing tools', async () => {
    const user = userEvent.setup();
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'Tools Workspace',
      description: 'desc',
      gitUrl: '',
      branch: 'main',
      agenticTools: ['claude-code', 'codex'],
      accessRole: 'owner',
      accessSource: 'owned',
      provisioner: 'docker',
      overallPhase: 'Running',
      runtimeStatus,
      components: {},
    });
    putMock.mockResolvedValue({
      id: 'ws-123',
      name: 'Renamed Workspace',
      description: 'desc',
      gitUrl: '',
      branch: 'main',
      agenticTools: ['claude-code', 'codex'],
      accessRole: 'owner',
      accessSource: 'owned',
      provisioner: 'docker',
      overallPhase: 'Running',
      runtimeStatus,
      components: {},
    });

    render(<WorkspaceBasicSettings />);

    expect(await screen.findByRole('button', { name: 'Claude Code' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Codex' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'OpenCode' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'OpenCode' }));
    await user.click(screen.getByRole('button', { name: 'Codex' }));
    await user.click(screen.getByRole('button', { name: 'workspace.workspaceSettings.basic.actions.save.label' }));

    await waitFor(() => {
      expect(putMock).toHaveBeenCalledWith('/workspaces/ws-123', {
        name: 'Tools Workspace',
        description: 'desc',
        agenticTools: ['claude-code', 'opencode'],
      });
    });
    expect(reloadMock).toHaveBeenCalledOnce();
  });

  it('does not allow removing the final selected agentic tool', async () => {
    const user = userEvent.setup();
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'Tools Workspace',
      description: 'desc',
      gitUrl: '',
      branch: 'main',
      agenticTools: ['claude-code'],
      accessRole: 'owner',
      accessSource: 'owned',
      provisioner: 'docker',
      overallPhase: 'Running',
      runtimeStatus,
      components: {},
    });

    render(<WorkspaceBasicSettings />);

    const claudeButton = await screen.findByRole('button', { name: 'Claude Code' });
    await user.click(claudeButton);

    expect(screen.getByRole('button', { name: 'workspace.workspaceSettings.basic.actions.save.label' })).toBeDisabled();
  });

});
