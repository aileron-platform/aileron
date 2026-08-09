import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceActivityTab } from './MarketplaceActivityTab';
import { MarketplaceGeneralTab, type MarketplaceRootMetadata } from './MarketplaceGeneralTab';
import { MarketplaceSshKeysTab } from './MarketplaceSshKeysTab';
import type { UserSettingsSSH } from '@/shared/types/user';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('../../../api/marketplaceApi', () => ({
  listMarketplaceActivity: vi.fn(async () => ({
    items: [], total: 0, page: 1, pageSize: 50, totalPages: 0,
  })),
}));

describe('Marketplace settings tab panels', () => {
  it('renders editable root metadata and generated registry previews', () => {
    const metadata: MarketplaceRootMetadata = {
      name: 'team-marketplace',
      maintainerName: 'Team Maintainer',
      maintainerEmail: 'team@example.local',
      description: 'Team registry',
    };
    const onMetadataChange = vi.fn();

    render(
      <MarketplaceGeneralTab
        metadata={metadata}
        rootPath="/tmp/marketplace"
        isSaving={false}
        onMetadataChange={onMetadataChange}
        onSave={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByDisplayValue('team-marketplace'), {
      target: { value: 'internal-marketplace' },
    });
    expect(onMetadataChange).toHaveBeenCalledWith({ ...metadata, name: 'internal-marketplace' });
    const claudePreview = screen.getByLabelText('claude-code/.claude-plugin/marketplace.json') as HTMLTextAreaElement;
    const codexPreview = screen.getByLabelText('codex/.agents/plugins/marketplace.json') as HTMLTextAreaElement;
    expect(claudePreview.value).toContain('"owner"');
    expect(codexPreview.value).not.toContain('"owner"');
  });

  it('supports user SSH key visibility, copy, generate, and save actions', async () => {
    const user = userEvent.setup();
    const sshKeys: UserSettingsSSH = {
      publicKey: 'ssh-ed25519 public-key',
      privateKey: 'private-key',
      fingerprint: 'SHA256:test',
      lastRotatedAt: '2026-05-07T00:00:00.000Z',
    };
    const onShowPrivateKeyChange = vi.fn();
    const onCopy = vi.fn();
    const onGenerateSshKey = vi.fn();
    const onSaveSshKeys = vi.fn();

    render(
      <MarketplaceSshKeysTab
        sshKeys={sshKeys}
        showPrivateKey={false}
        onSshKeysChange={vi.fn()}
        onShowPrivateKeyChange={onShowPrivateKeyChange}
        onGenerateSshKey={onGenerateSshKey}
        onSaveSshKeys={onSaveSshKeys}
        onCopy={onCopy}
      />,
    );

    expect(screen.getByLabelText('pages.settings.sections.ssh.privateKey.label')).toHaveValue('••••••••••••');
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.privateKey.actions.show' }));
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.publicKey.copy' }));
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.generate' }));
    await user.click(screen.getByRole('button', { name: 'pages.settings.actions.save' }));

    expect(onShowPrivateKeyChange).toHaveBeenCalledWith(true);
    expect(onCopy).toHaveBeenCalledWith('ssh-ed25519 public-key');
    expect(onGenerateSshKey).toHaveBeenCalled();
    expect(onSaveSshKeys).toHaveBeenCalled();
  });

  it('renders registry activity empty state with i18n keys', async () => {
    render(<MemoryRouter><MarketplaceActivityTab /></MemoryRouter>);
    expect(screen.getByText('marketplace.settings.activity.title')).toBeInTheDocument();
    expect(await screen.findByText('marketplace.settings.activity.empty')).toBeInTheDocument();
  });
});
