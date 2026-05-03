import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { WorkspaceHookDialog } from './WorkspaceHookDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'workspace.agentSettings.common.hooks.dialog.title.create': 'Add hook',
        'workspace.agentSettings.common.hooks.dialog.title.edit': 'Edit hook',
        'workspace.agentSettings.common.hooks.dialog.description': 'Configure hook.',
        'workspace.agentSettings.common.hooks.dialog.scope.label': 'Scope',
        'workspace.agentSettings.common.hooks.dialog.scope.labelWithAsterisk': 'Scope',
        'workspace.agentSettings.common.hooks.dialog.scope.placeholder': 'Choose scope',
        'workspace.agentSettings.common.hooks.dialog.scope.options.project': 'Project',
        'workspace.agentSettings.common.hooks.dialog.scope.options.user': 'User',
        'workspace.agentSettings.common.hooks.dialog.scope.options.local': 'Local',
        'workspace.agentSettings.common.hooks.dialog.event.label': 'Event type',
        'workspace.agentSettings.common.hooks.dialog.event.placeholder': 'Choose event',
        'workspace.agentSettings.common.hooks.events.PreToolUse.option': 'PreToolUse',
        'workspace.agentSettings.common.hooks.events.PostToolUse.option': 'PostToolUse',
        'workspace.agentSettings.common.hooks.events.UserPromptSubmit.option': 'UserPromptSubmit',
        'workspace.agentSettings.common.hooks.events.Notification.option': 'Notification',
        'workspace.agentSettings.common.hooks.events.Stop.option': 'Stop',
        'workspace.agentSettings.common.hooks.events.SubagentStop.option': 'SubagentStop',
        'workspace.agentSettings.common.hooks.events.PreCompact.option': 'PreCompact',
        'workspace.agentSettings.common.hooks.events.SessionStart.option': 'SessionStart',
        'workspace.agentSettings.common.hooks.events.SessionEnd.option': 'SessionEnd',
        'workspace.agentSettings.common.hooks.dialog.matcher.sectionTitle': 'Matchers',
        'workspace.agentSettings.common.hooks.dialog.matcher.add': 'Add matcher',
        'workspace.agentSettings.common.hooks.dialog.matcher.patternLabel': 'Pattern',
        'workspace.agentSettings.common.hooks.dialog.matcher.patternPlaceholder': 'Pattern placeholder',
        'workspace.agentSettings.common.hooks.dialog.matcher.helper.intro': 'Pattern intro',
        'workspace.agentSettings.common.hooks.dialog.matcher.helper.simple': 'Pattern simple',
        'workspace.agentSettings.common.hooks.dialog.matcher.helper.regex': 'Pattern regex',
        'workspace.agentSettings.common.hooks.dialog.matcher.helper.wildcard': 'Pattern wildcard',
        'workspace.agentSettings.common.hooks.dialog.matcher.remove': 'Remove matcher',
        'workspace.agentSettings.common.hooks.dialog.execution.sectionTitle': 'Executions',
        'workspace.agentSettings.common.hooks.dialog.execution.add': 'Add execution',
        'workspace.agentSettings.common.hooks.dialog.execution.nameLabel': 'Hook name',
        'workspace.agentSettings.common.hooks.dialog.execution.namePlaceholder': 'Name placeholder',
        'workspace.agentSettings.common.hooks.dialog.execution.nameHelp': 'Name help',
        'workspace.agentSettings.common.hooks.dialog.execution.descriptionLabel': 'Description',
        'workspace.agentSettings.common.hooks.dialog.execution.descriptionPlaceholder': 'Description placeholder',
        'workspace.agentSettings.common.hooks.dialog.execution.descriptionHelp': 'Description help',
        'workspace.agentSettings.common.hooks.dialog.execution.timeoutLabel': 'Timeout',
        'workspace.agentSettings.common.hooks.dialog.execution.timeoutPlaceholder': '30',
        'workspace.agentSettings.common.hooks.dialog.execution.timeoutHelp': 'Timeout help',
        'workspace.agentSettings.common.hooks.dialog.execution.commandLabel': 'Command',
        'workspace.agentSettings.common.hooks.dialog.execution.commandPlaceholder': 'Command placeholder',
        'workspace.agentSettings.common.hooks.dialog.execution.commandHelp': 'Command help',
        'workspace.agentSettings.common.hooks.dialog.execution.statusMessageLabel': 'Status message',
        'workspace.agentSettings.common.hooks.dialog.execution.statusMessagePlaceholder': 'Status placeholder',
        'workspace.agentSettings.common.hooks.dialog.execution.statusMessageHelp': 'Status help',
        'workspace.agentSettings.common.hooks.dialog.execution.remove': 'Remove execution',
        'workspace.agentSettings.common.hooks.dialog.actions.cancel': 'Cancel',
        'workspace.agentSettings.common.hooks.dialog.actions.create': 'Create hook',
        'workspace.agentSettings.common.hooks.dialog.actions.save': 'Save changes',
        'workspace.agentSettings.common.hooks.dialog.validation.duplicateEventWarning': 'Duplicate event',
        'workspace.agentSettings.common.hooks.dialog.validation.duplicateEventSuggestion': 'Edit existing hook.',
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

  it('keeps action metadata hidden unless enabled by the tool capability', () => {
    render(
      <WorkspaceHookDialog
        open
        mode="create"
        hook={null}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.queryByPlaceholderText('Name placeholder')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Description placeholder')).not.toBeInTheDocument();
  });

  it('submits Gemini hook action name and description when metadata is enabled', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <WorkspaceHookDialog
        open
        mode="create"
        hook={null}
        supportsActionMetadata
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.clear(screen.getByPlaceholderText('Pattern placeholder'));
    await user.type(screen.getByPlaceholderText('Pattern placeholder'), 'Write');
    await user.type(screen.getByPlaceholderText('Name placeholder'), 'security-check');
    await user.type(screen.getByPlaceholderText('Description placeholder'), 'Check commands before execution');
    await user.type(screen.getByPlaceholderText('Command placeholder'), 'echo write');
    await user.click(screen.getByRole('button', { name: 'Create hook' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        matchers: [
          {
            matcher: 'Write',
            hooks: [
              {
                type: 'command',
                name: 'security-check',
                description: 'Check commands before execution',
                command: 'echo write',
                timeout: 30,
              },
            ],
          },
        ],
      }));
    });
  });

  it('preserves and clears Gemini hook action metadata in edit mode', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <WorkspaceHookDialog
        open
        mode="edit"
        hook={{
          id: 'project:PreToolUse',
          scope: 'project',
          eventName: 'PreToolUse',
          matchers: [
            {
              matcher: 'Write',
              hooks: [
                {
                  type: 'command',
                  name: 'security-check',
                  description: 'Check commands before execution',
                  command: 'echo write',
                  timeout: 30,
                },
              ],
            },
          ],
        }}
        supportsActionMetadata
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByDisplayValue('security-check')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Check commands before execution')).toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText('Name placeholder'));
    await user.clear(screen.getByPlaceholderText('Description placeholder'));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
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
