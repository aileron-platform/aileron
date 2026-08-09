import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SettingsSshTab } from './SettingsSshTab';
import type { UserSettingsSSH } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const sshKeys: UserSettingsSSH = {
  publicKey: 'ssh-ed25519 public-key',
  privateKey: 'private-key',
  fingerprint: 'SHA256:test',
  lastRotatedAt: '2026-05-07T00:00:00.000Z',
};

describe('SettingsSshTab', () => {
  it('renders masked private key and SSH actions with i18n keys', () => {
    render(
      <SettingsSshTab
        sshKeys={sshKeys}
        showPrivateKey={false}
        onSshKeysChange={vi.fn()}
        onShowPrivateKeyChange={vi.fn()}
        onCopyPrivateKey={vi.fn()}
        onCopyPublicKey={vi.fn()}
        onGenerateSSHKey={vi.fn()}
      />,
    );

    expect(screen.getByText('pages.settings.sections.ssh.title')).toBeInTheDocument();
    expect(screen.getByLabelText('pages.settings.sections.ssh.privateKey.label')).toHaveValue('••••••••••••');
    expect(screen.getByRole('button', { name: 'pages.settings.sections.ssh.generate' })).toBeInTheDocument();
  });

  it('dispatches SSH key field and action changes', async () => {
    const user = userEvent.setup();
    const onSshKeysChange = vi.fn();
    const onShowPrivateKeyChange = vi.fn();
    const onCopyPublicKey = vi.fn();
    const onGenerateSSHKey = vi.fn();

    render(
      <SettingsSshTab
        sshKeys={sshKeys}
        showPrivateKey
        onSshKeysChange={onSshKeysChange}
        onShowPrivateKeyChange={onShowPrivateKeyChange}
        onCopyPrivateKey={vi.fn()}
        onCopyPublicKey={onCopyPublicKey}
        onGenerateSSHKey={onGenerateSSHKey}
      />,
    );

    await user.clear(screen.getByLabelText('pages.settings.sections.ssh.publicKey.label'));
    await user.type(screen.getByLabelText('pages.settings.sections.ssh.publicKey.label'), 'ssh-ed25519 updated');
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.privateKey.actions.hide' }));
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.publicKey.copy' }));
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.generate' }));

    expect(onSshKeysChange).toHaveBeenCalled();
    expect(onShowPrivateKeyChange).toHaveBeenCalledWith(false);
    expect(onCopyPublicKey).toHaveBeenCalled();
    expect(onGenerateSSHKey).toHaveBeenCalled();
  });
});
