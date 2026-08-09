import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { WorkspaceDeletionDialog } from './WorkspaceDeletionDialog';

const tMock = (key: string) => key;

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

describe('WorkspaceDeletionDialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('requires the complete current workspace name before confirming', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue(true);

    render(
      <WorkspaceDeletionDialog
        workspaceName="Workspace One"
        canDelete
        isDeleting={false}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    }));

    const confirmationInput = screen.getByRole('textbox');
    const confirmButton = screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.dialog.confirm',
    });
    expect(confirmButton).toBeDisabled();

    await user.type(confirmationInput, 'Workspace');
    expect(confirmButton).toBeDisabled();
    await user.type(confirmationInput, ' One');
    expect(confirmButton).toBeEnabled();

    await user.click(confirmButton);

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith('Workspace One');
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    });
  });

  it('keeps the dialog open when the delete request is rejected', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue(false);

    render(
      <WorkspaceDeletionDialog
        workspaceName="Workspace One"
        canDelete
        isDeleting={false}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    }));
    await user.type(screen.getByRole('textbox'), 'Workspace One');
    await user.click(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.dialog.confirm',
    }));

    expect(onConfirm).toHaveBeenCalledWith('Workspace One');
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });

  it('does not render a destructive entry when the name is unavailable or the actor is not the owner', () => {
    const { rerender } = render(
      <WorkspaceDeletionDialog
        workspaceName={null}
        canDelete
        isDeleting={false}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.queryByTestId('workspace-deletion-trigger')).not.toBeInTheDocument();

    rerender(
      <WorkspaceDeletionDialog
        workspaceName="Workspace One"
        canDelete={false}
        isDeleting={false}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('workspace-deletion-trigger')).not.toBeInTheDocument();
  });
});
