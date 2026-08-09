import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsCodexTab } from './SettingsCodexTab';
import type { UserSettingsCodex } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string>) => {
      if (values?.code) {
        return `${key}:${values.code}`;
      }
      return key;
    },
  }),
}));

vi.mock('@/shared/components/settings-workflow', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/components/settings-workflow')>()),
  EnvironmentVariables: ({ title, description }: { title: string; description: string }) => (
    <div data-testid="environment-variables">
      <span>{title}</span>
      <span>{description}</span>
    </div>
  ),
}));

const pendingCodexSettings: UserSettingsCodex = {
  authMethod: 'subscription',
  loginStatus: 'pending',
  account: null,
  model: 'gpt-5.6-sol',
  modelSelection: {
    availableModels: ['gpt-5.6-sol'],
    customModels: [],
    allowedModels: ['gpt-5.6-sol'],
    defaultModel: 'gpt-5.6-sol',
  },
  environmentVariables: [],
  authFlow: {
    loginId: 'login-123',
    verificationUrl: 'https://auth.openai.com/device',
    userCode: 'ABCD-EFGH',
  },
};

const expectOnlyOuterCard = (container: HTMLElement) => {
  expect(container.querySelectorAll('.bg-card')).toHaveLength(1);
  expect(
    Array.from(container.querySelectorAll('[class]')).some((element) =>
      element.getAttribute('class')?.includes('bg-muted/30'),
    ),
  ).toBe(false);
};

describe('SettingsCodexTab', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
  });

  it('renders pending subscription login state with i18n-keyed actions', () => {
    const { container } = render(
      <SettingsCodexTab
        codexSettings={pendingCodexSettings}
        isCodexAuthLoading={false}
        onCodexSettingsChange={vi.fn()}
        onSignIn={vi.fn()}
        onRefreshStatus={vi.fn()}
        onLogout={vi.fn()}
        onCancelLogin={vi.fn()}
      />,
    );

    expect(screen.getByText('pages.settings.tabs.codex')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.codex.login.status.pending')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.codex.login.deviceCode:ABCD-EFGH')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'pages.settings.sections.codex.login.refreshButton' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'pages.settings.sections.codex.login.cancelButton' }),
    ).toBeInTheDocument();
    expectOnlyOuterCard(container);
  });

  it('renders the not-connected subscription description once', () => {
    render(
      <SettingsCodexTab
        codexSettings={{
          ...pendingCodexSettings,
          loginStatus: 'notConnected',
          authFlow: null,
        }}
        isCodexAuthLoading={false}
        onCodexSettingsChange={vi.fn()}
        onSignIn={vi.fn()}
        onRefreshStatus={vi.fn()}
        onLogout={vi.fn()}
        onCancelLogin={vi.fn()}
      />,
    );

    expect(
      screen.getAllByText('pages.settings.sections.codex.login.notConnectedDescription'),
    ).toHaveLength(1);
  });

  it('dispatches direct model updates and connected logout action', async () => {
    const user = userEvent.setup();
    const onCodexSettingsChange = vi.fn();
    const onLogout = vi.fn();
    const connectedSettings: UserSettingsCodex = {
      ...pendingCodexSettings,
      loginStatus: 'connected',
      account: { email: 'codex@example.com', planType: 'pro' },
      authFlow: null,
    };

    render(
      <SettingsCodexTab
        codexSettings={connectedSettings}
        isCodexAuthLoading={false}
        onCodexSettingsChange={onCodexSettingsChange}
        onSignIn={vi.fn()}
        onRefreshStatus={vi.fn()}
        onLogout={onLogout}
        onCancelLogin={vi.fn()}
      />,
    );

    await user.type(screen.getByDisplayValue('gpt-5.6-sol'), 'x');
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.codex.login.disconnectButton' }));

    expect(onCodexSettingsChange).toHaveBeenLastCalledWith({
      ...connectedSettings,
      model: 'gpt-5.6-solx',
    });
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it('renders API key environment variables when API key auth is selected', () => {
    render(
      <SettingsCodexTab
        codexSettings={{
          ...pendingCodexSettings,
          authMethod: 'apikey',
          loginStatus: 'notConnected',
          authFlow: null,
        }}
        isCodexAuthLoading={false}
        onCodexSettingsChange={vi.fn()}
        onSignIn={vi.fn()}
        onRefreshStatus={vi.fn()}
        onLogout={vi.fn()}
        onCancelLogin={vi.fn()}
      />,
    );

    expect(screen.getByTestId('environment-variables')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.codex.environmentVariables.title')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.codex.environmentVariables.description')).toBeInTheDocument();
  });
});
