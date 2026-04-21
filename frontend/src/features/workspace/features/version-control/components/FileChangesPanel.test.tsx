import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/shared/api/apiClient';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileChangesPanel } from './FileChangesPanel';

const {
  onFileSelectMock,
  changesQueryMock,
  branchesQueryMock,
  statusQueryMock,
} = vi.hoisted(() => ({
  onFileSelectMock: vi.fn(),
  changesQueryMock: {
    data: {
      staged: [],
      unstaged: [{ name: 'notes.md', path: 'notes.md', status: 'M', additions: 1, deletions: 0 }],
      untracked: [{ name: 'draft.txt', path: 'draft.txt', status: '?', additions: 0, deletions: 0 }],
      untrackedHasMore: false,
    },
    isLoading: false,
    isFetching: false,
    error: null,
  },
  branchesQueryMock: {
    data: [{ name: 'main', displayName: 'main', isActive: true }],
    isLoading: false,
    error: null,
  },
  statusQueryMock: {
    data: { branch: 'main' },
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) =>
      ({
        'workspace.versionControl.actions.refresh.label': 'Refresh',
        'workspace.versionControl.actions.refresh.tooltip': 'Refresh version control status',
        'workspace.versionControl.actions.menu.label': 'More actions',
        'workspace.versionControl.actions.branch.label': 'Branch',
        'workspace.versionControl.actions.pull.label': 'Pull',
        'workspace.versionControl.actions.push.label': 'Push',
        'workspace.versionControl.fileChanges.stagedTitle': 'Staged changes',
        'workspace.versionControl.fileChanges.unstagedTitle': 'Unstaged changes',
        'workspace.versionControl.fileChanges.unstageAllTooltip': 'Unstage all files',
        'workspace.versionControl.fileChanges.stageAllTooltip': 'Stage all files',
        'workspace.versionControl.fileChanges.loadingMore': 'Loading...',
        'workspace.versionControl.commitForm.placeholder': 'Commit message',
        'workspace.versionControl.commitForm.submit': 'Commit',
        'workspace.versionControl.commitForm.submitting': 'Committing...',
      }[key] ?? key),
  }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: {
      versionControl: {
        selectedGitContextId: 'primary',
      },
    },
    dispatch: vi.fn(),
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime',
      workspaceId: 'ws-refresh',
    },
  }),
}));

vi.mock('../hooks/useVersionControlQueries', () => ({
  useGitContextsQuery: () => ({
    data: {
      activeContextId: 'primary',
      contexts: [{ id: 'primary', kind: 'primary', displayName: 'main', repoPath: '/workspace', detached: false, locked: false, prunable: false }],
    },
    isLoading: false,
  }),
  useChangesQuery: () => changesQueryMock,
  useBranchesQuery: () => branchesQueryMock,
  useStatusQuery: () => statusQueryMock,
  useStageMutation: () => ({ mutateAsync: vi.fn() }),
  useUnstageMutation: () => ({ mutateAsync: vi.fn() }),
  useCommitMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDiscardMutation: () => ({ mutateAsync: vi.fn() }),
}));

describe('FileChangesPanel', () => {
  beforeEach(() => {
    onFileSelectMock.mockClear();
    changesQueryMock.error = null;
    branchesQueryMock.error = null;
  });

  it('renders branch and action controls in the changes header', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('Branch')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'main' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument();
  });

  it('keeps unstaged files visible in the panel', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
    expect(screen.getAllByText('draft.txt').length).toBeGreaterThan(0);
  });

  it('clears selected file state when the branch changes', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    const view = render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByText('notes.md')[0]);

    expect(onFileSelectMock).toHaveBeenCalledWith(
      expect.objectContaining({ path: 'notes.md' }),
    );

    branchesQueryMock.data = [{ name: 'feature-auth', displayName: 'feature-auth', isActive: true }];
    statusQueryMock.data = { branch: 'feature-auth' };

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(onFileSelectMock).toHaveBeenLastCalledWith(null);
  });

  it('renders a non-git empty state when the repository is not initialized', () => {
    const queryClient = new QueryClient();
    changesQueryMock.error = new ApiError(
      'Workspace is not a git repository',
      400,
      'VC_REPOSITORY_NOT_INITIALIZED',
    );

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('workspace.versionControl.errors.notInitialized.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.versionControl.errors.notInitialized.description')).toBeInTheDocument();
  });
});
