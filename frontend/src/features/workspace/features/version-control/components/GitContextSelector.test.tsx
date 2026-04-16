import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GitContextSelector } from './GitContextSelector';

const { dispatchMock, workspaceStateMock } = vi.hoisted(() => ({
  dispatchMock: vi.fn(),
  workspaceStateMock: {
    versionControl: {
      selectedGitContextId: null as string | null,
    },
  },
}));

let currentLocale = 'zh-TW';

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
      if (currentLocale === 'en') {
        if (key === 'workspace.versionControl.gitContext.label') return 'Worktree';
        if (key === 'workspace.versionControl.gitContext.ariaLabel') return 'Worktree';
        if (key === 'workspace.versionControl.gitContext.option.primary') return `Primary worktree · ${name}`;
        if (key === 'workspace.versionControl.gitContext.option.worktree') return `Worktree · ${name}`;
      }

      if (key === 'workspace.versionControl.gitContext.label') return '工作樹';
      if (key === 'workspace.versionControl.gitContext.ariaLabel') return '工作樹';
      if (key === 'workspace.versionControl.gitContext.option.primary') return `主要工作樹 · ${name}`;
      if (key === 'workspace.versionControl.gitContext.option.worktree') return `工作樹 · ${name}`;
      return key;
    },
  }),
}));

vi.mock('../hooks/useVersionControlQueries', () => ({
  useGitContextsQuery: () => ({
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
  }),
}));

describe('GitContextSelector', () => {
  beforeEach(() => {
    dispatchMock.mockClear();
    workspaceStateMock.versionControl.selectedGitContextId = null;
    currentLocale = 'zh-TW';
  });

  it('selects the active Git context when no context is chosen yet', () => {
    render(<GitContextSelector />);

    expect(dispatchMock).toHaveBeenCalledWith({ type: 'SET_SELECTED_GIT_CONTEXT', payload: 'primary' });
    expect(screen.getByRole('combobox', { name: '工作樹' })).toHaveValue('primary');
    expect(screen.getByText('工作樹')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '主要工作樹 · main' })).toBeInTheDocument();
  });

  it('dispatches the selected worktree context', async () => {
    const user = userEvent.setup();
    workspaceStateMock.versionControl.selectedGitContextId = 'primary';

    render(<GitContextSelector />);

    await user.selectOptions(screen.getByRole('combobox', { name: '工作樹' }), 'worktree:feature-auth');

    expect(dispatchMock).toHaveBeenCalledWith({
      type: 'SET_SELECTED_GIT_CONTEXT',
      payload: 'worktree:feature-auth',
    });
  });

  it('renders English labels when locale is en', () => {
    currentLocale = 'en';
    render(<GitContextSelector />);

    expect(screen.getByRole('combobox', { name: 'Worktree' })).toHaveValue('primary');
    expect(screen.getByText('Worktree')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Primary worktree · main' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Worktree · feature-auth' })).toBeInTheDocument();
  });
});
