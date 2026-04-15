import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { FirewallSettingsView } from './FirewallSettingsView';

const { getMock, putMock, toastMock, tMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
  toastMock: vi.fn(),
  tMock: (key: string, params?: Record<string, unknown>) => {
    const translations: Record<string, string> = {
      'workspace.containerManagement.firewall.header.title': 'Firewall',
      'workspace.containerManagement.firewall.header.actions.save': 'Save',
      'workspace.containerManagement.firewall.header.actions.saving': 'Saving',
      'workspace.containerManagement.firewall.groups.workspace.title': 'Workspace Firewall',
      'workspace.containerManagement.firewall.groups.browser.title': 'Browser Firewall',
      'workspace.containerManagement.firewall.allowedDomains.placeholder': 'Add domain',
      'workspace.containerManagement.firewall.allowedDomains.add': 'Add',
      'workspace.containerManagement.firewall.notifications.saveSuccess': 'Saved',
      'workspace.containerManagement.firewall.unavailable.title': 'Unavailable',
      'workspace.containerManagement.firewall.unavailable.description': 'Cilium is not enabled',
      'workspace.containerManagement.firewall.unavailable.reasons.CILIUM_NOT_ENABLED': 'Cilium is not enabled',
    };
    return translations[key] ?? (params as { defaultValue?: string })?.defaultValue ?? key;
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
    },
  }),
}));

describe('FirewallSettingsView', () => {
  beforeEach(() => {
    getMock.mockReset();
    putMock.mockReset();
    toastMock.mockReset();
  });

  it('loads dual firewall groups and saves the nested payload', async () => {
    getMock.mockResolvedValue({
      firewallAvailable: true,
      firewall: {
        workspace: {
          networkAccessEnabled: true,
          domainAccessMode: 'specific',
          allowedDomains: ['github.com'],
          effectiveAllowedDomains: ['github.com', 'registry.npmjs.org'],
        },
        browser: {
          networkAccessEnabled: true,
          domainAccessMode: 'specific',
          allowedDomains: ['google.com'],
          effectiveAllowedDomains: ['google.com', 'gstatic.com'],
        },
      },
    });
    putMock.mockResolvedValue({
      firewallAvailable: true,
      firewall: {
        workspace: {
          networkAccessEnabled: true,
          domainAccessMode: 'specific',
          allowedDomains: ['github.com', 'internal.example.com'],
          effectiveAllowedDomains: ['github.com', 'registry.npmjs.org', 'internal.example.com'],
        },
        browser: {
          networkAccessEnabled: true,
          domainAccessMode: 'specific',
          allowedDomains: ['google.com'],
          effectiveAllowedDomains: ['google.com', 'gstatic.com'],
        },
      },
    });

    render(<FirewallSettingsView />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(await screen.findByText('Workspace Firewall')).toBeInTheDocument();
    expect(screen.getByText('Browser Firewall')).toBeInTheDocument();
    expect(screen.getByText('registry.npmjs.org')).toBeInTheDocument();
    expect(screen.getByText('gstatic.com')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeDisabled();

    const domainInputs = screen.getAllByPlaceholderText('Add domain');
    fireEvent.change(domainInputs[0], { target: { value: 'internal.example.com' } });

    const addButtons = screen.getAllByText('Add');
    fireEvent.click(addButtons[0]);
    expect(screen.getByText('Save')).toBeEnabled();
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(putMock).toHaveBeenCalledWith('/workspaces/ws-123', {
        firewall: {
          workspace: {
            networkAccessEnabled: true,
            domainAccessMode: 'specific',
            allowedDomains: ['github.com', 'internal.example.com'],
          },
          browser: {
            networkAccessEnabled: true,
            domainAccessMode: 'specific',
            allowedDomains: ['google.com'],
          },
        },
      });
    });
  });

  it('disables save actions only when the backend reports firewall unavailable', async () => {
    getMock.mockResolvedValue({
      firewallAvailable: false,
      firewallUnavailableReason: 'CILIUM_NOT_ENABLED',
      firewall: {
        workspace: {
          networkAccessEnabled: true,
          domainAccessMode: 'specific',
          allowedDomains: ['github.com'],
          effectiveAllowedDomains: [],
        },
        browser: {
          networkAccessEnabled: true,
          domainAccessMode: 'specific',
          allowedDomains: ['google.com'],
          effectiveAllowedDomains: [],
        },
      },
    });

    render(<FirewallSettingsView />);

    expect(await screen.findByText('Unavailable')).toBeInTheDocument();
    expect(screen.getByText('Cilium is not enabled')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeDisabled();

    fireEvent.click(screen.getByText('Save'));
    expect(putMock).not.toHaveBeenCalled();
  });
});
