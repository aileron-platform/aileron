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

  it('renders runtime settings without port mapping controls', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      runtime: 'universal',
      provisioner: 'docker',
      setupScript: '',
      envVars: [],
    });

    render(<RuntimeSettingsView />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(screen.queryByText('workspace.containerManagement.runtime.portMappings.system.label')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.containerManagement.runtime.portMappings.label')).not.toBeInTheDocument();
  });

  it('shows kubernetes runtime resources without port mapping editor', async () => {
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
    });

    render(<RuntimeSettingsView />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(screen.queryByText('workspace.containerManagement.runtime.portMappings.system.label')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.containerManagement.runtime.portMappings.kubernetesUnsupported')).not.toBeInTheDocument();
  });
});
