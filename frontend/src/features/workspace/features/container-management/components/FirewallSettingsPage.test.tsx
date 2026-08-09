import { act } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { ApiError } from '@/shared/api/apiClient';
import {
  FIREWALL_POLL_INTERVAL_MS,
  FirewallSettingsPage,
  normalizeExactHostname,
} from './FirewallSettingsPage';

const {
  getMock,
  postMock,
  putMock,
  toastMock,
  tMock,
  workspacePermissions,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  toastMock: vi.fn(),
  workspacePermissions: {
    canManageFirewall: true,
  },
  tMock: (key: string, params?: Record<string, unknown>) => {
    if (key === 'workspace.containerManagement.firewall.allowedDomains.remove') {
      return `Remove ${String(params?.domain)}`;
    }
    if (key === 'workspace.containerManagement.firewall.sync.applied') {
      return `Applied revision ${String(params?.revision)}`;
    }
    const translations: Record<string, string> = {
      'workspace.containerManagement.firewall.header.title': 'Firewall',
      'workspace.containerManagement.firewall.header.actions.save': 'Save',
      'workspace.containerManagement.firewall.header.actions.saving': 'Saving',
      'workspace.containerManagement.firewall.groups.workspace.title': 'Workspace Firewall',
      'workspace.containerManagement.firewall.groups.browser.title': 'Browser Firewall',
      'workspace.containerManagement.firewall.egressMode.label': 'External network access',
      'workspace.containerManagement.firewall.egressMode.options.blocked.label': 'Block external network',
      'workspace.containerManagement.firewall.egressMode.options.allowlist.label': 'Allow specified domains',
      'workspace.containerManagement.firewall.egressMode.options.unrestricted.label': 'Allow all external network',
      'workspace.containerManagement.firewall.allowedDomains.placeholder': 'Add domain',
      'workspace.containerManagement.firewall.allowedDomains.add': 'Add',
      'workspace.containerManagement.firewall.allowedDomains.invalid': 'Invalid exact hostname',
      'workspace.containerManagement.firewall.allowedDomains.required': 'At least one domain is required',
      'workspace.containerManagement.firewall.notifications.applied': 'Firewall applied',
      'workspace.containerManagement.firewall.sync.applying.title': 'Applying firewall',
      'workspace.containerManagement.firewall.sync.failed.title': 'Firewall failed',
      'workspace.containerManagement.firewall.sync.failed.description': 'Enforcement failed',
      'workspace.containerManagement.firewall.sync.failed.retry': 'Retry enforcement',
      'workspace.containerManagement.firewall.sync.failed.retrying': 'Retrying',
      'workspace.containerManagement.firewall.errors.FIREWALL_DELIVERY_FAILED': 'Delivery failed',
      'workspace.containerManagement.firewall.errors.FIREWALL_RETRY_NOT_ALLOWED': 'This revision cannot be retried',
      'workspace.containerManagement.firewall.unavailable.title': 'Unavailable',
      'workspace.containerManagement.firewall.unavailable.description': 'Cilium is not enabled',
      'workspace.containerManagement.firewall.unavailable.reasons.CILIUM_NOT_ENABLED': 'Cilium is not enabled',
    };
    return translations[key] ?? (params as { defaultValue?: string })?.defaultValue ?? key;
  },
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiError: class ApiError extends Error {
    status: number;
    errorCode?: string;

    constructor(message: string, status = 500, errorCode?: string) {
      super(message);
      this.status = status;
      this.errorCode = errorCode;
    }
  },
  apiClient: {
    get: getMock,
    post: postMock,
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
    permissions: workspacePermissions,
  }),
}));

const firewallResource = (overrides: Record<string, unknown> = {}) => ({
  revision: 3,
  observedRevision: 3,
  syncStatus: 'applied',
  errorCode: null,
  workspace: {
    egressMode: 'allowlist',
    allowedDomains: ['github.com', 'registry.npmjs.org'],
  },
  browser: {
    egressMode: 'allowlist',
    allowedDomains: ['google.com'],
  },
  ...overrides,
});

describe('FirewallSettingsPage', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    toastMock.mockReset();
    workspacePermissions.canManageFirewall = true;
  });

  it('saves Runtime and Browser rules independently and reports applying without false success', async () => {
    getMock.mockResolvedValue(firewallResource());
    putMock.mockResolvedValue(firewallResource({
      revision: 4,
      observedRevision: 3,
      syncStatus: 'pending',
      workspace: {
        egressMode: 'allowlist',
        allowedDomains: ['github.com', 'internal.example.com'],
      },
    }));

    render(<FirewallSettingsPage />);

    expect(await screen.findByText('Workspace Firewall')).toBeInTheDocument();
    expect(screen.getByText('Browser Firewall')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Remove registry.npmjs.org' }));
    const domainInputs = screen.getAllByPlaceholderText('Add domain');
    fireEvent.change(domainInputs[0], { target: { value: 'internal.example.com' } });
    fireEvent.click(screen.getAllByText('Add')[0]);
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(putMock).toHaveBeenCalledWith('/workspaces/ws-123/firewall', {
        revision: 3,
        workspace: {
          egressMode: 'allowlist',
          allowedDomains: ['github.com', 'internal.example.com'],
        },
        browser: {
          egressMode: 'allowlist',
          allowedDomains: ['google.com'],
        },
      });
    });

    expect(await screen.findByText('Applying firewall')).toBeInTheDocument();
    expect(toastMock).not.toHaveBeenCalled();
    expect(screen.getByText('Save')).toBeDisabled();
  });

  it('renders one unambiguous egress mode control and hides domains outside allowlist mode', async () => {
    getMock.mockResolvedValue(firewallResource({
      workspace: {
        egressMode: 'blocked',
        allowedDomains: [],
      },
      browser: {
        egressMode: 'unrestricted',
        allowedDomains: [],
      },
    }));

    render(<FirewallSettingsPage />);

    expect(await screen.findByText('Block external network')).toBeInTheDocument();
    expect(screen.getByText('Allow all external network')).toBeInTheDocument();
    expect(screen.getAllByText('External network access')).toHaveLength(2);
    expect(screen.getAllByRole('combobox')).toHaveLength(2);
    expect(screen.queryByPlaceholderText('Add domain')).not.toBeInTheDocument();
  });

  it('does not submit allowlist mode without at least one allowed domain', async () => {
    getMock.mockResolvedValue(firewallResource({
      workspace: {
        egressMode: 'allowlist',
        allowedDomains: ['github.com'],
      },
      browser: {
        egressMode: 'unrestricted',
        allowedDomains: [],
      },
    }));

    render(<FirewallSettingsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Remove github.com' }));

    expect(screen.getByText('At least one domain is required')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeDisabled();
    fireEvent.click(screen.getByText('Save'));
    expect(putMock).not.toHaveBeenCalled();
  });

  it('announces success only after observed revision reaches the desired revision', async () => {
    vi.useFakeTimers();
    try {
      getMock
        .mockResolvedValueOnce(firewallResource())
        .mockResolvedValueOnce(firewallResource({
          revision: 4,
          observedRevision: 4,
        }));
      putMock.mockResolvedValue(firewallResource({
        revision: 4,
        observedRevision: 3,
        syncStatus: 'applying',
        workspace: {
          egressMode: 'allowlist',
          allowedDomains: ['github.com'],
        },
      }));

      render(<FirewallSettingsPage />);
      await act(async () => {
        await Promise.resolve();
      });
      fireEvent.click(screen.getByRole('button', { name: 'Remove registry.npmjs.org' }));
      fireEvent.click(screen.getByText('Save'));
      await act(async () => {
        await Promise.resolve();
      });

      expect(screen.getByText('Applying firewall')).toBeInTheDocument();
      expect(toastMock).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(FIREWALL_POLL_INTERVAL_MS);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByText('Applied revision 4')).toBeInTheDocument();
      expect(toastMock).toHaveBeenCalledWith({
        title: 'Firewall',
        description: 'Firewall applied',
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps polling when applied status has not reached the desired revision', async () => {
    vi.useFakeTimers();
    try {
      getMock
        .mockResolvedValueOnce(firewallResource({
          revision: 5,
          observedRevision: 4,
          syncStatus: 'applied',
        }))
        .mockResolvedValueOnce(firewallResource({
          revision: 5,
          observedRevision: 5,
          syncStatus: 'applied',
        }));

      render(<FirewallSettingsPage />);
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByText('Applying firewall')).toBeInTheDocument();
      expect(screen.queryByText('Applied revision 5')).not.toBeInTheDocument();

      await act(async () => {
        vi.advanceTimersByTime(FIREWALL_POLL_INTERVAL_MS);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(getMock).toHaveBeenCalledTimes(2);
      expect(screen.getByText('Applied revision 5')).toBeInTheDocument();
      expect(toastMock).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not announce a saved revision after a newer revision supersedes it', async () => {
    vi.useFakeTimers();
    try {
      getMock
        .mockResolvedValueOnce(firewallResource())
        .mockResolvedValueOnce(firewallResource({
          revision: 5,
          observedRevision: 5,
          syncStatus: 'applied',
        }));
      putMock.mockResolvedValue(firewallResource({
        revision: 4,
        observedRevision: 3,
        syncStatus: 'applying',
        workspace: {
          egressMode: 'allowlist',
          allowedDomains: ['github.com'],
        },
      }));

      render(<FirewallSettingsPage />);
      await act(async () => {
        await Promise.resolve();
      });
      fireEvent.click(screen.getByRole('button', { name: 'Remove registry.npmjs.org' }));
      fireEvent.click(screen.getByText('Save'));
      await act(async () => {
        await Promise.resolve();
      });

      await act(async () => {
        vi.advanceTimersByTime(FIREWALL_POLL_INTERVAL_MS);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByText('Applied revision 5')).toBeInTheDocument();
      expect(toastMock).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps failed desired settings and retries through the dedicated endpoint', async () => {
    getMock.mockResolvedValue(firewallResource({
      revision: 5,
      observedRevision: 4,
      syncStatus: 'error',
      errorCode: 'FIREWALL_DELIVERY_FAILED',
    }));
    postMock.mockResolvedValue(firewallResource({
      revision: 5,
      observedRevision: 4,
      syncStatus: 'applying',
      errorCode: null,
    }));

    render(<FirewallSettingsPage />);

    expect(await screen.findByText('Firewall failed')).toBeInTheDocument();
    expect(screen.getByText('Delivery failed')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Retry enforcement'));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/workspaces/ws-123/firewall/retry');
    });
    expect(await screen.findByText('Applying firewall')).toBeInTheDocument();
    expect(screen.getByDisplayValue('registry.npmjs.org')).toBeInTheDocument();
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('maps a rejected retry to localized text without exposing the raw code', async () => {
    getMock.mockResolvedValue(firewallResource({
      revision: 5,
      observedRevision: 4,
      syncStatus: 'error',
      errorCode: 'FIREWALL_DELIVERY_FAILED',
    }));
    postMock.mockRejectedValue(new ApiError(
      'FIREWALL_RETRY_NOT_ALLOWED',
      409,
      'FIREWALL_RETRY_NOT_ALLOWED',
    ));

    render(<FirewallSettingsPage />);
    fireEvent.click(await screen.findByText('Retry enforcement'));

    expect(await screen.findByText('This revision cannot be retried')).toBeInTheDocument();
    expect(screen.queryByText('FIREWALL_RETRY_NOT_ALLOWED')).not.toBeInTheDocument();
  });

  it('rejects wildcard input before it can enter the desired payload', async () => {
    getMock.mockResolvedValue(firewallResource());
    render(<FirewallSettingsPage />);

    const domainInputs = await screen.findAllByPlaceholderText('Add domain');
    fireEvent.change(domainInputs[0], { target: { value: '*.example.com' } });
    fireEvent.click(screen.getAllByText('Add')[0]);

    expect(screen.getByText('Invalid exact hostname')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('*.example.com')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeDisabled();
  });

  it('disables save actions when the backend reports firewall unavailable', async () => {
    getMock.mockResolvedValue(firewallResource({
      revision: 1,
      observedRevision: 0,
      syncStatus: 'unavailable',
      errorCode: 'CILIUM_NOT_ENABLED',
    }));

    render(<FirewallSettingsPage />);

    expect(await screen.findByText('Unavailable')).toBeInTheDocument();
    expect(screen.getByText('Cilium is not enabled')).toBeInTheDocument();
    expect(screen.getByText('Save')).toBeDisabled();

    fireEvent.click(screen.getByText('Save'));
    expect(putMock).not.toHaveBeenCalled();
  });
});

describe('normalizeExactHostname', () => {
  it.each([
    [' GitHub.COM. ', 'github.com'],
    ['docs.example.com', 'docs.example.com'],
    ['bücher.example', 'xn--bcher-kva.example'],
  ])('normalizes %s to a canonical exact hostname', (input, expected) => {
    expect(normalizeExactHostname(input)).toBe(expected);
  });

  it.each([
    '*.example.com',
    'https://example.com',
    'example.com/path',
    'example.com:443',
    '127.0.0.1',
    'bad_label.example.com',
  ])('rejects non-hostname input %s', (input) => {
    expect(normalizeExactHostname(input)).toBeNull();
  });
});
