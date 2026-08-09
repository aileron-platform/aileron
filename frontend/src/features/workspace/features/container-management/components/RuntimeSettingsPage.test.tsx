import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import RuntimeSettingsPage from './RuntimeSettingsPage';

const { getMock, putMock, toastMock, restartComponentMock, tMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
  toastMock: vi.fn(),
  restartComponentMock: vi.fn(),
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

vi.mock('@/features/workspace/api/workspaceLifecycleApi', () => ({
  workspaceLifecycleApi: {
    restartComponent: restartComponentMock,
    rotateBrowserCredentials: vi.fn(),
  },
}));

describe('RuntimeSettingsPage', () => {
  beforeEach(() => {
    getMock.mockReset();
    putMock.mockReset();
    toastMock.mockReset();
    restartComponentMock.mockReset();
  });

  it('renders runtime settings without port mapping controls', async () => {
    getMock.mockImplementation((url: string) => Promise.resolve(
      url.endsWith('/sensitive-settings')
        ? { setupScript: '', envVars: [], acpCliArgs: [] }
        : {
            id: 'ws-123',
            runtime: 'universal',
            provisioner: 'docker',
          },
    ));

    render(<RuntimeSettingsPage />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
      expect(getMock).toHaveBeenCalledWith(
        '/workspaces/ws-123/sensitive-settings',
      );
    });

    expect(screen.queryByText('workspace.containerManagement.runtime.portMappings.system.label')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.containerManagement.runtime.portMappings.label')).not.toBeInTheDocument();
  });

  it('does not expose or submit per-workspace Kubernetes resource overrides', async () => {
    const detail = {
      id: 'ws-123',
      runtime: 'universal',
      provisioner: 'kubernetes',
    };
    getMock.mockImplementation((url: string) => Promise.resolve(
      url.endsWith('/sensitive-settings')
        ? { setupScript: '', envVars: [], acpCliArgs: [] }
        : detail,
    ));
    putMock.mockResolvedValue({
      setupScript: 'echo ready',
      envVars: [],
      acpCliArgs: [],
    });

    render(<RuntimeSettingsPage />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(
      screen.queryByText('workspace.containerManagement.runtime.resources.title'),
    ).not.toBeInTheDocument();

    fireEvent.change(
      await screen.findByLabelText(
        'workspace.containerManagement.runtime.form.setupScript.label',
      ),
      { target: { value: 'echo ready' } },
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: 'workspace.containerManagement.runtime.header.actions.save',
      }),
    );

    await waitFor(() => {
      expect(putMock).toHaveBeenCalledWith(
        '/workspaces/ws-123/sensitive-settings',
        {
          setupScript: 'echo ready',
        },
      );
    });
    expect(putMock).not.toHaveBeenCalledWith(
      '/workspaces/ws-123',
      expect.anything(),
    );
    expect(restartComponentMock).not.toHaveBeenCalled();
  });

  it('keeps configured secrets masked and requires replacements for a full env update', async () => {
    getMock.mockImplementation((url: string) => Promise.resolve(
      url.endsWith('/sensitive-settings')
        ? {
            setupScript: '',
            envVars: [{ key: 'API_TOKEN', isConfigured: true }],
            acpCliArgs: [],
          }
        : {
            id: 'ws-123',
            runtime: 'universal',
            provisioner: 'docker',
          },
    ));

    render(<RuntimeSettingsPage />);

    const secretInput = await screen.findByPlaceholderText(
      'workspace.containerManagement.runtime.envVars.configuredValuePlaceholder',
    );
    expect(secretInput).toHaveValue('');
    expect(screen.queryByDisplayValue('API_TOKEN_SECRET')).not.toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText(
        'workspace.containerManagement.runtime.envVars.keyPlaceholder',
      ),
      { target: { value: 'RENAMED_API_TOKEN' } },
    );

    expect(await screen.findByText(
      'workspace.containerManagement.runtime.envVars.replaceConfiguredValues',
    )).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'workspace.containerManagement.runtime.header.actions.save',
    })).toBeDisabled();
    expect(putMock).not.toHaveBeenCalled();
  });
});
