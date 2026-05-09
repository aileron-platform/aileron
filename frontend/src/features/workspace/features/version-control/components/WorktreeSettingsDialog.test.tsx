import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '@/shared/api/apiClient';
import { WorktreeSettingsDialog } from './WorktreeSettingsDialog';

const toastMock = vi.fn();
const onOpenChangeMock = vi.fn();
const onSavedMock = vi.fn();

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const translations: Record<string, string> = {
  'workspace.versionControl.worktree.dialog.title': 'Worktree settings',
  'workspace.versionControl.worktree.dialog.description': 'Choose a directory.',
  'workspace.versionControl.worktree.dialog.fieldLabel': 'Directory path',
  'workspace.versionControl.worktree.dialog.helper': 'Use a relative path.',
  'workspace.versionControl.worktree.dialog.cancel': 'Cancel',
  'workspace.versionControl.worktree.dialog.save': 'Save',
  'workspace.versionControl.worktree.dialog.saving': 'Saving...',
  'workspace.versionControl.worktree.validation.empty': 'Enter a directory path.',
  'workspace.versionControl.worktree.validation.separator': 'Use a relative directory path without leading, trailing, or empty path segments.',
  'workspace.versionControl.worktree.validation.parentTraversal': 'Directory paths cannot contain parent path segments.',
  'workspace.versionControl.worktree.validation.tooLong': 'Directory paths must be 64 characters or fewer.',
  'workspace.versionControl.worktree.toast.loadFailed.title': 'Unable to load worktree settings',
  'workspace.versionControl.worktree.toast.loadFailed.description': 'Try opening the dialog again.',
  'workspace.versionControl.worktree.toast.saveSuccess.title': 'Worktree settings saved',
  'workspace.versionControl.worktree.toast.saveSuccess.description': 'The runtime will sync the .gitignore managed block.',
  'workspace.versionControl.worktree.toast.saveFailed.title': 'Unable to save worktree settings',
  'workspace.versionControl.worktree.toast.saveFailed.description': 'Review the value and try again.',
};

const tMock = vi.fn((key: string) => translations[key] ?? key);

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

describe('WorktreeSettingsDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue({ id: 'ws-1', name: 'Workspace', worktreeSubdir: 'worktree' });
    vi.mocked(apiClient.put).mockResolvedValue({ id: 'ws-1', name: 'Workspace', worktreeSubdir: 'branches' });
  });

  it('renders the current worktree subdirectory', async () => {
    render(
      <WorktreeSettingsDialog
        open
        workspaceId="ws-1"
        onOpenChange={onOpenChangeMock}
      />
    );

    expect(await screen.findByDisplayValue('worktree')).toBeInTheDocument();
  });

  it.each([
    ['/', 'Use a relative directory path without leading, trailing, or empty path segments.'],
    ['branches//team-a', 'Use a relative directory path without leading, trailing, or empty path segments.'],
    ['..', 'Directory paths cannot contain parent path segments.'],
    ['x'.repeat(65), 'Directory paths must be 64 characters or fewer.'],
  ])('surfaces validation errors for invalid value %s', async (value, message) => {
    const user = userEvent.setup();
    render(
      <WorktreeSettingsDialog
        open
        workspaceId="ws-1"
        onOpenChange={onOpenChangeMock}
      />
    );

    const input = await screen.findByDisplayValue('worktree');
    await user.clear(input);
    await user.type(input, value);

    expect(screen.getByText(message)).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it('submits worktreeSubdir and closes only after success', async () => {
    const user = userEvent.setup();
    render(
      <WorktreeSettingsDialog
        open
        workspaceId="ws-1"
        onOpenChange={onOpenChangeMock}
        onSaved={onSavedMock}
      />
    );

    const input = await screen.findByDisplayValue('worktree');
    await user.clear(input);
    await user.type(input, 'branches');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/workspaces/ws-1', { worktreeSubdir: 'branches' });
    });
    expect(toastMock).toHaveBeenCalledWith({
      title: 'Worktree settings saved',
      description: 'The runtime will sync the .gitignore managed block.',
    });
    expect(onSavedMock).toHaveBeenCalled();
    expect(onOpenChangeMock).toHaveBeenCalledWith(false);
  });

  it('allows nested relative worktree subdirectory paths', async () => {
    const user = userEvent.setup();
    render(
      <WorktreeSettingsDialog
        open
        workspaceId="ws-1"
        onOpenChange={onOpenChangeMock}
        onSaved={onSavedMock}
      />
    );

    const input = await screen.findByDisplayValue('worktree');
    await user.clear(input);
    await user.type(input, 'branches/team-a');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/workspaces/ws-1', { worktreeSubdir: 'branches/team-a' });
    });
  });

  it('keeps the dialog open on failed save', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.put).mockRejectedValueOnce(new Error('failed'));
    render(
      <WorktreeSettingsDialog
        open
        workspaceId="ws-1"
        onOpenChange={onOpenChangeMock}
      />
    );

    const input = await screen.findByDisplayValue('worktree');
    await user.clear(input);
    await user.type(input, 'branches');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith({
        title: 'Unable to save worktree settings',
        description: 'Review the value and try again.',
        variant: 'destructive',
      });
    });
    expect(onOpenChangeMock).not.toHaveBeenCalledWith(false);
  });
});
