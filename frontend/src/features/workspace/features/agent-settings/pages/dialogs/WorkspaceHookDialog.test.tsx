import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { WorkspaceHookDialog } from './WorkspaceHookDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'workspace.claudeCode.hooks.dialog.title.create': 'Add hook',
        'workspace.claudeCode.hooks.dialog.title.edit': 'Edit hook',
        'workspace.claudeCode.hooks.dialog.description': 'Configure hook.',
        'workspace.claudeCode.hooks.dialog.scope.label': 'Scope',
        'workspace.claudeCode.hooks.dialog.scope.labelWithAsterisk': 'Scope',
        'workspace.claudeCode.hooks.dialog.scope.placeholder': 'Choose scope',
        'workspace.claudeCode.hooks.dialog.scope.options.project': 'Project',
        'workspace.claudeCode.hooks.dialog.scope.options.user': 'User',
        'workspace.claudeCode.hooks.dialog.scope.options.local': 'Local',
        'workspace.claudeCode.hooks.dialog.event.label': 'Event type',
        'workspace.claudeCode.hooks.dialog.event.placeholder': 'Choose event',
        'workspace.claudeCode.hooks.events.PreToolUse.option': 'PreToolUse',
        'workspace.claudeCode.hooks.events.PostToolUse.option': 'PostToolUse',
        'workspace.claudeCode.hooks.events.UserPromptSubmit.option': 'UserPromptSubmit',
        'workspace.claudeCode.hooks.events.Notification.option': 'Notification',
        'workspace.claudeCode.hooks.events.Stop.option': 'Stop',
        'workspace.claudeCode.hooks.events.SubagentStop.option': 'SubagentStop',
        'workspace.claudeCode.hooks.events.PreCompact.option': 'PreCompact',
        'workspace.claudeCode.hooks.events.SessionStart.option': 'SessionStart',
        'workspace.claudeCode.hooks.events.SessionEnd.option': 'SessionEnd',
        'workspace.claudeCode.hooks.dialog.matcher.sectionTitle': 'Matchers',
        'workspace.claudeCode.hooks.dialog.matcher.add': 'Add matcher',
        'workspace.claudeCode.hooks.dialog.matcher.patternLabel': 'Pattern',
        'workspace.claudeCode.hooks.dialog.matcher.patternPlaceholder': 'Pattern placeholder',
        'workspace.claudeCode.hooks.dialog.matcher.helper.intro': 'Pattern intro',
        'workspace.claudeCode.hooks.dialog.matcher.helper.simple': 'Pattern simple',
        'workspace.claudeCode.hooks.dialog.matcher.helper.regex': 'Pattern regex',
        'workspace.claudeCode.hooks.dialog.matcher.helper.wildcard': 'Pattern wildcard',
        'workspace.claudeCode.hooks.dialog.matcher.remove': 'Remove matcher',
        'workspace.claudeCode.hooks.dialog.execution.sectionTitle': 'Executions',
        'workspace.claudeCode.hooks.dialog.execution.add': 'Add execution',
        'workspace.claudeCode.hooks.dialog.execution.timeoutLabel': 'Timeout',
        'workspace.claudeCode.hooks.dialog.execution.timeoutPlaceholder': '30',
        'workspace.claudeCode.hooks.dialog.execution.timeoutHelp': 'Timeout help',
        'workspace.claudeCode.hooks.dialog.execution.commandLabel': 'Command',
        'workspace.claudeCode.hooks.dialog.execution.commandPlaceholder': 'Command placeholder',
        'workspace.claudeCode.hooks.dialog.execution.commandHelp': 'Command help',
        'workspace.claudeCode.hooks.dialog.execution.remove': 'Remove execution',
        'workspace.claudeCode.hooks.dialog.actions.cancel': 'Cancel',
        'workspace.claudeCode.hooks.dialog.actions.create': 'Create hook',
        'workspace.claudeCode.hooks.dialog.actions.save': 'Save changes',
        'workspace.claudeCode.hooks.dialog.validation.duplicateEventWarning': 'Duplicate event',
        'workspace.claudeCode.hooks.dialog.validation.duplicateEventSuggestion': 'Edit existing hook.',
      };
      return map[key] ?? key;
    },
  }),
}));

describe('WorkspaceHookDialog', () => {
  it('submits workspace hook payload without template fields', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <WorkspaceHookDialog
        open
        mode="create"
        hook={null}
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
        eventName: 'PreToolUse',
        matchers: [
          {
            matcher: 'Write',
            hooks: [{ type: 'command', command: 'echo write', timeout: 30 }],
          },
        ],
      }));
    });
  });

  it('blocks duplicate workspace event and scope during creation', () => {
    render(
      <WorkspaceHookDialog
        open
        mode="create"
        hook={null}
        existingHooks={[
          {
            id: 'project:PreToolUse',
            scope: 'project',
            eventName: 'PreToolUse',
            matchers: [],
          },
        ]}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText('Duplicate event')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create hook' })).toBeDisabled();
  });

  it('calls the workspace close handler from cancel', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <WorkspaceHookDialog
        open
        mode="create"
        hook={null}
        onClose={onClose}
        onSubmit={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onClose).toHaveBeenCalled();
  });
});
