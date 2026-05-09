import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '@/shared/api/apiClient';
import { VersionControlView } from './VersionControlView';

const reloadMock = vi.fn();
const toggleSecondColumnMock = vi.fn();
const toastMock = vi.fn();

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const translations: Record<string, string> = {
  'workspace.versionControl.sidebar.title.changes': 'File changes',
  'workspace.versionControl.sidebar.title.history': 'Commit history',
  'workspace.versionControl.sidebar.toggle.expand': 'Expand sidebar',
  'workspace.versionControl.sidebar.toggle.collapse': 'Collapse sidebar',
  'workspace.versionControl.worktree.menu.moreActions': 'More actions',
  'workspace.versionControl.worktree.menu.group': 'Worktrees',
  'workspace.versionControl.worktree.menu.settings': 'Worktree settings...',
  'workspace.versionControl.worktree.menu.create': 'Create worktree...',
  'workspace.versionControl.worktree.menu.comingSoon': 'Coming soon',
  'workspace.versionControl.worktree.dialog.title': 'Worktree settings',
  'workspace.versionControl.worktree.dialog.description': 'Choose a directory.',
  'workspace.versionControl.worktree.dialog.fieldLabel': 'Directory name',
  'workspace.versionControl.worktree.dialog.helper': 'Use one directory.',
  'workspace.versionControl.worktree.dialog.cancel': 'Cancel',
  'workspace.versionControl.worktree.dialog.save': 'Save',
  'workspace.versionControl.worktree.dialog.saving': 'Saving...',
};

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => translations[key] ?? key,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspace: {
      versionControl: {
        subView: 'changes',
      },
    },
    workspaceRuntime: {
      workspaceId: 'ws-1',
      reload: reloadMock,
    },
    layout: {
      secondColumnCollapsed: false,
    },
    toggleSecondColumn: toggleSecondColumnMock,
  }),
}));

vi.mock('./FileChangesPanel', () => ({
  FileChangesPanel: () => <div data-testid="file-changes-panel" />,
}));

vi.mock('./CommitHistoryPanel', () => ({
  CommitHistoryPanel: () => <div data-testid="commit-history-panel" />,
}));

describe('VersionControlView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({ id: 'ws-1', name: 'Workspace', worktreeSubdir: 'worktree' });
  });

  it('opens the worktree actions dropdown', async () => {
    const user = userEvent.setup();
    render(<VersionControlView />);

    await user.click(screen.getByRole('button', { name: 'More actions' }));

    expect(screen.getByText('Worktrees')).toBeInTheDocument();
    expect(screen.getByText('Worktree settings...')).toBeInTheDocument();
    expect(screen.getByText('Create worktree...')).toHaveAttribute('aria-disabled', 'true');
  });

  it('mounts the settings dialog from the dropdown action', async () => {
    const user = userEvent.setup();
    render(<VersionControlView />);

    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByText('Worktree settings...'));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Worktree settings')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('worktree')).toBeInTheDocument();
  });
});
