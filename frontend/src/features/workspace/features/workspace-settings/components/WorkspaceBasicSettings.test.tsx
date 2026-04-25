import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@/__tests__/utils/render';
import { render } from '@/__tests__/utils/render';
import { WorkspaceBasicSettings } from './WorkspaceBasicSettings';

const { getMock, putMock, toastMock, reloadMock, tMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
  toastMock: vi.fn(),
  reloadMock: vi.fn(),
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
      'workspace.workspaceSettings.access.badges.owned': 'Owned',
      'workspace.workspaceSettings.access.badges.shared': `Shared · ${String(options?.role ?? '')}`,
      'workspace.workspaceSettings.access.roles.viewer': 'viewer',
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
  }),
}));

describe('WorkspaceBasicSettings', () => {
  beforeEach(() => {
    getMock.mockReset();
    putMock.mockReset();
    toastMock.mockReset();
    reloadMock.mockReset();
  });

  it('renders provisioner, namespace and component status metadata', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'K8s Workspace',
      description: 'desc',
      gitUrl: 'https://github.com/example/repo.git',
      branch: 'main',
      cliType: 'claude-code',
      provisioner: 'kubernetes',
      targetNamespace: 'team-a',
      overallPhase: 'Running',
      components: {
        runtime: {
          phase: 'Running',
          internalUrl: 'http://runtime.team-a.svc.cluster.local:3002',
          externalUrl: 'http://runtime.example.com',
          lastRestartRequestedAt: '2026-04-08T10:00:00Z',
        },
        browser: {
          phase: 'Running',
          internalUrl: 'http://browser.team-a.svc.cluster.local:6080',
        },
        canvas: {
          phase: 'Disabled',
          internalUrl: 'http://canvas.team-a.svc.cluster.local:3003',
        },
      },
    });

    render(<WorkspaceBasicSettings />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(await screen.findByText('Kubernetes')).toBeInTheDocument();
    expect(screen.getByText('team-a')).toBeInTheDocument();
    expect(screen.getByText('http://runtime.example.com')).toBeInTheDocument();
    expect(screen.getByText('http://browser.team-a.svc.cluster.local:6080')).toBeInTheDocument();
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0);
    expect(screen.getByText('Disabled')).toBeInTheDocument();
  });

  it('shows read-only shared access state for viewer role', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'Shared Workspace',
      accessRole: 'viewer',
      accessSource: 'shared',
      owner: {
        id: 'owner-1',
        displayName: 'Workspace Owner',
        email: 'owner@example.com',
      },
      cliType: 'claude-code',
      provisioner: 'docker',
      overallPhase: 'Running',
      components: {},
    });

    render(<WorkspaceBasicSettings />);

    expect(await screen.findByText('Shared · viewer')).toBeInTheDocument();
    expect(screen.queryByText('Add share')).not.toBeInTheDocument();
  });

});
