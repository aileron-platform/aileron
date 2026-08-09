import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/apiClient';

import { CommitHistoryPanel } from './CommitHistoryPanel';

const {
  commitsQueryMock,
  filesQueryMock,
  cloneRepositoryMutationMock,
  initializeRepositoryMutationMock,
  toastMock,
} = vi.hoisted(() => ({
  commitsQueryMock: {
    data: { pages: [{ items: [] }] },
    isLoading: false,
    isFetchingNextPage: false,
    hasNextPage: false,
    fetchNextPage: vi.fn(),
    error: null as unknown,
    lastBranch: undefined as string | undefined,
    lastSearch: undefined as string | undefined,
    lastLimit: undefined as number | undefined,
  },
  filesQueryMock: {
    data: [],
    isLoading: false,
    error: null as unknown,
  },
  initializeRepositoryMutationMock: {
    mutateAsync: vi.fn(),
    isPending: false,
  },
  cloneRepositoryMutationMock: {
    mutateAsync: vi.fn(),
    isPending: false,
  },
  toastMock: vi.fn(),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: {
      versionControl: {
        selectedGitContextId: null,
      },
    },
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime',
      workspaceId: 'ws-history',
    },
    permissions: {
      canWrite: true,
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => ({
      'shared.versionControl.commitHistory.filters.allBranches': 'All branches',
      'shared.versionControl.commitHistory.filters.searchPlaceholder': 'Search commits',
      'shared.versionControl.commitHistory.filters.searchAriaLabel': 'Search commits',
      'shared.versionControl.actions.branch.label': 'Branch',
      'shared.versionControl.repositorySetup.title': 'Version control is not set up',
      'shared.versionControl.repositorySetup.description': 'Initialize a repository or clone an existing one.',
      'shared.versionControl.repositorySetup.actions.init': 'Initialize Git',
      'shared.versionControl.repositorySetup.actions.initializing': 'Initializing...',
      'shared.versionControl.repositorySetup.actions.clone': 'Clone Repository',
      'shared.versionControl.repositorySetup.initializeDialog.title': 'Initialize Git repository',
      'shared.versionControl.repositorySetup.initializeDialog.description': 'Choose the default branch.',
      'shared.versionControl.repositorySetup.initializeDialog.defaultBranchLabel': 'Default branch',
      'shared.versionControl.repositorySetup.initializeDialog.cancel': 'Cancel',
      'shared.versionControl.repositorySetup.errors.title': 'Setup failed',
      'shared.versionControl.repositorySetup.errors.init': 'Unable to initialize repository.',
      'shared.versionControl.repositorySetup.errors.clone': 'Unable to clone repository.',
      'shared.versionControl.repositorySetup.errors.discovery': 'Unable to load branches.',
      'shared.versionControl.repositorySetup.dialog.title': 'Clone repository',
      'shared.versionControl.repositorySetup.dialog.description': 'Clone a remote repository.',
      'shared.versionControl.repositorySetup.localContentWarning': 'Local content exists.',
      'shared.versionControl.repositorySetup.clone.urlLabel': 'Repository URL',
      'shared.versionControl.repositorySetup.clone.urlPlaceholder': 'git@example.com:team/repo.git',
      'shared.versionControl.repositorySetup.clone.branchLabel': 'Branch',
      'shared.versionControl.repositorySetup.clone.branchPlaceholder': 'main',
      'shared.versionControl.repositorySetup.clone.branchHelper': 'Default branch selected.',
      'shared.versionControl.repositorySetup.clone.branchesEmpty': 'No branches.',
      'shared.versionControl.repositorySetup.clone.helper': 'Clone into this workspace.',
      'shared.versionControl.repositorySetup.clone.disabledHelper': 'Clone disabled.',
      'shared.versionControl.repositorySetup.clone.actions.loadBranches': 'Load branches',
      'shared.versionControl.repositorySetup.clone.actions.loadingBranches': 'Loading...',
      'shared.versionControl.repositorySetup.clone.actions.cloning': 'Cloning...',
      'shared.versionControl.repositorySetup.sshKeyRequired.title': 'SSH key required',
      'shared.versionControl.repositorySetup.sshKeyRequired.description': 'Configure an SSH key in System Settings.',
      'shared.versionControl.repositorySetup.sshKeyRequired.action': 'Open System Settings',
      'workspace.versionControl.toasts.initializeSuccess.title': 'Git repository initialized',
      'workspace.versionControl.toasts.cloneSuccess.title': 'Repository cloned',
    }[key] ?? key),
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('../../../integrations/version-control/workspaceVersionControlSession', () => {
  return {
    useWorkspaceVersionControlSession: () => ({
      changes: {
        useStatusQuery: () => ({ data: { currentBranch: 'main' } }),
      },
      history: {
        useBranchesQuery: () => ({
          data: [{
            name: 'main',
            displayName: 'main',
            kind: 'local',
            isCurrent: true,
            upstream: null,
            checkedOutTarget: null,
            ahead: 0,
            behind: 0,
            capabilities: {
              switch: { allowed: true },
              rename: { allowed: true },
              delete: { allowed: false },
            },
          }],
        }),
        useCommitsInfiniteQuery: vi.fn((params: {
          branch?: string;
          search?: string;
          limit?: number;
        }) => {
          commitsQueryMock.lastBranch = params.branch;
          commitsQueryMock.lastSearch = params.search;
          commitsQueryMock.lastLimit = params.limit;
          return commitsQueryMock;
        }),
        useCommitFilesQuery: () => filesQueryMock,
        useRevertCommitMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
      },
      remote: {
        useCloneRepositoryMutation: () => cloneRepositoryMutationMock,
        useInitializeRepositoryMutation: () => initializeRepositoryMutationMock,
        useRemoteBranchesMutation: () => ({
          mutateAsync: vi.fn().mockResolvedValue({
            branches: ['develop'],
            defaultBranch: 'develop',
          }),
        }),
        useRepositoryQuery: () => ({
          data: {
            isGitRepo: false,
            hasOrigin: false,
            hasLocalContent: false,
            canCloneSafely: true,
            canInitSafely: true,
          },
        }),
      },
    }),
  };
});

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: () => ({
    getVirtualItems: () => [],
    getTotalSize: () => 0,
    measureElement: vi.fn(),
  }),
}));

vi.mock('./GitContextSelector', () => ({
  GitContextSelector: () => null,
}));

describe('CommitHistoryPanel', () => {
  beforeEach(() => {
    commitsQueryMock.data = { pages: [{ items: [] }] };
    commitsQueryMock.error = null;
    commitsQueryMock.lastBranch = undefined;
    commitsQueryMock.lastSearch = undefined;
    commitsQueryMock.lastLimit = undefined;
    filesQueryMock.error = null;
    initializeRepositoryMutationMock.mutateAsync.mockReset();
    initializeRepositoryMutationMock.mutateAsync.mockResolvedValue({});
    initializeRepositoryMutationMock.isPending = false;
    cloneRepositoryMutationMock.mutateAsync.mockReset();
    cloneRepositoryMutationMock.mutateAsync.mockResolvedValue({});
    cloneRepositoryMutationMock.isPending = false;
    toastMock.mockReset();
  });

  it('initializes Git from the non-git empty state', async () => {
    const user = userEvent.setup();
    commitsQueryMock.error = new ApiError('repository not initialized', 404, 'repository_not_initialized');

    render(
      <QueryClientProvider client={new QueryClient()}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    expect(screen.getByText('Version control is not set up')).toBeInTheDocument();
    expect(screen.getByText('Initialize a repository or clone an existing one.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Initialize Git' }));
    await user.click(screen.getAllByRole('button', { name: 'Initialize Git' }).at(-1)!);
    expect(initializeRepositoryMutationMock.mutateAsync).toHaveBeenCalledWith({ defaultBranch: 'main' });
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Git repository initialized',
      variant: 'success',
    }));
  });

  it('opens a dialog and clones a repository from the non-git empty state', async () => {
    const user = userEvent.setup();
    commitsQueryMock.error = new ApiError('repository not initialized', 404, 'repository_not_initialized');

    render(
      <QueryClientProvider client={new QueryClient()}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Clone Repository' }));
    await user.type(
      screen.getByLabelText('Repository URL'),
      'https://example.com/team/repository.git',
    );
    await user.click(screen.getByRole('button', { name: 'Load branches' }));
    expect(await screen.findByRole('combobox', { name: 'Branch' })).toHaveTextContent('develop');
    await user.click(screen.getByRole('button', { name: 'Clone Repository' }));

    expect(cloneRepositoryMutationMock.mutateAsync).toHaveBeenCalledWith({
      remoteUrl: 'https://example.com/team/repository.git',
      branch: 'develop',
    });
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Repository cloned',
      variant: 'success',
    }));
  });

  it('guides SSH clone users without a configured key to System Settings', async () => {
    const user = userEvent.setup();
    commitsQueryMock.error = new ApiError('repository not initialized', 404, 'repository_not_initialized');
    cloneRepositoryMutationMock.mutateAsync.mockRejectedValueOnce(new ApiError(
      'SSH key required',
      409,
      'VC_SSH_KEY_REQUIRED',
    ));

    render(
      <QueryClientProvider client={new QueryClient()}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Clone Repository' }));
    await user.type(
      screen.getByLabelText('Repository URL'),
      'git@example.com:team/repository.git',
    );
    await user.click(screen.getByRole('button', { name: 'Load branches' }));
    await user.click(screen.getByRole('button', { name: 'Clone Repository' }));

    expect(await screen.findByText('SSH key required')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open System Settings' }))
      .toHaveAttribute('href', '/settings');
  });

  it('passes search and branch filters to the commit history query', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText('Search commits'), 'fix');
    await user.click(screen.getByRole('button', { name: 'Branch: All branches' }));
    await user.click(screen.getByRole('menuitem', { name: 'main' }));

    expect(commitsQueryMock.lastSearch).toBe('fix');
    expect(commitsQueryMock.lastBranch).toBe('main');
  });

  it('requests commits with a numeric page limit the runtime accepts', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    expect(commitsQueryMock.lastLimit).toBe(20);
  });
});
