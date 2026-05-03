import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { JobCreateDialog } from './JobCreateDialog';

const mocks = vi.hoisted(() => ({
  closeCreateDialog: vi.fn(),
  createTask: vi.fn(),
  listWorkspaces: vi.fn(),
  listSlashCommands: vi.fn(),
  t: vi.fn((key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      'common.messages.fallbackOwnerName': 'Scheduled Task',
      'automation.create.title': 'Create scheduled task definition',
      'automation.create.subtitle': 'Register schedule',
      'automation.create.actions.creating': 'Creating...',
      'automation.create.actions.submit': 'Create definition',
      'automation.form.fields.name.label': 'Definition name',
      'automation.form.fields.name.placeholder': 'Definition name',
      'automation.form.fields.workspace.label': 'Target workspace',
      'automation.form.fields.workspace.placeholder': 'Select workspace',
      'automation.form.fields.workspace.loading': 'Loading workspaces',
      'automation.form.fields.workspace.empty': 'No workspaces',
      'automation.form.fields.workspace.error': 'Workspace error',
      'automation.form.fields.workspace.accessSource.owned': 'Owned',
      'automation.form.fields.workspace.accessSource.shared': 'Shared',
      'automation.form.fields.description.label': 'Description',
      'automation.form.fields.description.placeholder': 'Description',
      'automation.form.fields.prompt.label': 'Prompt',
      'automation.form.fields.prompt.placeholder': 'Prompt',
      'automation.form.fields.prompt.helper': 'Prompt helper',
      'automation.form.fields.prompt.selectCommand': 'Choose command',
      'automation.form.fields.prompt.commandsLoading': 'Loading commands',
      'automation.form.fields.prompt.commandsEmpty': 'No commands',
      'automation.form.fields.prompt.commandsError': 'Command error',
      'automation.form.fields.trigger.label': 'Trigger type',
      'automation.form.fields.trigger.placeholder': 'Trigger type',
      'automation.form.fields.status.label': 'Status',
      'automation.form.fields.status.placeholder': 'Status',
      'automation.form.fields.schedule.label': 'Job configuration',
      'automation.form.fields.schedule.timezoneHelper': 'Uses system timezone.',
      'automation.form.fields.tags.label': 'Tags',
      'automation.form.fields.tags.placeholder': 'Add tag',
      'automation.form.fields.tags.add': 'Add',
      'automation.form.fields.tags.suggestionsLabel': 'Suggestions:',
      'automation.form.trigger.cron': 'Cron schedule',
      'automation.form.trigger.manual': 'Manual',
      'automation.form.trigger.webhook': 'Webhook',
      'automation.form.status.active': 'Active',
      'automation.form.status.paused': 'Paused',
      'automation.form.status.draft': 'Draft',
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
      'automation.slashDialog.title': 'Select slash command',
      'automation.slashDialog.description': 'Pick command',
      'automation.slashDialog.searchPlaceholder': 'Search',
      'automation.slashDialog.empty': 'No commands',
      'automation.slashDialog.scope.all': 'All',
      'automation.slashDialog.scope.project': 'Project',
      'automation.slashDialog.scope.user': 'User',
      'common.cancel': 'Cancel',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: mocks.t }),
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: { id: 'user-1', name: 'User One' },
    },
  }),
}));

vi.mock('../providers/AutomationProvider', () => ({
  useAutomation: () => ({
    state: {
      isCreateDialogOpen: true,
      creating: false,
      automationJobs: [],
    },
    closeCreateDialog: mocks.closeCreateDialog,
    createTask: mocks.createTask,
  }),
}));

vi.mock('../services/workspaceApi', () => ({
  workspaceApi: {
    list: mocks.listWorkspaces,
    listSlashCommands: mocks.listSlashCommands,
  },
}));

vi.mock('@/shared/components/slash-command-picker', () => ({
  SlashCommandPickerDialog: () => null,
}));

describe('JobCreateDialog', () => {
  beforeEach(() => {
    mocks.createTask.mockReset();
    mocks.closeCreateDialog.mockReset();
    mocks.listWorkspaces.mockReset();
    mocks.listSlashCommands.mockReset();
    mocks.t.mockClear();
    mocks.createTask.mockResolvedValue(undefined);
    mocks.listWorkspaces.mockResolvedValue([{ id: 'ws-1', name: 'Primary workspace', accessSource: 'owned' }]);
    mocks.listSlashCommands.mockResolvedValue([]);
  });

  it('uses structured schedule controls and submits the generated cron string', { timeout: 10000 }, async () => {
    render(<JobCreateDialog />);

    expect(await screen.findByText('Create scheduled task definition')).toBeInTheDocument();
    expect(await screen.findByText('Runs every day at 09:00.')).toBeInTheDocument();
    expect(screen.getByText('0 9 * * *')).toBeInTheDocument();
    await waitFor(() => {
      expect(mocks.listWorkspaces).toHaveBeenCalled();
    });

    await userEvent.type(screen.getByPlaceholderText('Definition name'), 'Daily task');
    await userEvent.type(screen.getByPlaceholderText('Prompt'), '/daily');
    const submitButton = screen.getByRole('button', { name: 'Create definition' });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Daily task',
        workspaceId: 'ws-1',
        prompt: '/daily',
        schedule: '0 9 * * *',
      }));
    });
    expect(mocks.t).toHaveBeenCalledWith('automation.form.scheduleBuilder.fields.mode');
    expect(mocks.t).toHaveBeenCalledWith('automation.form.scheduleBuilder.summaryLabel');
  });
});
