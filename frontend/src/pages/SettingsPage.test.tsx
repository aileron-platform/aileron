import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import SettingsPage from './SettingsPage';
import { apiClient } from '@/shared/api/apiClient';

vi.mock('@/app/components/navigation/GlobalNavigation', () => ({
  default: () => <div data-testid="global-navigation" />,
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string>) => {
      if (values?.code) {
        return `${key}:${values.code}`;
      }
      return key;
    },
    changeLanguage: vi.fn(),
  }),
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: {
        id: 'user-123',
        preferences: {
          theme: 'system',
          language: 'en',
        },
      },
    },
    dispatch: vi.fn(),
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

const settingsResponse = {
  data: {
    general: {
      theme: 'system',
      language: 'en',
      timezone: 'Asia/Taipei',
      notifications: { desktop: true, email: false, updates: true },
      performance: { autoSave: true, animationsEnabled: true },
      privacy: { analytics: false, crashReports: true, usageData: false },
    },
    ssh: {
      publicKey: '',
      privateKey: '',
      fingerprint: null,
      lastRotatedAt: null,
    },
    claudeCode: {
      authMethod: 'subscription',
      model: 'claude-sonnet-4-20250514',
      selectedProvider: 'anthropic',
      environmentVariables: [],
      availableModels: [],
      availableProviders: [],
    },
    codex: {
      authMethod: 'subscription',
      loginStatus: 'pending',
      account: null,
      model: 'gpt-5.3-codex',
      environmentVariables: [],
      authFlow: {
        loginId: 'login-123',
        verificationUrl: 'https://auth.openai.com/device',
        userCode: 'ABCD-EFGH',
      },
    },
    git: {
      userName: '',
      userEmail: '',
      signingKey: '',
    },
  },
};

const notConnectedSettingsResponse = {
  data: {
    ...settingsResponse.data,
    codex: {
      authMethod: 'subscription',
      loginStatus: 'notConnected',
      account: null,
      model: 'gpt-5.3-codex',
      environmentVariables: [],
      authFlow: null,
    },
  },
};

describe('SettingsPage Codex tab', () => {
  const openedWindow = {
    opener: {},
    location: { href: '' },
    close: vi.fn(),
  } as unknown as Window;

  beforeEach(() => {
    vi.clearAllMocks();
    openedWindow.location.href = '';
    Object.defineProperty(window, 'open', {
      value: vi.fn(() => openedWindow),
      writable: true,
    });
    vi.mocked(apiClient.get).mockResolvedValue(settingsResponse);
    vi.mocked(apiClient.post).mockResolvedValue({
      success: true,
      codex: {
        ...settingsResponse.data.codex,
        loginStatus: 'connected',
        account: {
          email: 'codex@example.com',
          planType: 'pro',
        },
        authFlow: null,
      },
    });
  });

  it('renders Codex login status and i18n-keyed actions', async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'pages.settings.tabs.codex' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'pages.settings.tabs.codex' }));

    expect(screen.getByText('pages.settings.sections.codex.login.status.pending')).toBeInTheDocument();
    expect(
      screen.getByText('pages.settings.sections.codex.login.deviceCode:ABCD-EFGH')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'pages.settings.sections.codex.login.refreshButton' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'pages.settings.sections.codex.login.cancelButton' })
    ).toBeInTheDocument();
  });

  it('renders tabs in the expected order', async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'pages.settings.tabs.general' })).toBeInTheDocument();
    });

    const tabNames = screen.getAllByRole('tab').map((tab) => tab.textContent);

    expect(tabNames).toEqual([
      'pages.settings.tabs.general',
      'pages.settings.tabs.claudeCode',
      'pages.settings.tabs.codex',
      'pages.settings.tabs.gemini',
      'pages.settings.tabs.opencode',
      'pages.settings.tabs.ssh',
      'pages.settings.tabs.git',
    ]);
  });

  it('refreshes Codex login status through the manager API', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce(settingsResponse)
      .mockResolvedValueOnce({
        success: true,
        codex: {
          loginStatus: 'pending',
          account: null,
          model: 'gpt-5.3-codex',
          environmentVariables: [],
          authFlow: {
            loginId: 'login-123',
            verificationUrl: 'https://auth.openai.com/device',
            userCode: 'ABCD-EFGH',
          },
        },
      });
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'pages.settings.tabs.codex' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'pages.settings.tabs.codex' }));
    await user.click(
      await screen.findByRole('button', { name: 'pages.settings.sections.codex.login.refreshButton' })
    );

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/users/user-123/settings/codex/login/status');
    });
    expect(screen.getByText('pages.settings.sections.codex.login.title')).toBeInTheDocument();
  });

  it('opens the Codex verification page after starting sign in', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockResolvedValueOnce(notConnectedSettingsResponse);
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      success: true,
      codex: settingsResponse.data.codex,
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'pages.settings.tabs.codex' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'pages.settings.tabs.codex' }));
    await user.click(
      await screen.findByRole('button', { name: 'pages.settings.sections.codex.login.connectButton' })
    );

    await waitFor(() => {
      expect(window.open).toHaveBeenCalledWith('about:blank', '_blank');
      expect(openedWindow.location.href).toBe('https://auth.openai.com/device');
    });
  });
});
