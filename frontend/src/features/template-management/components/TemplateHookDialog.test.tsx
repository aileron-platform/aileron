import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { TemplateHookDialog } from './TemplateHookDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'common.cancel': 'Cancel',
        'common.remove': 'Remove',
        'template.editor.hooks.dialog.title.create': 'Add hook',
        'template.editor.hooks.dialog.title.edit': 'Edit hook',
        'template.editor.hooks.dialog.description': 'Configure template hook.',
        'template.editor.hooks.dialog.fields.event.label': 'Event type',
        'template.editor.hooks.dialog.fields.event.placeholder': 'Choose event',
        'template.editor.hooks.events.preToolUse.label': 'PreToolUse',
        'template.editor.hooks.events.preToolUse.description': 'Before tool use',
        'template.editor.hooks.events.postToolUse.label': 'PostToolUse',
        'template.editor.hooks.events.postToolUse.description': 'After tool use',
        'template.editor.hooks.events.userPromptSubmit.label': 'UserPromptSubmit',
        'template.editor.hooks.events.userPromptSubmit.description': 'Prompt submitted',
        'template.editor.hooks.events.notification.label': 'Notification',
        'template.editor.hooks.events.notification.description': 'Notification',
        'template.editor.hooks.events.stop.label': 'Stop',
        'template.editor.hooks.events.stop.description': 'Stop',
        'template.editor.hooks.events.subagentStop.label': 'SubagentStop',
        'template.editor.hooks.events.subagentStop.description': 'Subagent stop',
        'template.editor.hooks.events.preCompact.label': 'PreCompact',
        'template.editor.hooks.events.preCompact.description': 'Pre compact',
        'template.editor.hooks.events.sessionStart.label': 'SessionStart',
        'template.editor.hooks.events.sessionStart.description': 'Session start',
        'template.editor.hooks.events.sessionEnd.label': 'SessionEnd',
        'template.editor.hooks.events.sessionEnd.description': 'Session end',
        'template.editor.hooks.dialog.matchers.title': 'Matchers',
        'template.editor.hooks.dialog.matchers.add': 'Add matcher',
        'template.editor.hooks.dialog.matchers.patternLabel': 'Pattern',
        'template.editor.hooks.dialog.matchers.patternPlaceholder': 'Pattern placeholder',
        'template.editor.hooks.dialog.matchers.patternHelp.overview': 'Pattern overview',
        'template.editor.hooks.dialog.matchers.patternHelp.literal': 'Literal pattern',
        'template.editor.hooks.dialog.matchers.patternHelp.regex': 'Regex pattern',
        'template.editor.hooks.dialog.matchers.patternHelp.wildcard': 'Wildcard pattern',
        'template.editor.hooks.dialog.executions.title': 'Executions',
        'template.editor.hooks.dialog.executions.add': 'Add execution',
        'template.editor.hooks.dialog.executions.timeoutLabel': 'Timeout',
        'template.editor.hooks.dialog.executions.timeoutPlaceholder': '30',
        'template.editor.hooks.dialog.executions.timeoutHelp': 'Timeout help',
        'template.editor.hooks.dialog.executions.commandLabel': 'Command',
        'template.editor.hooks.dialog.executions.commandPlaceholder': 'Command placeholder',
        'template.editor.hooks.dialog.executions.commandHelp': 'Command help',
        'template.editor.hooks.dialog.executions.remove': 'Remove execution',
        'template.editor.hooks.dialog.actions.create': 'Create hook',
        'template.editor.hooks.dialog.actions.save': 'Save changes',
        'template.editor.hooks.dialog.validation.duplicateEventWarning': 'Duplicate event',
        'template.editor.hooks.dialog.validation.duplicateEventSuggestion': 'Edit existing hook.',
      };
      return map[key] ?? key;
    },
  }),
}));

describe('TemplateHookDialog', () => {
  it('submits template hook payload and closes the dialog', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onSave = vi.fn();

    render(
      <TemplateHookDialog
        open
        onOpenChange={onOpenChange}
        onSave={onSave}
      />,
    );

    await user.clear(screen.getByPlaceholderText('Pattern placeholder'));
    await user.type(screen.getByPlaceholderText('Pattern placeholder'), 'Bash');
    await user.type(screen.getByPlaceholderText('Command placeholder'), 'echo bash');
    await user.click(screen.getByRole('button', { name: 'Create hook' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
        event: 'PreToolUse',
        matchers: [
          {
            matcher: 'Bash',
            hooks: [{ type: 'command', command: 'echo bash', timeout: 30 }],
          },
        ],
      }));
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('blocks duplicate template event during creation', () => {
    render(
      <TemplateHookDialog
        open
        existingHooks={[
          {
            localId: 'hook-1',
            event: 'PreToolUse',
            matchers: [],
          },
        ]}
        onOpenChange={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText('Duplicate event')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create hook' })).toBeDisabled();
  });
});
