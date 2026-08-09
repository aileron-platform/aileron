import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { HookDialog } from './HookDialog';
import {
  createHookDialogTestLabels,
  createHookDialogTestOptions,
} from './__tests__/HookDialog.fixtures';

const labels = createHookDialogTestLabels();
const options = createHookDialogTestOptions();

describe('HookDialog behavior', () => {
  it('submits hook payload without template fields', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <HookDialog
        provider="claude-code"
        open
        mode="create"
        hook={null}
        labels={labels}
        options={options}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.clear(screen.getByPlaceholderText('Pattern placeholder'));
    await user.type(screen.getByPlaceholderText('Pattern placeholder'), 'Write');
    await user.type(screen.getByPlaceholderText('Command placeholder'), 'echo write');
    await user.click(screen.getByRole('button', { name: 'Create hook' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        scope: 'project',
        eventName: 'SessionStart',
        matchers: [
          {
            matcher: 'Write',
            hooks: [expect.objectContaining({
              type: 'command',
              command: 'echo write',
              timeout: 600,
              shell: 'bash',
              async: false,
              asyncRewake: false,
            })],
          },
        ],
      }));
    });
  });

  it('keeps action metadata hidden unless enabled by the tool capability', () => {
    render(
      <HookDialog
        provider="claude-code"
        open
        mode="create"
        hook={null}
        labels={labels}
        options={options}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByPlaceholderText('Name placeholder')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Description placeholder')).not.toBeInTheDocument();
  });

  it('blocks duplicate event and scope during creation', () => {
    render(
      <HookDialog
        provider="claude-code"
        open
        mode="create"
        hook={null}
        existingHooks={[
          {
            id: 'project:SessionStart',
            scope: 'project',
            eventName: 'SessionStart',
            matchers: [],
          },
        ]}
        labels={labels}
        options={options}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText('Duplicate event')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create hook' })).toBeDisabled();
  });

  it('keeps invalid action feedback silent when the feature option is disabled', () => {
    render(
      <HookDialog
        provider="claude-code"
        open
        mode="create"
        hook={null}
        labels={labels}
        options={options}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByText('A valid action is required.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create hook' })).toBeEnabled();
  });

  it('shows invalid action feedback and disables submit when the feature option is enabled', () => {
    render(
      <HookDialog
        provider="claude-code"
        open
        mode="create"
        hook={null}
        labels={labels}
        options={{
          ...options,
          showInvalidActionWarning: true,
        }}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText('A valid action is required.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create hook' })).toBeDisabled();
  });

  it('calls the close handler from cancel', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <HookDialog
        provider="claude-code"
        open
        mode="create"
        hook={null}
        labels={labels}
        options={options}
        onClose={onClose}
        onSubmit={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onClose).toHaveBeenCalled();
  });

  it('hides the scope selector when only one scope is allowed', () => {
    render(
      <HookDialog
        open
        mode="create"
        provider="claude-code"
        hook={null}
        labels={labels}
        options={{
          ...options,
          scopes: [{ value: 'project', label: 'Project' }],
        }}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByText('Scope')).not.toBeInTheDocument();
  });
});
