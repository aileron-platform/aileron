import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsClaudeCodeTab } from './SettingsClaudeCodeTab';
import type { UserSettingsClaudeCode } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const subscriptionSettings: UserSettingsClaudeCode = {
  authMethod: 'subscription',
  authKey: null,
  model: 'claude-opus-4-8',
  subscriptionAccessToken: 'token',
  environmentVariables: [],
  modelSelection: {
    availableModels: ['claude-opus-4-8'],
    customModels: [],
    allowedModels: ['claude-opus-4-8'],
    defaultModel: 'claude-opus-4-8',
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

describe('SettingsClaudeCodeTab', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
  });

  it('renders connected subscription state with i18n account fallback', () => {
    const { container } = render(
      <SettingsClaudeCodeTab
        claudeCodeSettings={subscriptionSettings}
        fallbackAccountEmail={null}
        showAuthCodeInput={false}
        isExchangingCode={false}
        tempAuthCode=""
        onClaudeCodeSettingsChange={vi.fn()}
        onTempAuthCodeChange={vi.fn()}
        onConnect={vi.fn()}
        onSaveAuthCode={vi.fn()}
        onCancelAuth={vi.fn()}
        onDisconnect={vi.fn()}
      />,
    );

    expect(screen.getByText('pages.settings.sections.claudeCode.title')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.claudeCode.subscription.status.connected')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.claudeCode.subscription.accountUnavailable')).toBeInTheDocument();
    expect(screen.getAllByText('pages.settings.sections.claudeCode.subscription.title')).toHaveLength(1);
    expect(
      screen.getByRole('button', { name: 'pages.settings.sections.claudeCode.subscription.disconnectButton' }),
    ).toBeInTheDocument();
    expectOnlyOuterCard(container);
  });

  it('dispatches auth code input and save/cancel actions', async () => {
    const user = userEvent.setup();
    const onTempAuthCodeChange = vi.fn();
    const onSaveAuthCode = vi.fn();
    const onCancelAuth = vi.fn();

    const { container } = render(
      <SettingsClaudeCodeTab
        claudeCodeSettings={{ ...subscriptionSettings, subscriptionAccessToken: undefined }}
        fallbackAccountEmail="dev@example.com"
        showAuthCodeInput
        isExchangingCode={false}
        tempAuthCode="code"
        onClaudeCodeSettingsChange={vi.fn()}
        onTempAuthCodeChange={onTempAuthCodeChange}
        onConnect={vi.fn()}
        onSaveAuthCode={onSaveAuthCode}
        onCancelAuth={onCancelAuth}
        onDisconnect={vi.fn()}
      />,
    );

    await user.type(screen.getByDisplayValue('code'), 'x');
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.claudeCode.subscription.saveButton' }));
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.claudeCode.subscription.cancelButton' }));

    expect(onTempAuthCodeChange).toHaveBeenCalledWith('codex');
    expect(onSaveAuthCode).toHaveBeenCalledTimes(1);
    expect(onCancelAuth).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText('pages.settings.sections.claudeCode.subscription.title')).toHaveLength(1);
    expectOnlyOuterCard(container);
  });

  it('renders API key controls and environment variables', () => {
    const { container } = render(
      <SettingsClaudeCodeTab
        claudeCodeSettings={{
          authMethod: 'apikey',
          authKey: null,
          apiProvider: 'anthropic',
          model: 'claude-opus-4-8',
          environmentVariables: [{ key: 'ANTHROPIC_API_KEY', value: 'test-api-key' }],
          modelSelection: {
            availableModels: ['claude-opus-4-8'],
            customModels: [],
            allowedModels: ['claude-opus-4-8'],
            defaultModel: 'claude-opus-4-8',
          },
        }}
        fallbackAccountEmail={null}
        showAuthCodeInput={false}
        isExchangingCode={false}
        tempAuthCode=""
        onClaudeCodeSettingsChange={vi.fn()}
        onTempAuthCodeChange={vi.fn()}
        onConnect={vi.fn()}
        onSaveAuthCode={vi.fn()}
        onCancelAuth={vi.fn()}
        onDisconnect={vi.fn()}
      />,
    );

    expect(screen.getByText('pages.settings.sections.claudeCode.apikey.providerLabel')).toBeInTheDocument();
    expect(screen.getByText('pages.settings.sections.claudeCode.apikey.modelLabel')).toBeInTheDocument();
    expect(screen.getByDisplayValue('ANTHROPIC_API_KEY')).toBeInTheDocument();
    expect(screen.getByDisplayValue('test-api-key')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'pages.settings.sections.claudeCode.environmentVariables.title' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /addButton/ })).not.toBeInTheDocument();
    expectOnlyOuterCard(container);
  });
});
