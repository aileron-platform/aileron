import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileChangesPanel } from './FileChangesPanel';

const {
  refreshVersionControlQueriesMock,
  onFileSelectMock,
  changesQueryMock,
  branchesQueryMock,
  statusQueryMock,
} = vi.hoisted(() => ({
  refreshVersionControlQueriesMock: vi.fn().mockResolvedValue(undefined),
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
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime',
      workspaceId: 'ws-refresh',
    },
  }),
}));

vi.mock('../hooks/useVersionControlQueries', () => ({
  useChangesQuery: () => changesQueryMock,
  useBranchesQuery: () => branchesQueryMock,
  useStatusQuery: () => statusQueryMock,
  useStageMutation: () => ({ mutateAsync: vi.fn() }),
  useUnstageMutation: () => ({ mutateAsync: vi.fn() }),
  useCommitMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDiscardMutation: () => ({ mutateAsync: vi.fn() }),
}));

vi.mock('../lib/queryClient', async () => {
  const actual = await vi.importActual<typeof import('../lib/queryClient')>('../lib/queryClient');
  return {
    ...actual,
    refreshVersionControlQueries: refreshVersionControlQueriesMock,
  };
});

describe('FileChangesPanel', () => {
  beforeEach(() => {
    refreshVersionControlQueriesMock.mockClear();
    onFileSelectMock.mockClear();
  });

  it('triggers coordinated version-control refresh from the changes header', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(refreshVersionControlQueriesMock).toHaveBeenCalledTimes(1);
    expect(refreshVersionControlQueriesMock).toHaveBeenCalledWith(
      queryClient,
      'ws-refresh',
      { includeBranches: true },
    );
  });

  it('keeps unstaged files visible while refresh is in flight', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    let resolveRefresh: (() => void) | null = null;
    refreshVersionControlQueriesMock.mockImplementationOnce(
      () => new Promise<void>((resolve) => {
        resolveRefresh = resolve;
      }),
    );

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
    expect(screen.getAllByText('draft.txt').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
    expect(screen.getAllByText('draft.txt').length).toBeGreaterThan(0);

    await act(async () => {
      resolveRefresh?.();
    });
  });
});
