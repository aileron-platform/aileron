import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceSettingsView } from './MarketplaceSettingsView';

const marketplaceApiMock = vi.hoisted(() => ({
  getRegistrySettings: vi.fn(),
  getRegistryRepository: vi.fn(),
  saveRegistrySettings: vi.fn(),
  initializeRegistryGit: vi.fn(),
  cloneRegistry: vi.fn(),
  setRegistryRemote: vi.fn(),
  getRegistryGitStatus: vi.fn(),
  getRegistryCommits: vi.fn(),
  getRegistryCommitFiles: vi.fn(),
  getRegistryFileDiff: vi.fn(),
  getRegistryCommitFileDiff: vi.fn(),
  stageRegistryFiles: vi.fn(),
  unstageRegistryFiles: vi.fn(),
  commitRegistryChanges: vi.fn(),
  fetchRegistry: vi.fn(),
  pullRegistry: vi.fn(),
  pushRegistry: vi.fn(),
}));

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
}));

const clipboardWriteTextMock = vi.hoisted(() => vi.fn());

vi.mock('../../api/marketplaceApi', () => marketplaceApiMock);
vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: {
        id: 'user-123',
      },
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceSettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: clipboardWriteTextMock.mockResolvedValue(undefined),
      },
    });
    apiClientMock.get.mockResolvedValue({
      data: {
        general: {
          theme: 'system',
          language: 'zh-TW',
          timezone: 'Asia/Taipei',
          notifications: { desktop: true, email: true, updates: true },
          performance: { autoSave: true, animationsEnabled: true },
          privacy: { analytics: false, crashReports: true, usageData: false },
        },
        ssh: {
          publicKey: 'ssh-ed25519 user-public-key',
          privateKey: '-----BEGIN OPENSSH PRIVATE KEY-----\nuser-private-key\n-----END OPENSSH PRIVATE KEY-----',
          fingerprint: 'SHA256:user',
          lastRotatedAt: '2026-05-07T00:00:00.000Z',
        },
        claudeCode: {
          authMethod: 'apikey',
          authKey: null,
          environmentVariables: [],
        },
        codex: {
          authMethod: 'subscription',
          loginStatus: 'notConnected',
          account: null,
          model: 'gpt-5.3-codex',
          environmentVariables: [],
          authFlow: null,
        },
        git: {
          userName: null,
          userEmail: null,
          signingKey: null,
        },
        gemini: {
          authMethod: 'apikey',
          environmentVariables: [],
        },
      },
    });
    apiClientMock.put.mockImplementation(async (_path: string, payload: unknown) => ({ data: payload }));
    apiClientMock.post.mockResolvedValue({
      publicKey: 'ssh-ed25519 generated-user-public-key',
      privateKey: '-----BEGIN OPENSSH PRIVATE KEY-----\ngenerated-user-private-key\n-----END OPENSSH PRIVATE KEY-----',
      fingerprint: 'SHA256:generated-user',
      generatedAt: '2026-05-07T01:00:00.000Z',
    });
    marketplaceApiMock.getRegistrySettings.mockResolvedValue({
      displayName: 'marketplace.settings.general.mock.displayName',
      rootPath: '/tmp/marketplace',
      status: 'ready',
      description: 'marketplace.settings.general.mock.description',
      maintainerName: 'marketplace.settings.general.mock.maintainerName',
      maintainerEmail: 'marketplace.settings.general.mock.maintainerEmail',
      remoteUrl: 'git@github.com:example/marketplace-registry.git',
      branch: 'main',
      gitUserName: 'Marketplace Registry',
      gitUserEmail: 'marketplace@example.local',
    });
    marketplaceApiMock.saveRegistrySettings.mockResolvedValue({
      settings: {
        displayName: 'team-marketplace',
        rootPath: '/tmp/marketplace',
        status: 'ready',
        description: 'Team registry',
        maintainerName: 'Team Maintainer',
        maintainerEmail: 'team@example.local',
      },
    });
    marketplaceApiMock.getRegistryRepository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: 'git@github.com:example/marketplace-registry.git',
      hasOrigin: true,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
    });
    marketplaceApiMock.setRegistryRemote.mockResolvedValue({
      success: true,
      messageKey: 'marketplace.git.remote_update_success',
      repository: {
        isGitRepo: true,
        currentBranch: 'main',
        remoteUrl: 'git@github.com:example/updated-marketplace-registry.git',
        hasOrigin: true,
        hasLocalContent: true,
        canCloneSafely: false,
        canInitSafely: false,
      },
    });
    marketplaceApiMock.initializeRegistryGit.mockResolvedValue({
      success: true,
      messageKey: 'marketplace.git.init_success',
    });
    marketplaceApiMock.cloneRegistry.mockResolvedValue({
      success: true,
      messageKey: 'marketplace.git.clone_success',
    });
    marketplaceApiMock.getRegistryGitStatus.mockResolvedValue({
      branch: 'main',
      isGitRepo: true,
      staged: [{
        path: 'codex/plugins/figma-context/.codex-plugin/plugin.json',
        status: 'M',
        type: 'modified',
      }],
      unstaged: [{
        path: 'claude-code/plugins/review-assistant/README.md',
        status: 'M',
        type: 'modified',
      }],
      untracked: [],
      stagedCount: 1,
      unstagedCount: 1,
      untrackedCount: 0,
    });
    marketplaceApiMock.getRegistryCommits.mockResolvedValue({
      page: 1,
      pageSize: 50,
      total: 1,
      items: [{
        id: 'a1b2c3d',
        message: 'Update provider package listings',
        author: 'Marketplace Registry',
        email: 'marketplace@example.local',
        timestamp: '2026-05-06T08:30:00.000Z',
        additions: 38,
        deletions: 6,
        filesChanged: 2,
      }],
    });
    marketplaceApiMock.getRegistryCommitFiles.mockResolvedValue({
      commitId: 'a1b2c3d',
      files: [{
        path: 'claude-code/plugins/review-assistant/README.md',
        status: 'M',
        type: 'modified',
      }],
    });
    marketplaceApiMock.getRegistryFileDiff.mockResolvedValue({
      path: 'codex/plugins/figma-context/.codex-plugin/plugin.json',
      patch: '+  "version": "0.3.0"',
      diff: '+  "version": "0.3.0"',
      binary: false,
    });
    marketplaceApiMock.getRegistryCommitFileDiff.mockResolvedValue({
      path: 'claude-code/plugins/review-assistant/README.md',
      patch: '+Adds Claude Code review workflows',
      diff: '+Adds Claude Code review workflows',
      binary: false,
      commitId: 'a1b2c3d',
    });
    marketplaceApiMock.stageRegistryFiles.mockResolvedValue({});
    marketplaceApiMock.unstageRegistryFiles.mockResolvedValue({});
    marketplaceApiMock.commitRegistryChanges.mockResolvedValue({ success: true, messageKey: 'marketplace.git.commit_success' });
    marketplaceApiMock.fetchRegistry.mockResolvedValue({ success: true, messageKey: 'marketplace.git.fetch_success' });
    marketplaceApiMock.pullRegistry.mockResolvedValue({ success: true, messageKey: 'marketplace.git.pull_success' });
    marketplaceApiMock.pushRegistry.mockResolvedValue({ success: true, messageKey: 'marketplace.git.push_success' });
  });

  it('shows provider-neutral registry settings in General', () => {
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    expect(screen.getByText('marketplace.settings.general.displayName')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.maintainerName')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.maintainerEmail')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.rootPath')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.generatedPreviewTitle')).toBeInTheDocument();
    expect(screen.getByLabelText('claude-code/.claude-plugin/marketplace.json')).toBeInTheDocument();
    expect(screen.getByLabelText('codex/.agents/plugins/marketplace.json')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.status')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.defaultProvider')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.defaultViewMode')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.defaultWorkspace')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.version')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.pluginRoot')).not.toBeInTheDocument();
  });

  it('updates generated marketplace.json previews from root metadata fields', async () => {
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByDisplayValue('marketplace.settings.general.mock.displayName'), {
      target: { value: 'team-marketplace' },
    });

    expect((screen.getByLabelText('claude-code/.claude-plugin/marketplace.json') as HTMLTextAreaElement).value).toContain('team-marketplace');
    expect((screen.getByLabelText('codex/.agents/plugins/marketplace.json') as HTMLTextAreaElement).value).toContain('team-marketplace');
  });

  it('uses maintainer root metadata shape in generated registry previews', async () => {
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByDisplayValue('marketplace.settings.general.mock.maintainerName'), {
      target: { value: 'Team Maintainer' },
    });
    fireEvent.change(await screen.findByDisplayValue('marketplace.settings.general.mock.maintainerEmail'), {
      target: { value: 'team@example.local' },
    });

    const claudePreview = JSON.parse((screen.getByLabelText('claude-code/.claude-plugin/marketplace.json') as HTMLTextAreaElement).value);
    const codexPreview = JSON.parse((screen.getByLabelText('codex/.agents/plugins/marketplace.json') as HTMLTextAreaElement).value);
    expect(claudePreview).toMatchObject({
      owner: {
        name: 'Team Maintainer',
        email: 'team@example.local',
      },
      plugins: [],
    });
    expect(codexPreview).toMatchObject({ plugins: [] });
    expect(claudePreview.ownerName).toBeUndefined();
    expect(claudePreview.ownerEmail).toBeUndefined();
    expect(codexPreview.owner).toBeUndefined();
    expect(codexPreview.ownerName).toBeUndefined();
    expect(codexPreview.ownerEmail).toBeUndefined();
  });

  it('reviews registry changes and commit history in version control', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.versionControl' }));

    expect(screen.getByText('codex/plugins/figma-context/.codex-plugin/plugin.json')).toBeInTheDocument();
    await user.click(screen.getByText('codex/plugins/figma-context/.codex-plugin/plugin.json'));
    expect(screen.getByText(/"version": "0\.3\.0"/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /shared\.versionControl\.mode\.commitHistory/ }));
    expect(screen.getByText('Update provider package listings')).toBeInTheDocument();
    await user.click(screen.getByText('claude-code/plugins/review-assistant/README.md'));
    expect(screen.getByText(/Adds Claude Code review workflows/)).toBeInTheDocument();
  });

  it('moves unstaged registry files into staged changes from the stage response', async () => {
    const user = userEvent.setup();
    marketplaceApiMock.stageRegistryFiles.mockResolvedValueOnce({
      branch: 'main',
      isGitRepo: true,
      staged: [
        {
          path: 'codex/plugins/figma-context/.codex-plugin/plugin.json',
          status: 'M',
          type: 'modified',
        },
        {
          path: 'claude-code/plugins/review-assistant/README.md',
          status: 'M',
          type: 'modified',
        },
      ],
      unstaged: [],
      untracked: [],
      stagedCount: 2,
      unstagedCount: 0,
      untrackedCount: 0,
    });

    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.versionControl' }));
    await screen.findByText('claude-code/plugins/review-assistant/README.md');
    expect(screen.getAllByTitle('shared.versionControl.fileItem.unstageTooltip')).toHaveLength(1);

    await user.click(screen.getByTitle('shared.versionControl.fileItem.stageTooltip'));

    await waitFor(() => {
      expect(marketplaceApiMock.stageRegistryFiles).toHaveBeenCalledWith([
        'claude-code/plugins/review-assistant/README.md',
      ]);
      expect(screen.getAllByTitle('shared.versionControl.fileItem.unstageTooltip')).toHaveLength(2);
    });
    expect(screen.queryByTitle('shared.versionControl.fileItem.stageTooltip')).not.toBeInTheDocument();
  });

  it('initializes Git for existing local registry content before showing version control changes', async () => {
    const user = userEvent.setup();
    const uninitializedRepository = {
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: true,
    };
    marketplaceApiMock.getRegistryRepository
      .mockResolvedValueOnce(uninitializedRepository)
      .mockResolvedValueOnce(uninitializedRepository);
    marketplaceApiMock.initializeRegistryGit.mockResolvedValueOnce({
      success: true,
      messageKey: 'marketplace.git.init_success',
      repository: {
        isGitRepo: true,
        currentBranch: 'main',
        remoteUrl: null,
        hasOrigin: false,
        hasLocalContent: true,
        canCloneSafely: false,
        canInitSafely: false,
      },
    });
    marketplaceApiMock.getRegistryGitStatus.mockResolvedValueOnce({
      branch: 'main',
      isGitRepo: true,
      staged: [],
      unstaged: [],
      untracked: [{
        path: 'claude-code/plugins/settings/README.md',
        status: '??',
        type: 'untracked',
      }],
      stagedCount: 0,
      unstagedCount: 0,
      untrackedCount: 1,
    });

    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.versionControl' }));

    await waitFor(() => {
      expect(marketplaceApiMock.initializeRegistryGit).toHaveBeenCalled();
    });
    expect(await screen.findByText('claude-code/plugins/settings/README.md')).toBeInTheDocument();
  });

  it('opens remote configuration from the version control action menu', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    expect(screen.queryByRole('tab', { name: 'marketplace.settings.tabs.remote' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.versionControl' }));
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.actions.menu.label' }));
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.actions.remoteSettings.label' }));

    expect(screen.getByText('shared.versionControl.remoteDialog.title')).toBeInTheDocument();
    const remoteUrl = screen.getByLabelText('shared.versionControl.remoteDialog.remote.urlLabel');
    expect(remoteUrl).toHaveValue('git@github.com:example/marketplace-registry.git');

    await user.clear(remoteUrl);
    await user.type(remoteUrl, 'git@github.com:example/updated-marketplace-registry.git');
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.remoteDialog.remote.actions.save' }));

    expect(marketplaceApiMock.setRegistryRemote).toHaveBeenCalledWith('git@github.com:example/updated-marketplace-registry.git');
  });

  it('updates Git user identity fields without exposing provider-specific settings', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.gitUser' }));
    expect(screen.queryByText('marketplace.settings.git.repository.title')).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText('marketplace.settings.git.user.name'));
    await user.type(screen.getByLabelText('marketplace.settings.git.user.name'), 'Registry Maintainer');
    await user.clear(screen.getByLabelText('marketplace.settings.git.user.email'));
    await user.type(screen.getByLabelText('marketplace.settings.git.user.email'), 'registry@example.local');

    expect(screen.getByLabelText('marketplace.settings.git.user.name')).toHaveValue('Registry Maintainer');
    expect(screen.getByLabelText('marketplace.settings.git.user.email')).toHaveValue('registry@example.local');
  });

  it('uses the same user SSH key operations as global settings', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.sshKeys' }));

    const publicKey = await screen.findByLabelText('pages.settings.sections.ssh.publicKey.label');
    const privateKey = screen.getByLabelText('pages.settings.sections.ssh.privateKey.label');

    expect(publicKey).toHaveValue('ssh-ed25519 user-public-key');
    expect(privateKey).toHaveValue('••••••••••••');
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.privateKey.actions.show' }));
    expect(privateKey).toHaveValue('-----BEGIN OPENSSH PRIVATE KEY-----\nuser-private-key\n-----END OPENSSH PRIVATE KEY-----');
    expect(screen.getByRole('button', { name: 'pages.settings.sections.ssh.publicKey.copy' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'pages.settings.sections.ssh.generate' }));
    expect(apiClientMock.post).toHaveBeenCalledWith('/users/user-123/ssh-keys/generate');
    expect(publicKey).toHaveValue('ssh-ed25519 generated-user-public-key');
    await user.click(screen.getByRole('button', { name: 'pages.settings.actions.save' }));
    expect(apiClientMock.put).toHaveBeenCalledWith('/users/user-123/settings', expect.objectContaining({
      ssh: expect.objectContaining({
        publicKey: 'ssh-ed25519 generated-user-public-key',
        fingerprint: 'SHA256:generated-user',
      }),
    }));

    expect(screen.queryByText('marketplace.settings.ssh.importTitle')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('marketplace.settings.ssh.hostBindings')).not.toBeInTheDocument();
  });

  it('renders the registry activity empty state', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <MarketplaceSettingsView />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('tab', { name: 'marketplace.settings.tabs.activity' }));

    expect(screen.getByText('marketplace.settings.activity.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.activity.empty')).toBeInTheDocument();
  });
});
