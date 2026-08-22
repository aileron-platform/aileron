import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceSettingsPage } from './MarketplaceSettingsPage';

const marketplaceApiMock = vi.hoisted(() => ({
  getRegistrySettings: vi.fn(),
  saveRegistrySettings: vi.fn(),
  listMarketplaceActivity: vi.fn(),
}));

const versionControlMocks = vi.hoisted(() => ({
  repository: vi.fn(),
  initialize: vi.fn(),
  clone: vi.fn(),
  setRemote: vi.fn(),
  commits: vi.fn(),
  commitFiles: vi.fn(),
  workingDiff: vi.fn(),
  commitDiff: vi.fn(),
}));

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
}));

// The session owns the API boundary. ApiError is shared so its retry and
// operation-conflict policies observe the same error instance in tests.
const { sharedClient, MockApiError } = vi.hoisted(() => {
  class MockApiError extends Error {
    status: number;

    errorCode?: string;

    messageKey?: string;

    stale?: boolean;

    canForceUnlock?: boolean;

    constructor(
      message: string,
      status: number,
      errorCode?: string,
      metadata?: { messageKey?: string; stale?: boolean; canForceUnlock?: boolean },
    ) {
      super(message);
      this.status = status;
      this.errorCode = errorCode;
      this.messageKey = metadata?.messageKey;
      this.stale = metadata?.stale;
      this.canForceUnlock = metadata?.canForceUnlock;
    }
  }
  return {
    sharedClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), patch: vi.fn() },
    MockApiError,
  };
});

const clipboardWriteTextMock = vi.hoisted(() => vi.fn());
const toastMock = vi.hoisted(() => vi.fn());
const authState = vi.hoisted(() => ({ isPlatformAdmin: true }));

vi.mock('../../api/marketplaceApi', () => marketplaceApiMock);
vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
  ApiClient: vi.fn().mockImplementation(() => sharedClient),
  ApiError: MockApiError,
}));
vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));
vi.mock('@/features/auth/public', () => ({
  useAuth: () => authState,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.isPlatformAdmin = true;
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
          model: 'gpt-5.6-sol',
          environmentVariables: [],
          authFlow: null,
        },
        git: {
          userName: null,
          userEmail: null,
          signingKey: null,
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
    versionControlMocks.repository.mockResolvedValue({
      isGitRepo: true,
      currentBranch: 'main',
      remoteUrl: 'git@github.com:example/marketplace-registry.git',
      hasOrigin: true,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: false,
    });
    marketplaceApiMock.listMarketplaceActivity.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 50,
      totalPages: 0,
    });
    versionControlMocks.setRemote.mockResolvedValue({
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
    versionControlMocks.initialize.mockResolvedValue({
      success: true,
      messageKey: 'marketplace.git.init_success',
    });
    versionControlMocks.clone.mockResolvedValue({
      success: true,
      messageKey: 'marketplace.git.clone_success',
    });
    resetChanges();
    sharedClient.get.mockImplementation(routeVersionControlGet);
    sharedClient.post.mockImplementation(routeVersionControlPost);
    sharedClient.put.mockImplementation(routeVersionControlPut);
    versionControlMocks.commits.mockResolvedValue({
      total: 1,
      nextCursor: null,
      hasMore: false,
      queryScope: 'current',
      items: [{
        id: 'a1b2c3d',
        message: 'Update targetClient package listings',
        author: 'Marketplace Registry',
        email: 'marketplace@example.local',
        timestamp: Date.parse('2026-05-06T08:30:00.000Z') / 1000,
        additions: 38,
        deletions: 6,
        files: 2,
      }],
    });
    versionControlMocks.commitFiles.mockResolvedValue({
      commitId: 'a1b2c3d',
      files: [{
        name: 'README.md',
        path: 'claude-code/plugins/review-assistant/README.md',
        status: 'M',
        type: 'modified',
      }],
    });
    versionControlMocks.workingDiff.mockResolvedValue({
      path: 'codex/plugins/figma-context/.codex-plugin/plugin.json',
      patch: '+  "version": "0.3.0"',
      diff: '+  "version": "0.3.0"',
      binary: false,
    });
    versionControlMocks.commitDiff.mockResolvedValue({
      path: 'claude-code/plugins/review-assistant/README.md',
      patch: '+Adds Claude Code review workflows',
      diff: '+Adds Claude Code review workflows',
      binary: false,
      commitId: 'a1b2c3d',
    });
  });

const statusFixture = () => ({
  isInitialized: true,
  currentBranch: 'main',
  detachedHead: false,
  headSha: 'a1b2c3d',
  hasOrigin: true,
  upstream: 'origin/main',
  ahead: 0,
  behind: 0,
  hasConflicts: false,
  stagedTotal: 1,
  unstagedTotal: 1,
  untrackedTotal: 0,
  conflictTotal: 0,
  operationStatus: null,
});

// Unified changes shape returned by the session's GET /changes query. Stateful so
// a stage/unstage POST can move a file and the subsequent refetch confirms the
// optimistic update (no flash/revert). additions/deletions present to keep the
// deferred numstat query idle.
const initialChanges = () => ({
  staged: { items: [{
    name: 'plugin.json',
    path: 'codex/plugins/figma-context/.codex-plugin/plugin.json',
    status: 'M',
    type: 'modified',
    additions: 1,
    deletions: 0,
  }], total: 1, nextCursor: null, hasMore: false },
  unstaged: { items: [{
    name: 'README.md',
    path: 'claude-code/plugins/review-assistant/README.md',
    status: 'M',
    type: 'modified',
    additions: 1,
    deletions: 0,
  }], total: 1, nextCursor: null, hasMore: false },
  untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
  conflicts: { items: [], total: 0, nextCursor: null, hasMore: false },
});
let changesState = initialChanges();
const resetChanges = () => {
  changesState = initialChanges();
};

const routeVersionControlGet = async (url: string) => {
  if (url.endsWith('/version-control/repository')) {
    return versionControlMocks.repository();
  }
  if (url.includes('/version-control/changes')) {
    return JSON.parse(JSON.stringify(changesState));
  }
  if (url.includes('/version-control/operation-status')) {
    return { isActive: false };
  }
  if (url.includes('/version-control/status')) {
    return statusFixture();
  }
  if (url.includes('/version-control/commits/') && url.includes('/diff?')) {
    const commitId = decodeURIComponent(url.split('/commits/')[1]?.split('/')[0] ?? '');
    const params = new URLSearchParams(url.split('?')[1] ?? '');
    return versionControlMocks.commitDiff(commitId, params.get('path'));
  }
  if (url.includes('/version-control/commits/') && url.endsWith('/files')) {
    const commitId = decodeURIComponent(url.split('/commits/')[1]?.split('/')[0] ?? '');
    return versionControlMocks.commitFiles(commitId);
  }
  if (url.includes('/version-control/commits?')) {
    const params = new URLSearchParams(url.split('?')[1] ?? '');
    return versionControlMocks.commits(
      Number(params.get('page') ?? 1),
      Number(params.get('pageSize') ?? 50),
    );
  }
  if (url.includes('/version-control/diff?')) {
    const params = new URLSearchParams(url.split('?')[1] ?? '');
    return versionControlMocks.workingDiff(params.get('path'), params.get('head'));
  }
  return {};
};

const routeVersionControlPost = async (url: string, body?: unknown) => {
  if (url.endsWith('/version-control/init')) {
    return versionControlMocks.initialize(body);
  }
  if (url.endsWith('/version-control/clone')) {
    return versionControlMocks.clone(body);
  }
  if (url.endsWith('/version-control/remote-branches')) {
    return { branches: ['main', 'develop'], defaultBranch: 'develop' };
  }
  // Simulate the backend confirming an optimistic stage move so the
  // post-success refetch keeps the file staged.
  if (url.includes('/version-control/stage') && body && Array.isArray((body as { paths?: string[] }).paths)) {
    const paths = new Set((body as { paths: string[] }).paths);
    const moved = changesState.unstaged.items.filter((file: { path: string }) => paths.has(file.path));
    changesState = {
      ...changesState,
      staged: {
        ...changesState.staged,
        items: [...changesState.staged.items, ...moved],
        total: changesState.staged.total + moved.length,
      },
      unstaged: {
        ...changesState.unstaged,
        items: changesState.unstaged.items.filter((file: { path: string }) => !paths.has(file.path)),
        total: Math.max(0, changesState.unstaged.total - moved.length),
      },
    };
  }
  return {};
};

const routeVersionControlPut = async (url: string, body?: unknown) => {
  if (url.endsWith('/version-control/remote')) {
    return versionControlMocks.setRemote(
      (body as { remoteUrl?: string } | undefined)?.remoteUrl,
    );
  }
  return {};
};

const LocationProbe = () => {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
};

const renderView = (initialEntry = '/') => render(
  <QueryClientProvider client={new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false, gcTime: 0 },
    },
  })}
  >
    <MemoryRouter initialEntries={[initialEntry]}>
      <LocationProbe />
      <MarketplaceSettingsPage userId="user-123" />
    </MemoryRouter>
  </QueryClientProvider>,
);

  it('renders Marketplace breadcrumbs in the settings header', async () => {
    renderView('/?section=general');

    await screen.findByDisplayValue('marketplace.settings.general.mock.displayName');
    expect(screen.getByText('marketplace.breadcrumbs.root')).toBeInTheDocument();
    expect(within(screen.getByRole('complementary', {
      name: 'marketplace.settings.navigation.label',
    })).getByText('marketplace.settings.title')).toBeInTheDocument();
  });

  it('renders settings categories as semantic navigation instead of a horizontal tablist', async () => {
    renderView('/?section=sshKeys');

    const navigation = screen.getByRole('complementary', {
      name: 'marketplace.settings.navigation.label',
    });
    expect(navigation.querySelector('[role="tablist"]')).toBeNull();
    expect(screen.getByRole('button', { name: 'marketplace.settings.sections.sshKeys' }))
      .toHaveAttribute('aria-current', 'page');
  });

  it('does not mount registry sections for a member', async () => {
    authState.isPlatformAdmin = false;

    renderView('/?section=versionControl');

    expect(
      await screen.findByText('marketplace.settings.activity.title'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'marketplace.settings.sections.general' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'marketplace.settings.sections.versionControl' }),
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(apiClientMock.get).toHaveBeenCalledWith('/users/user-123/settings');
    });
    expect(marketplaceApiMock.getRegistrySettings).not.toHaveBeenCalled();
    expect(marketplaceApiMock.saveRegistrySettings).not.toHaveBeenCalled();
    expect(versionControlMocks.repository).not.toHaveBeenCalled();
    expect(versionControlMocks.initialize).not.toHaveBeenCalled();
    expect(versionControlMocks.clone).not.toHaveBeenCalled();
    expect(versionControlMocks.setRemote).not.toHaveBeenCalled();
  });

  it('shows targetClient-neutral registry settings in General', async () => {
    renderView();

    await screen.findByDisplayValue('marketplace.settings.general.mock.displayName');
    expect(screen.getByText('marketplace.settings.general.displayName')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.maintainerName')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.maintainerEmail')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.rootPath')).toBeInTheDocument();
    expect(screen.getByText('marketplace.settings.general.generatedPreviewTitle')).toBeInTheDocument();
    expect(screen.getByLabelText('claude-code/.claude-plugin/marketplace.json')).toBeInTheDocument();
    expect(screen.getByLabelText('codex/.agents/plugins/marketplace.json')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.status')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.defaultTargetClient')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.defaultViewMode')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.defaultWorkspace')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.version')).not.toBeInTheDocument();
    expect(screen.queryByText('marketplace.settings.general.pluginRoot')).not.toBeInTheDocument();
  });

  it('updates generated marketplace.json previews from root metadata fields', async () => {
    renderView();

    fireEvent.change(await screen.findByDisplayValue('marketplace.settings.general.mock.displayName'), {
      target: { value: 'team-marketplace' },
    });

    expect((screen.getByLabelText('claude-code/.claude-plugin/marketplace.json') as HTMLTextAreaElement).value).toContain('team-marketplace');
    expect((screen.getByLabelText('codex/.agents/plugins/marketplace.json') as HTMLTextAreaElement).value).toContain('team-marketplace');
  });

  it('uses maintainer root metadata shape in generated registry previews', async () => {
    renderView();

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
    renderView('/?section=versionControl');

    await screen.findByText('claude-code/plugins/review-assistant/README.md');
    expect(document.querySelectorAll('[data-shell-region="navigation"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-shell-region="navigator"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-shell-region="main"]')).toHaveLength(1);
    expect(screen.queryByTestId('marketplace-version-control-presentation')).not.toBeInTheDocument();
    expect(within(screen.getByRole('complementary', {
      name: 'marketplace.settings.navigation.label',
    })).getByText('marketplace.settings.title')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.versionControl.mode.fileChanges' }))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.versionControl.mode.commitHistory' }))
      .toBeInTheDocument();
    expect(screen.queryByTestId('marketplace-version-control-mode-actions')).not.toBeInTheDocument();
    const changesCallsBeforeRefresh = sharedClient.get.mock.calls.filter(
      ([url]) => String(url).includes('/marketplace/version-control/changes'),
    ).length;
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.actions.refresh.label',
    }));
    await waitFor(() => {
      expect(sharedClient.get.mock.calls.filter(
        ([url]) => String(url).includes('/marketplace/version-control/changes'),
      ).length).toBeGreaterThan(changesCallsBeforeRefresh);
    });
    fireEvent.click(screen.getByText('codex/plugins/figma-context/.codex-plugin/plugin.json'));
    expect(await screen.findByText(/"version": "0\.3\.0"/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'shared.versionControl.mode.commitHistory' }));
    expect(await screen.findByText('Update targetClient package listings')).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'shared.versionControl.actions.refresh.label',
    })).toBeInTheDocument();
    fireEvent.click(screen.getByText('claude-code/plugins/review-assistant/README.md'));
    expect(await screen.findByText(/Adds Claude Code review workflows/)).toBeInTheDocument();
  });

  it('canonicalizes legacy version-control URLs and keeps submenu state in the first column', async () => {
    const user = userEvent.setup();
    renderView('/?tab=versionControl&mode=history');

    expect(await screen.findByText('Update targetClient package listings')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('location-search')).toHaveTextContent(
        '?section=versionControl&submenu=history',
      );
    });
    expect(screen.queryByTestId('marketplace-version-control-mode-actions')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'shared.versionControl.mode.fileChanges' }));
    await waitFor(() => {
      expect(screen.getByTestId('location-search')).toHaveTextContent(
        '?section=versionControl&submenu=changes',
      );
    });
    expect(await screen.findByText('claude-code/plugins/review-assistant/README.md')).toBeInTheDocument();
  });

  it('moves unstaged registry files into staged changes from the stage response', async () => {
    const user = userEvent.setup();

    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('claude-code/plugins/review-assistant/README.md');
    expect(screen.getAllByTitle('shared.versionControl.fileItem.unstageTooltip')).toHaveLength(1);

    await user.click(screen.getByTitle('shared.versionControl.fileItem.stageTooltip'));

    await waitFor(() => {
      expect(sharedClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/marketplace/version-control/stage'),
        { paths: ['claude-code/plugins/review-assistant/README.md'] },
      );
      expect(screen.getAllByTitle('shared.versionControl.fileItem.unstageTooltip')).toHaveLength(2);
    });
    expect(screen.queryByTitle('shared.versionControl.fileItem.stageTooltip')).not.toBeInTheDocument();
  });

  it('uses all requests for Marketplace registry header stage and unstage actions', async () => {
    const user = userEvent.setup();

    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('claude-code/plugins/review-assistant/README.md');

    await user.click(screen.getByTitle('shared.versionControl.fileChanges.stageAllTooltip'));
    await waitFor(() => {
      expect(sharedClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/marketplace/version-control/stage'),
        { all: true },
      );
    });

    await user.click(screen.getByTitle('shared.versionControl.fileChanges.unstageAllTooltip'));
    await waitFor(() => {
      expect(sharedClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/marketplace/version-control/unstage'),
        { all: true },
      );
    });
  });

  it('disables registry write actions while a version-control operation is reported active', async () => {
    const user = userEvent.setup();
    sharedClient.get.mockImplementation(async (url: string) => {
      if (url.includes('/version-control/operation-status')) {
        return { isActive: true, operation: 'changes.commit' };
      }
      return routeVersionControlGet(url);
    });

    renderView();
    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('claude-code/plugins/review-assistant/README.md');

    // isOperationActive feeds isMutating, which disables the stage/unstage-all
    // header actions while an operation is in progress.
    await waitFor(() => {
      expect(screen.getByTitle('shared.versionControl.fileChanges.stageAllTooltip')).toBeDisabled();
      expect(screen.getByTitle('shared.versionControl.fileChanges.unstageAllTooltip')).toBeDisabled();
    });
  });

  it('shows operation-in-progress toast without clearing Marketplace registry changes', async () => {
    const user = userEvent.setup();
    sharedClient.post.mockImplementation(async (url: string) => {
      if (url.includes('/version-control/stage')) {
        throw {
          status: 409,
          errorCode: 'operation_locked',
          message: 'Marketplace registry Git operation already in progress',
        };
      }
      return {};
    });

    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('claude-code/plugins/review-assistant/README.md');
    await user.click(screen.getByTitle('shared.versionControl.fileItem.stageTooltip'));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
        title: 'marketplace.settings.versionControl.toasts.operationInProgress.title',
        description: 'marketplace.settings.versionControl.toasts.operationInProgress.description',
        variant: 'destructive',
      }));
    });
    // Optimistic stage rolled back; the file remains unstaged.
    expect(screen.getByText('claude-code/plugins/review-assistant/README.md')).toBeInTheDocument();
  });

  it('does not initialize Git automatically for existing local registry content', async () => {
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
    versionControlMocks.repository.mockResolvedValue(uninitializedRepository);

    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));

    expect(await screen.findByText('shared.versionControl.repositorySetup.title')).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.init',
    })).toBeEnabled();
    expect(screen.getByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.clone',
    })).toBeDisabled();
    await waitFor(() => {
      expect(versionControlMocks.initialize).not.toHaveBeenCalled();
    });
  });

  it('initializes Marketplace Git from the shared repository setup', async () => {
    const user = userEvent.setup();
    versionControlMocks.repository.mockResolvedValue({
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: false,
      canCloneSafely: true,
      canInitSafely: true,
    });

    renderView('/?section=versionControl');

    await user.click(await screen.findByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.init',
    }));
    await user.click(screen.getAllByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.init',
    }).at(-1)!);

    await waitFor(() => expect(versionControlMocks.initialize).toHaveBeenCalledWith({ defaultBranch: 'main' }));
  });

  it('clones Marketplace Git from the shared repository setup dialog', async () => {
    const user = userEvent.setup();
    versionControlMocks.repository.mockResolvedValue({
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: false,
      canCloneSafely: true,
      canInitSafely: true,
    });

    renderView('/?section=versionControl');

    await user.click(await screen.findByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.clone',
    }));
    await user.type(
      screen.getByLabelText('shared.versionControl.repositorySetup.clone.urlLabel'),
      'git@example.com:team/marketplace.git',
    );
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.repositorySetup.clone.actions.loadBranches',
    }));
    expect(await screen.findByRole('combobox', {
      name: 'shared.versionControl.repositorySetup.clone.branchLabel',
    })).toHaveTextContent('develop');
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.clone',
    }));

    await waitFor(() => expect(versionControlMocks.clone).toHaveBeenCalledWith({
      remoteUrl: 'git@example.com:team/marketplace.git',
      branch: 'develop',
    }));
  });

  it('keeps the clone dialog open and guides missing SSH keys to settings', async () => {
    const user = userEvent.setup();
    versionControlMocks.repository.mockResolvedValue({
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: false,
      canCloneSafely: true,
      canInitSafely: true,
    });
    versionControlMocks.clone.mockRejectedValue(
      new MockApiError('SSH key required', 409, 'VC_SSH_KEY_REQUIRED'),
    );

    renderView('/?section=versionControl');

    await user.click(await screen.findByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.clone',
    }));
    await user.type(
      screen.getByLabelText('shared.versionControl.repositorySetup.clone.urlLabel'),
      'git@example.com:team/marketplace.git',
    );
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.repositorySetup.clone.actions.loadBranches',
    }));
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.repositorySetup.actions.clone',
    }));

    expect(await screen.findByText(
      'shared.versionControl.repositorySetup.sshKeyRequired.title',
    )).toBeInTheDocument();
    expect(
      screen.getByLabelText('shared.versionControl.repositorySetup.clone.urlLabel'),
    ).toBeInTheDocument();
  });

  it('opens remote configuration from the version control action menu', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('codex/plugins/figma-context/.codex-plugin/plugin.json');
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.actions.menu.label' }));
    await user.click(screen.getByRole('menuitem', { name: 'shared.versionControl.actions.remoteSettings.label' }));

    expect(screen.getByText('shared.versionControl.remoteDialog.title')).toBeInTheDocument();
    const remoteUrl = screen.getByLabelText('shared.versionControl.remoteDialog.remote.urlLabel');
    expect(remoteUrl).toHaveValue('git@github.com:example/marketplace-registry.git');

    fireEvent.change(remoteUrl, {
      target: { value: 'git@github.com:example/updated-marketplace-registry.git' },
    });
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.remoteDialog.remote.actions.save' }));

    expect(versionControlMocks.setRemote).toHaveBeenCalledWith('git@github.com:example/updated-marketplace-registry.git');
  });

  it('refreshes repository status and history after saving Marketplace registry remote settings', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('codex/plugins/figma-context/.codex-plugin/plugin.json');
    vi.clearAllMocks();

    await user.click(screen.getByRole('button', { name: 'shared.versionControl.actions.menu.label' }));
    await user.click(screen.getByRole('menuitem', { name: 'shared.versionControl.actions.remoteSettings.label' }));
    const remoteUrl = screen.getByLabelText('shared.versionControl.remoteDialog.remote.urlLabel');
    fireEvent.change(remoteUrl, {
      target: { value: 'git@github.com:example/updated-marketplace-registry.git' },
    });
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.remoteDialog.remote.actions.save' }));

    await waitFor(() => {
      expect(versionControlMocks.setRemote).toHaveBeenCalledWith('git@github.com:example/updated-marketplace-registry.git');
      expect(versionControlMocks.repository).toHaveBeenCalled();
      expect(versionControlMocks.commits).toHaveBeenCalledWith(1, 50);
    });
    // Changes and status refresh through the session-owned client.
    expect(sharedClient.get).toHaveBeenCalledWith(expect.stringContaining('/marketplace/version-control/changes'));
  });

  it('refreshes Marketplace registry status and history after commit', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.versionControl' }));
    await screen.findByText('codex/plugins/figma-context/.codex-plugin/plugin.json');
    vi.clearAllMocks();

    fireEvent.change(screen.getByPlaceholderText('shared.versionControl.commitForm.placeholder'), {
      target: { value: 'Update registry' },
    });
    await user.click(screen.getByRole('button', { name: 'shared.versionControl.commitForm.submit' }));

    await waitFor(() => {
      expect(sharedClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/marketplace/version-control/commit'),
        { message: 'Update registry' },
      );
      expect(versionControlMocks.commits).toHaveBeenCalledWith(1, 50);
    });
    expect(sharedClient.get).toHaveBeenCalledWith(expect.stringContaining('/marketplace/version-control/changes'));
  });

  it('uses the same user SSH key operations as global settings', async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.sshKeys' }));

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
    renderView();

    await user.click(screen.getByRole('button', { name: 'marketplace.settings.sections.activity' }));

    expect(screen.getByText('marketplace.settings.activity.title')).toBeInTheDocument();
    expect(
      await screen.findByText('marketplace.settings.activity.empty'),
    ).toBeInTheDocument();
  });

});
