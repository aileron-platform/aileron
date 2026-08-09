import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/shared/api/apiClient';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GitContextSelector } from './GitContextSelector';

const { dispatchMock, workspaceStateMock, contextsQueryMock } = vi.hoisted(() => ({
  dispatchMock: vi.fn(),
  workspaceStateMock: {
    versionControl: {
      selectedGitContextId: null as string | null,
    },
  },
  contextsQueryMock: {
    data: {
      activeContextId: 'primary',
      contexts: [
        {
          id: 'primary',
          kind: 'primary',
          displayName: 'main',
          repoPath: '/workspace',
          branch: 'main',
          detached: false,
          headSha: 'abc1234',
          locked: false,
          prunable: false,
        },
        {
          id: 'worktree:feature-auth',
          kind: 'worktree',
          displayName: 'feature-auth',
          repoPath: '/workspace/.worktrees/feature-auth',
          branch: 'feature-auth',
          detached: false,
          headSha: 'def5678',
          locked: false,
          prunable: false,
        },
      ],
    },
    isLoading: false,
    error: null as unknown,
  },
}));

let currentLocale = 'en';

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: workspaceStateMock,
    dispatch: dispatchMock,
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime',
      workspaceId: 'ws-contexts',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      const name = params?.name ?? '';
      if (key === 'workspace.versionControl.gitContext.label') return 'Worktree';
      if (key === 'workspace.versionControl.gitContext.ariaLabel') return 'Worktree';
      if (key === 'workspace.versionControl.gitContext.option.primary') return `Primary worktree ${name}`;
      if (key === 'workspace.versionControl.gitContext.option.worktree') return `Worktree ${name}`;
      return key;
    },
  }),
}));

vi.mock('../../../integrations/version-control/workspaceVersionControlSession', () => {
  return {
    useWorkspaceVersionControlSession: () => ({
      history: {
        useContextsQuery: () => contextsQueryMock,
      },
    }),
  };
});

describe('GitContextSelector', () => {
  beforeEach(() => {
    dispatchMock.mockClear();
    workspaceStateMock.versionControl.selectedGitContextId = null;
    currentLocale = 'en';
    contextsQueryMock.data = {
      activeContextId: 'primary',
      contexts: [
        {
          id: 'primary',
          kind: 'primary',
          displayName: 'main',
          repoPath: '/workspace',
          branch: 'main',
          detached: false,
          headSha: 'abc1234',
          locked: false,
          prunable: false,
        },
        {
          id: 'worktree:feature-auth',
          kind: 'worktree',
          displayName: 'feature-auth',
          repoPath: '/workspace/.worktrees/feature-auth',
          branch: 'feature-auth',
          detached: false,
          headSha: 'def5678',
          locked: false,
          prunable: false,
        },
      ],
    };
    contextsQueryMock.isLoading = false;
    contextsQueryMock.error = null;
  });

  it('selects the active Git context when no context is chosen yet', () => {
    render(<GitContextSelector />);

    expect(dispatchMock).toHaveBeenCalledWith({ type: 'SET_SELECTED_GIT_CONTEXT', payload: 'primary' });
    expect(screen.getByRole('combobox', { name: 'Worktree' })).toHaveValue('primary');
    expect(screen.getByRole('option', { name: 'Primary worktree main' })).toBeInTheDocument();
  });

  it('dispatches the selected worktree context', async () => {
    const user = userEvent.setup();
    workspaceStateMock.versionControl.selectedGitContextId = 'primary';

    render(<GitContextSelector />);

    await user.selectOptions(screen.getByRole('combobox', { name: 'Worktree' }), 'worktree:feature-auth');

    expect(dispatchMock).toHaveBeenCalledWith({
      type: 'SET_SELECTED_GIT_CONTEXT',
      payload: 'worktree:feature-auth',
    });
  });

  it('clears the selected context and hides the selector for non-git workspaces', () => {
    workspaceStateMock.versionControl.selectedGitContextId = 'primary';
    contextsQueryMock.data = undefined;
    contextsQueryMock.error = new ApiError(
      'Workspace is not a git repository',
      400,
      'repository_not_initialized',
    );

    render(<GitContextSelector />);

    expect(dispatchMock).toHaveBeenCalledWith({ type: 'SET_SELECTED_GIT_CONTEXT', payload: null });
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });
});
