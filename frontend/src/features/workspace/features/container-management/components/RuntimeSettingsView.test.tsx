import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import RuntimeSettingsView from './RuntimeSettingsView';

const { getMock, putMock, toastMock, rebuildMock, tMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
  toastMock: vi.fn(),
  rebuildMock: vi.fn(),
  tMock: vi.fn((key: string) => key),
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
    },
  }),
}));

vi.mock('@/shared/hooks/useContainerImages', () => ({
  useContainerImages: () => ({
    data: {
      images: [{ id: 'universal', name: 'Universal', description: 'desc', icon: 'U' }],
    },
    isLoading: false,
  }),
}));

vi.mock('@/features/workspace/services/workspaceLifecycleApi', () => ({
  workspaceLifecycleApi: {
    rebuildWorkspace: rebuildMock,
  },
}));

describe('RuntimeSettingsView', () => {
  beforeEach(() => {
    getMock.mockReset();
    putMock.mockReset();
    toastMock.mockReset();
    rebuildMock.mockReset();
  });

  it('renders docker system ports separately from custom port mappings', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      runtime: 'universal',
      provisioner: 'docker',
      setupScript: '',
      envVars: [],
      portMappings: [{ containerPort: 9000, hostPort: 39000, protocol: 'tcp', description: 'Custom' }],
      systemPortMappings: [
        { name: 'runtime', containerPort: 3002, hostPort: 31002, protocol: 'tcp', description: 'Workspace runtime API', editable: false },
      ],
    });

    render(<RuntimeSettingsView />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(await screen.findByText('System Ports')).toBeInTheDocument();
    expect(screen.getByDisplayValue('runtime')).toBeDisabled();
    expect(screen.getByDisplayValue('Workspace runtime API')).toBeDisabled();
    expect(screen.getByDisplayValue('Custom')).toBeInTheDocument();
  });

  it('shows unsupported copy for kubernetes workspaces instead of port mapping editor', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      runtime: 'universal',
      provisioner: 'kubernetes',
      setupScript: '',
      envVars: [],
      runtimeResources: {
        requests: { cpu: '500m', memory: '2Gi' },
        limits: { cpu: '2000m', memory: '4Gi' },
      },
      portMappings: [],
      systemPortMappings: [],
    });

    render(<RuntimeSettingsView />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(
      await screen.findByText('Workspace-level port exposure is not supported for Kubernetes workspaces.')
    ).toBeInTheDocument();
    expect(screen.queryByText('System Ports')).not.toBeInTheDocument();
  });
});
