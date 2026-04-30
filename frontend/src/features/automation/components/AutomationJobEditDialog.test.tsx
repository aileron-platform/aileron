import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { AutomationJobEditDialog } from './AutomationJobEditDialog';
import type { AutomationJob, AutomationJobUpdateInput } from '@/features/automation/types';
import type { SlashCommandItem } from '@/shared/types/slashCommands';

const { tMock } = vi.hoisted(() => ({
  tMock: (key: string) =>
    ({
      'automation.edit.title': 'Edit scheduled task definition',
      'automation.edit.subtitle': 'Update dispatch configuration',
      'automation.edit.actions.saving': 'Saving...',
      'automation.edit.actions.submit': 'Save definition',
      'automation.form.fields.name.label': 'Definition name',
      'automation.form.fields.name.placeholder': 'Definition name',
      'automation.form.fields.workspace.label': 'Target workspace',
      'automation.form.fields.workspace.placeholder': 'Select workspace',
      'automation.form.fields.workspace.accessSource.owned': 'Owned',
      'automation.form.fields.workspace.accessSource.shared': 'Shared',
      'automation.form.fields.description.label': 'Description',
      'automation.form.fields.description.placeholder': 'Description',
      'automation.form.fields.prompt.label': 'Prompt',
      'automation.form.fields.prompt.placeholder': 'Prompt',
      'automation.form.fields.prompt.selectCommand': 'Choose command',
      'automation.form.fields.trigger.label': 'Trigger type',
      'automation.form.fields.status.label': 'Status',
      'automation.form.fields.schedule.label': 'Job configuration',
      'automation.form.fields.schedule.placeholder': 'Cron expression',
      'automation.form.fields.schedule.timezoneHelper': 'Uses system timezone.',
      'automation.form.fields.tags.label': 'Tags',
      'automation.form.fields.tags.placeholder': 'Add tag',
      'automation.form.fields.tags.suggestions': 'Suggestions',
      'automation.form.trigger.cron': 'Cron schedule',
      'automation.form.trigger.interval': 'Interval',
      'automation.form.trigger.manual': 'Manual',
      'automation.form.trigger.webhook': 'Webhook',
      'automation.form.status.active': 'Active',
      'automation.form.status.paused': 'Paused',
      'automation.form.status.draft': 'Draft',
      'automation.slashDialog.title': 'Select slash command',
      'automation.slashDialog.description': 'Pick a command',
      'automation.slashDialog.searchPlaceholder': 'Search commands',
      'automation.slashDialog.empty': 'No commands',
      'automation.slashDialog.scope.all': 'All',
      'automation.slashDialog.scope.project': 'Project',
      'automation.slashDialog.scope.user': 'User',
      'common.cancel': 'Cancel',
    }[key] ?? key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('@/shared/components/slash-command-picker', () => ({
  SlashCommandPickerDialog: ({
    open,
    commands,
    onSelect,
  }: {
    open: boolean;
    commands: SlashCommandItem[];
    onSelect: (command: SlashCommandItem) => void;
  }) => (
    open ? (
      <button type="button" onClick={() => onSelect(commands[0])}>
        pick slash command
      </button>
    ) : null
  ),
}));

const job: AutomationJob = {
  id: 'job-1',
  name: 'Nightly backup',
  description: 'Back up workspace',
  owner: 'ops',
  userId: 'user-1',
  workspaceId: 'ws-1',
  prompt: '/backup',
  status: 'active',
  trigger: 'cron',
  schedule: '0 2 * * *',
  tags: ['backup'],
  createdAt: '2026-04-30T00:00:00.000Z',
  updatedAt: '2026-04-30T00:00:00.000Z',
  successRate: 100,
  failureRate: 0,
  totalExecutions: 2,
  averageDuration: 12,
  notifications: { email: false, slack: false, webhook: false },
  metadata: {},
};

const command: SlashCommandItem = {
  id: 'project:ops:deploy.md',
  fileName: 'deploy.md',
  kind: 'slash-command',
  scope: 'project',
  namespace: 'ops',
  displayName: 'ops/deploy',
  category: 'ops',
  description: 'Deploy service',
  invocation: '/ops/deploy',
  tags: [],
};

const renderDialog = (overrides: Partial<React.ComponentProps<typeof AutomationJobEditDialog>> = {}) => {
  const onSave = vi.fn<React.ComponentProps<typeof AutomationJobEditDialog>['onSave']>()
    .mockResolvedValue(undefined);

  render(
    <AutomationJobEditDialog
      isOpen
      task={job}
      loading={false}
      saving={false}
      onClose={vi.fn()}
      onSave={onSave}
      workspaces={[{ id: 'ws-1', name: 'Primary workspace', accessSource: 'owned' }]}
      workspacesLoading={false}
      commands={[command]}
      commandsLoading={false}
      existingTags={['backup', 'ops']}
      {...overrides}
    />,
  );

  return { onSave };
};

describe('AutomationJobEditDialog', () => {
  it('maps the selected job into editable form fields', () => {
    renderDialog();

    expect(screen.getByDisplayValue('Nightly backup')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Back up workspace')).toBeInTheDocument();
    expect(screen.getByDisplayValue('/backup')).toBeInTheDocument();
    expect(screen.getByDisplayValue('0 2 * * *')).toBeInTheDocument();
    expect(screen.getByText('Owned')).toBeInTheDocument();
  });

  it('submits the edited payload and supports slash command insertion', async () => {
    const user = userEvent.setup();
    const { onSave } = renderDialog();

    await user.clear(screen.getByPlaceholderText('Definition name'));
    expect(screen.getByRole('button', { name: 'Save definition' })).toBeDisabled();

    await user.type(screen.getByPlaceholderText('Definition name'), 'Daily deploy');
    await user.click(screen.getByRole('button', { name: 'Choose command' }));
    await user.click(screen.getByRole('button', { name: 'pick slash command' }));
    await user.click(screen.getByRole('button', { name: 'Save definition' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining<Partial<AutomationJobUpdateInput>>({
        id: 'job-1',
        name: 'Daily deploy',
        prompt: '/ops/deploy',
      }));
    });
  });
});
