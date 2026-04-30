import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { AutomationJobEditDialog } from './AutomationJobEditDialog';
import type { AutomationJob, AutomationJobUpdateInput } from '@/features/automation/types';
import type { SlashCommandItem } from '@/shared/types/slashCommands';

const { tMock } = vi.hoisted(() => ({
  tMock: (key: string, params?: Record<string, string | number>) =>
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
      'automation.form.scheduleBuilder.fields.mode': 'Frequency',
      'automation.form.scheduleBuilder.fields.minute': 'Minute',
      'automation.form.scheduleBuilder.fields.hour': 'Hour',
      'automation.form.scheduleBuilder.fields.time': 'Time',
      'automation.form.scheduleBuilder.fields.weekdays': 'Weekdays',
      'automation.form.scheduleBuilder.fields.dayOfMonth': 'Day of month',
      'automation.form.scheduleBuilder.fields.advancedCron': 'Cron expression',
      'automation.form.scheduleBuilder.modes.hourly': 'Hourly',
      'automation.form.scheduleBuilder.modes.daily': 'Daily',
      'automation.form.scheduleBuilder.modes.weekly': 'Weekly',
      'automation.form.scheduleBuilder.modes.monthly': 'Monthly',
      'automation.form.scheduleBuilder.modes.advanced': 'Advanced cron',
      'automation.form.scheduleBuilder.weekdays.0': 'Sunday',
      'automation.form.scheduleBuilder.weekdays.1': 'Monday',
      'automation.form.scheduleBuilder.weekdays.2': 'Tuesday',
      'automation.form.scheduleBuilder.weekdays.3': 'Wednesday',
      'automation.form.scheduleBuilder.weekdays.4': 'Thursday',
      'automation.form.scheduleBuilder.weekdays.5': 'Friday',
      'automation.form.scheduleBuilder.weekdays.6': 'Saturday',
      'automation.form.scheduleBuilder.weekdays.short.0': 'Sun',
      'automation.form.scheduleBuilder.weekdays.short.1': 'Mon',
      'automation.form.scheduleBuilder.weekdays.short.2': 'Tue',
      'automation.form.scheduleBuilder.weekdays.short.3': 'Wed',
      'automation.form.scheduleBuilder.weekdays.short.4': 'Thu',
      'automation.form.scheduleBuilder.weekdays.short.5': 'Fri',
      'automation.form.scheduleBuilder.weekdays.short.6': 'Sat',
      'automation.form.scheduleBuilder.weekdaySeparator': ', ',
      'automation.form.scheduleBuilder.dayOfMonthOption': `Day ${params?.day ?? ''}`,
      'automation.form.scheduleBuilder.advancedPlaceholder': '0 9 * * *',
      'automation.form.scheduleBuilder.advancedHelper': 'Use advanced cron only when needed.',
      'automation.form.scheduleBuilder.summaryLabel': 'Summary',
      'automation.form.scheduleBuilder.summary.hourly': `Runs every hour at minute ${params?.minute ?? ''}.`,
      'automation.form.scheduleBuilder.summary.daily': `Runs every day at ${params?.time ?? ''}.`,
      'automation.form.scheduleBuilder.summary.weekly': `Runs every ${params?.weekdays ?? ''} at ${params?.time ?? ''}.`,
      'automation.form.scheduleBuilder.summary.monthly': `Runs on day ${params?.day ?? ''} of every month at ${params?.time ?? ''}.`,
      'automation.form.scheduleBuilder.summary.advanced': `Runs using cron expression ${params?.cron ?? ''}.`,
      'automation.form.scheduleBuilder.validation.weekdayRequired': 'Select at least one weekday.',
      'automation.form.scheduleBuilder.validation.invalidCron': 'Enter a valid five-field cron expression.',
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
    expect(screen.getByText('Runs every day at 02:00.')).toBeInTheDocument();
    expect(screen.getByText('0 2 * * *')).toBeInTheDocument();
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
        schedule: '0 2 * * *',
      }));
    });
  });
});
