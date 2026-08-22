import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { AutomationJobCreateDialog } from './AutomationJobCreateDialog';
import { ApiError } from '@/shared/api/apiClient';

const mocks = vi.hoisted(() => ({
  closeCreateDialog: vi.fn(),
  createTask: vi.fn(),
  listWorkspaces: vi.fn(),
  listPromptInvocations: vi.fn(),
  getCapabilities: vi.fn(),
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
      'automation.form.fields.worktree.label': 'Worktree settings',
      'automation.form.fields.worktree.dedicated.label': 'Automatically create a dedicated worktree',
      'automation.form.fields.worktree.dedicated.description': 'The worktree is created on the first execution and reused by every later execution of this automation.',
      'automation.form.fields.description.label': 'Description',
      'automation.form.fields.description.placeholder': 'Description',
      'automation.form.fields.prompt.label': 'Prompt',
      'automation.form.fields.prompt.placeholder': 'Prompt',
      'automation.form.fields.prompt.helper': 'Prompt helper',
      'automation.form.fields.prompt.selectInvocation': 'Choose Prompt Invocation',
      'automation.form.fields.prompt.agenticToolRequired': 'Select an Agentic Tool first',
      'automation.form.fields.prompt.toolCompatibilityWarning': 'Invocation may be incompatible',
      'automation.form.fields.trigger.label': 'Trigger type',
      'automation.form.fields.trigger.placeholder': 'Trigger type',
      'automation.form.fields.status.label': 'Status',
      'automation.form.fields.status.placeholder': 'Status',
      'automation.form.fields.schedule.label': 'Job configuration',
      'automation.form.fields.schedule.timezoneHelper': 'Uses system timezone.',
      'automation.form.fields.atSchedule.label': 'Execution time',
      'automation.form.fields.atSchedule.placeholder': '20m or 2026-02-01T16:00:00Z',
      'automation.form.fields.atSchedule.help': 'Relative time or ISO timestamp.',
      'automation.form.fields.everyInterval.label': 'Interval',
      'automation.form.fields.everyInterval.placeholder': '30m or 1h',
      'automation.form.fields.everyInterval.help': 'Fixed execution interval.',
      'automation.form.fields.exact.label': 'Run on schedule',
      'automation.form.fields.exact.help': 'Run exactly at the scheduled time without spreading top-of-hour tasks.',
      'automation.form.fields.deliveryWebhookUrl.label': 'Delivery webhook URL',
      'automation.form.fields.deliveryWebhookUrl.placeholder': 'https://hooks.example.com/success',
      'automation.form.fields.deliveryWebhookUrl.help': 'POST successful scheduled runs to this URL.',
      'automation.form.fields.failureDestination.label': 'Failure destination',
      'automation.form.fields.failureDestination.placeholder': 'https://hooks.example.com/failure',
      'automation.form.fields.webhookTriggerUrl.pendingCreateHelper': 'Save this job first, then open it for editing to view and copy the trigger URL.',
      'automation.form.trigger.cron': 'Cron schedule',
      'automation.form.trigger.at': 'One-off',
      'automation.form.trigger.every': 'Interval',
      'automation.form.trigger.manual': 'Manual',
      'automation.form.trigger.webhook': 'Webhook',
      'automation.form.status.active': 'Active',
      'automation.form.status.paused': 'Paused',
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
      'automation.promptInvocationDialog.title': 'Select prompt invocation',
      'automation.promptInvocationDialog.description': 'Pick an invocation',
      'automation.promptInvocationDialog.searchPlaceholder': 'Search',
      'automation.promptInvocationDialog.empty': 'No invocations',
      'aiChat.settings.tool': 'Agentic Tool',
      'common.cancel': 'Cancel',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: mocks.t }),
}));

vi.mock('../../providers/AutomationProvider', () => ({
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

vi.mock('../../api/automationWorkspaceApi', () => ({
  automationWorkspaceApi: {
    list: mocks.listWorkspaces,
    listPromptInvocations: mocks.listPromptInvocations,
    getCapabilities: mocks.getCapabilities,
  },
}));

vi.mock('@/shared/components/prompt-invocation-picker', () => ({
  PromptInvocationPickerDialog: ({
    open,
    onSelect,
  }: {
    open: boolean;
    onSelect: (item: {
      id: string;
      sourceKey: string;
      fileName: string;
      kind: 'skill';
      scope: 'project';
      displayName: string;
      category: string;
      description: string;
      invocation: string;
      tags: string[];
    }) => void;
  }) => open ? (
    <button type="button" onClick={() => onSelect({
      id: 'codex:skill:project:review/SKILL.md',
      sourceKey: 'review/SKILL.md',
      fileName: 'SKILL.md',
      kind: 'skill',
      scope: 'project',
      displayName: 'review',
      category: 'project',
      description: 'Review changes',
      invocation: '$review',
      tags: [],
    })}>
      select-$review
    </button>
  ) : null,
}));

describe('AutomationJobCreateDialog', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
    mocks.createTask.mockReset();
    mocks.closeCreateDialog.mockReset();
    mocks.listWorkspaces.mockReset();
    mocks.listPromptInvocations.mockReset();
    mocks.getCapabilities.mockReset();
    mocks.t.mockClear();
    mocks.createTask.mockResolvedValue(undefined);
    mocks.listWorkspaces.mockResolvedValue([{
      id: 'ws-1',
      name: 'Primary workspace',
      accessSource: 'owned',
      runtimeUrl: 'http://runtime.test',
    }]);
    mocks.listPromptInvocations.mockResolvedValue({ items: [] });
    mocks.getCapabilities.mockResolvedValue({
      defaultTool: 'claude',
      tools: [{
        id: 'claude',
        models: ['claude-sonnet'],
        defaultModel: 'claude-sonnet',
        modes: ['execute', 'plan'],
        defaultMode: 'execute',
        contextWindow: 200000,
      }, {
        id: 'codex',
        models: ['gpt-5'],
        defaultModel: 'gpt-5',
        modes: ['execute'],
        defaultMode: 'execute',
        contextWindow: 200000,
      }],
    });
  });

  it('writes the Runtime-provided invocation into the Prompt field', async () => {
    render(<AutomationJobCreateDialog />);

    await screen.findByText('Create scheduled task definition');
    const pickerButton = await screen.findByRole('button', {
      name: 'Choose Prompt Invocation',
    });
    await waitFor(() => expect(pickerButton).toBeEnabled());
    await userEvent.click(pickerButton);
    await userEvent.click(screen.getByRole('button', { name: 'select-$review' }));

    expect(screen.getByPlaceholderText('Prompt')).toHaveValue('$review');
  });

  it('keeps the invocation, warns after switching tools, and clears the warning after editing', async () => {
    const user = userEvent.setup();
    render(<AutomationJobCreateDialog />);

    await user.click(await screen.findByRole('button', { name: 'Choose Prompt Invocation' }));
    await user.click(screen.getByRole('button', { name: 'select-$review' }));
    await user.click(screen.getByRole('button', { name: 'Agentic Tool' }));
    await user.click(screen.getByRole('button', { name: 'codex' }));

    const prompt = screen.getByPlaceholderText('Prompt');
    expect(prompt).toHaveValue('$review');
    expect(screen.getByRole('alert')).toHaveTextContent('Invocation may be incompatible');

    fireEvent.change(prompt, { target: { value: '$review with context' } });
    expect(screen.queryByText('Invocation may be incompatible')).not.toBeInTheDocument();
  });

  it('uses structured schedule controls and submits the generated cron string', { timeout: 20000 }, async () => {
    render(<AutomationJobCreateDialog />);

    expect(await screen.findByText('Create scheduled task definition')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toHaveClass('h-[min(880px,92vh)]');
    expect(screen.queryByText('Tags')).not.toBeInTheDocument();
    expect(screen.getByText('Worktree settings')).toBeInTheDocument();
    const worktreeSummary = screen.getByRole('group', {
      name: 'Worktree settings Automatically create a dedicated worktree',
    });
    expect(worktreeSummary).toHaveTextContent('Automatically create a dedicated worktree');
    expect(worktreeSummary).toHaveTextContent(
      'The worktree is created on the first execution and reused by every later execution of this automation.',
    );
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(await screen.findByText('Runs every day at 09:00.')).toBeInTheDocument();
    expect(screen.getByText('0 9 * * *')).toBeInTheDocument();
    await waitFor(() => {
      expect(mocks.listWorkspaces).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByPlaceholderText('Definition name'), {
      target: { value: 'Daily task' },
    });
    fireEvent.change(screen.getByPlaceholderText('Prompt'), { target: { value: '/daily' } });
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
    const payload = mocks.createTask.mock.calls[0][0];
    expect(payload).not.toHaveProperty('owner');
    expect(payload).not.toHaveProperty('userId');
    expect(payload).not.toHaveProperty('notifications');
    expect(payload).not.toHaveProperty('metadata');
  });

  it('generates an inbound webhook secret with Web Crypto only', { timeout: 10000 }, async () => {
    const randomUuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue(
      '12345678-1234-4234-8234-123456789abc',
    );
    const mathRandom = vi.spyOn(Math, 'random');
    render(<AutomationJobCreateDialog />);

    expect(await screen.findByText('Create scheduled task definition')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('combobox')[1]);
    const webhookOptions = await screen.findAllByText('Webhook');
    await userEvent.click(webhookOptions.at(-1)!);

    expect(screen.getByDisplayValue('12345678123442348234123456789abc')).toBeInTheDocument();
    expect(randomUuid).toHaveBeenCalledTimes(1);
    expect(mathRandom).not.toHaveBeenCalled();

    expect(screen.getByText(
      'Save this job first, then open it for editing to view and copy the trigger URL.',
    )).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy' })).not.toBeInTheDocument();
  });

  it('submits one-off schedules from the at trigger input', { timeout: 10000 }, async () => {
    render(<AutomationJobCreateDialog />);

    expect(await screen.findByText('Create scheduled task definition')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Definition name'), {
      target: { value: 'One-off task' },
    });
    fireEvent.change(screen.getByPlaceholderText('Prompt'), { target: { value: '/once' } });

    await userEvent.click(screen.getAllByRole('combobox')[1]);
    await waitFor(() => {
      expect(screen.getAllByText('One-off').length).toBeGreaterThan(1);
    });
    await userEvent.click(screen.getAllByText('One-off')[1]);
    const scheduleInput = screen.getByPlaceholderText('20m or 2026-02-01T16:00:00Z');
    fireEvent.change(scheduleInput, { target: { value: '20m' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create definition' })).toBeEnabled();
    });
    await userEvent.click(screen.getByRole('button', { name: 'Create definition' }));

    await waitFor(() => {
      expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({
        name: 'One-off task',
        trigger: 'at',
        schedule: '20m',
      }));
    });
  });

  it('submits delivery webhook destinations', { timeout: 20000 }, async () => {
    render(<AutomationJobCreateDialog />);

    expect(await screen.findByText('Create scheduled task definition')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Definition name'), {
      target: { value: 'Daily task' },
    });
    fireEvent.change(screen.getByPlaceholderText('Prompt'), { target: { value: '/daily' } });
    fireEvent.change(screen.getByPlaceholderText('https://hooks.example.com/success'), {
      target: { value: 'https://hooks.example.com/success' },
    });
    fireEvent.change(screen.getByPlaceholderText('https://hooks.example.com/failure'), {
      target: { value: 'https://hooks.example.com/failure' },
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create definition' })).toBeEnabled();
    });
    await userEvent.click(screen.getByRole('button', { name: 'Create definition' }));

    await waitFor(() => {
      expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({
        deliveryWebhookUrl: 'https://hooks.example.com/success',
        failureDestination: 'https://hooks.example.com/failure',
      }));
    });
  });

  it.each([
    'workspace_git_repository_required',
    'workspace_git_initial_commit_required',
  ])('shows the stable worktree preflight reason %s in the form', async (errorCode) => {
    mocks.createTask.mockRejectedValue(new ApiError(
      errorCode,
      409,
      errorCode,
    ));
    render(<AutomationJobCreateDialog />);

    await screen.findByText('Create scheduled task definition');
    fireEvent.change(screen.getByPlaceholderText('Definition name'), {
      target: { value: 'Git check' },
    });
    fireEvent.change(screen.getByPlaceholderText('Prompt'), {
      target: { value: 'Run checks' },
    });
    const submitButton = screen.getByRole('button', { name: 'Create definition' });
    await waitFor(() => expect(submitButton).toBeEnabled());
    await userEvent.click(submitButton);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      `automation.create.errors.${errorCode}`,
    );
  }, 20000);
});
