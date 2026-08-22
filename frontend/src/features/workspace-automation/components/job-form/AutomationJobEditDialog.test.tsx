import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import type React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AutomationJobEditDialog } from './AutomationJobEditDialog';
import type { AutomationJob, JobUpdateInput } from '../../model/automationTypes';

const { tMock, toastMock } = vi.hoisted(() => ({
  toastMock: vi.fn(),
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
      'automation.form.fields.worktree.label': 'Worktree settings',
      'automation.form.fields.worktree.dedicated.label': 'Automatically create a dedicated worktree',
      'automation.form.fields.worktree.dedicated.description': 'The worktree is created on the first execution and reused by every later execution of this automation.',
      'automation.form.fields.description.label': 'Description',
      'automation.form.fields.description.placeholder': 'Description',
      'automation.form.fields.prompt.label': 'Prompt',
      'automation.form.fields.prompt.placeholder': 'Prompt',
      'automation.form.fields.prompt.selectInvocation': 'Choose Prompt Invocation',
      'automation.form.fields.prompt.toolCompatibilityWarning': 'Invocation may be incompatible',
      'automation.form.fields.trigger.label': 'Trigger type',
      'automation.form.fields.status.label': 'Status',
      'automation.form.fields.schedule.label': 'Job configuration',
      'automation.form.fields.schedule.placeholder': 'Cron expression',
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
      'automation.form.fields.webhookApiKey.regenerate': 'Regenerate',
      'automation.form.fields.webhookApiKey.configured': 'Webhook key is configured.',
      'automation.form.fields.webhookApiKey.notConfigured': 'Webhook key is not configured.',
      'automation.form.fields.webhookApiKey.helper': 'Use this API Key to trigger task execution via Webhook.',
      'automation.form.fields.webhookTriggerUrl.label': 'Webhook trigger URL',
      'automation.form.fields.webhookTriggerUrl.helper': 'POST to this URL with the header to trigger this job.',
      'automation.form.fields.webhookTriggerUrl.copy': 'Copy',
      'automation.form.fields.webhookTriggerUrl.copySuccessTitle': 'Copied',
      'automation.form.fields.webhookTriggerUrl.copySuccessDescription': 'The trigger URL has been copied.',
      'automation.form.fields.webhookTriggerUrl.copyFailedTitle': 'Copy failed',
      'automation.form.fields.webhookTriggerUrl.copyFailedDescription': 'Could not copy to clipboard.',
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
      'automation.form.trigger.cron': 'Cron schedule',
      'automation.form.trigger.at': 'One-off',
      'automation.form.trigger.every': 'Interval',
      'automation.form.trigger.manual': 'Manual',
      'automation.form.trigger.webhook': 'Webhook',
      'automation.form.status.active': 'Active',
      'automation.form.status.paused': 'Paused',
      'automation.promptInvocationDialog.title': 'Select prompt invocation',
      'automation.promptInvocationDialog.description': 'Pick an invocation',
      'automation.promptInvocationDialog.searchPlaceholder': 'Search invocations',
      'automation.promptInvocationDialog.empty': 'No invocations',
      'aiChat.settings.tool': 'Agentic Tool',
      'common.cancel': 'Cancel',
    }[key] ?? key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  registerCsrfTokenProvider: vi.fn(),
  registerExecutionGrantProvider: vi.fn(),
  registerExecutionGrantRejectionHandler: vi.fn(),
  apiClient: {
    buildUrl: (path: string) => `/api/v1${path}`,
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
      kind: 'slash-command';
      scope: 'project';
      namespace: string;
      displayName: string;
      category: string;
      description: string;
      invocation: string;
      tags: string[];
    }) => void;
  }) => (
    open ? (
      <button type="button" onClick={() => onSelect({
        id: 'codex:slash-command:project:ops/deploy.md',
        sourceKey: 'ops/deploy.md',
        fileName: 'ops/deploy.md',
        kind: 'slash-command',
        scope: 'project',
        namespace: 'ops',
        displayName: 'ops/deploy',
        category: 'ops',
        description: 'Deploy service',
        invocation: '/ops/deploy',
        tags: [],
      })}>
        pick prompt invocation
      </button>
    ) : null
  ),
}));

vi.mock('../../api/automationWorkspaceApi', () => ({
  automationWorkspaceApi: {
    getCapabilities: vi.fn().mockResolvedValue({
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
    }),
    listPromptInvocations: vi.fn(),
  },
}));

const job: AutomationJob = {
  id: 'job-1',
  name: 'Nightly backup',
  description: 'Back up workspace',
  workspaceId: 'ws-1',
  creatorUserId: 'user-1',
  creatorDisplayName: 'ops',
  prompt: '/backup',
  status: 'active',
  trigger: 'cron',
  schedule: '0 2 * * *',
  agenticTool: 'claude',
  model: 'claude-sonnet',
  agentConfig: { mode: null, permissionMode: 'bypassPermissions' },
  worktreeKey: 'automation/job-1',
  worktreeBranch: 'automation/job-1',
  createdAt: '2026-04-30T00:00:00.000Z',
  updatedAt: '2026-04-30T00:00:00.000Z',
  successRate: 100,
  totalExecutions: 2,
  averageDuration: 12,
  webhookConfigured: true,
  deliveryWebhookUrl: 'https://hooks.example.com/success',
  failureDestination: 'https://hooks.example.com/failure',
  deletedAt: null,
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
      workspaces={[{
        id: 'ws-1',
        name: 'Primary workspace',
        accessSource: 'owned',
        runtimeUrl: 'http://runtime.test',
      }]}
      {...overrides}
    />,
  );

  return { onSave };
};

describe('AutomationJobEditDialog', () => {
  beforeEach(() => {
    toastMock.mockReset();
  });

  it('maps the selected job into editable form fields', () => {
    renderDialog();

    expect(screen.getByDisplayValue('Nightly backup')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Back up workspace')).toBeInTheDocument();
    expect(screen.getByDisplayValue('/backup')).toBeInTheDocument();
    expect(screen.getByText('Runs every day at 02:00.')).toBeInTheDocument();
    expect(screen.getByText('0 2 * * *')).toBeInTheDocument();
    expect(screen.getByText('Owned')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://hooks.example.com/success')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://hooks.example.com/failure')).toBeInTheDocument();
    expect(screen.getAllByRole('combobox')[0]).toBeDisabled();
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
  });

  it('submits the edited payload and inserts the Runtime invocation', { timeout: 10000 }, async () => {
    const user = userEvent.setup();
    const { onSave } = renderDialog();

    fireEvent.change(screen.getByPlaceholderText('Definition name'), { target: { value: '' } });
    expect(screen.getByRole('button', { name: 'Save definition' })).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText('Definition name'), {
      target: { value: 'Daily deploy' },
    });
    await user.click(screen.getByRole('button', { name: 'Choose Prompt Invocation' }));
    await user.click(screen.getByRole('button', { name: 'pick prompt invocation' }));
    await user.click(screen.getByRole('button', { name: 'Save definition' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining<Partial<JobUpdateInput>>({
        id: 'job-1',
        name: 'Daily deploy',
        prompt: '/ops/deploy',
        schedule: '0 2 * * *',
        deliveryWebhookUrl: 'https://hooks.example.com/success',
        failureDestination: 'https://hooks.example.com/failure',
      }));
    });
    const payload = onSave.mock.calls[0][0];
    expect(payload).not.toHaveProperty('owner');
    expect(payload).not.toHaveProperty('userId');
    expect(payload).not.toHaveProperty('notifications');
    expect(payload).not.toHaveProperty('metadata');
    expect(payload).not.toHaveProperty('workspaceId');
  });

  it('keeps the invocation, warns after switching tools, and clears the warning after editing', async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole('button', { name: 'Choose Prompt Invocation' }));
    await user.click(screen.getByRole('button', { name: 'pick prompt invocation' }));
    await user.click(screen.getByRole('button', { name: 'Agentic Tool' }));
    await user.click(screen.getByRole('button', { name: 'codex' }));

    const prompt = screen.getByPlaceholderText('Prompt');
    expect(prompt).toHaveValue('/ops/deploy');
    expect(screen.getByRole('alert')).toHaveTextContent('Invocation may be incompatible');

    fireEvent.change(prompt, { target: { value: '/ops/deploy safely' } });
    expect(screen.queryByText('Invocation may be incompatible')).not.toBeInTheDocument();
  });

  it('maps every schedules with exact enabled into editable fields', async () => {
    const { onSave } = renderDialog({
      task: {
        ...job,
        trigger: 'every',
        schedule: '30m',
        exact: true,
      },
    });

    expect(screen.getByDisplayValue('30m')).toBeInTheDocument();
    expect(screen.getByText('Run on schedule')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Save definition' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining<Partial<JobUpdateInput>>({
        trigger: 'every',
        schedule: '30m',
        exact: true,
      }));
    });
  });

  it('allows clearing delivery destinations', { timeout: 10000 }, async () => {
    const user = userEvent.setup();
    const { onSave } = renderDialog();

    fireEvent.change(screen.getByDisplayValue('https://hooks.example.com/success'), {
      target: { value: '' },
    });
    fireEvent.change(screen.getByDisplayValue('https://hooks.example.com/failure'), {
      target: { value: '' },
    });
    await user.click(screen.getByRole('button', { name: 'Save definition' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining<Partial<JobUpdateInput>>({
        deliveryWebhookUrl: '',
        failureDestination: '',
      }));
    });
  });

  it('shows the response-only configured state without generating or submitting a secret', async () => {
    const randomUuid = vi.spyOn(crypto, 'randomUUID');
    const { onSave } = renderDialog({
      task: { ...job, trigger: 'webhook', schedule: '', webhookConfigured: true },
    });

    expect(screen.getByText('Webhook key is configured.')).toBeInTheDocument();
    expect(randomUuid).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Save definition' }));

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0]).not.toHaveProperty('webhookApiKey');
    randomUuid.mockRestore();
  });

  it('generates and submits a new webhook secret only after explicit regeneration', async () => {
    const randomUuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue(
      '12345678-1234-4234-8234-123456789abc',
    );
    const mathRandom = vi.spyOn(Math, 'random');
    const { onSave } = renderDialog({
      task: { ...job, trigger: 'webhook', schedule: '', webhookConfigured: true },
    });

    await userEvent.click(screen.getByRole('button', { name: 'Regenerate' }));
    expect(screen.getByDisplayValue('12345678123442348234123456789abc')).toBeInTheDocument();
    expect(randomUuid).toHaveBeenCalledTimes(1);
    expect(mathRandom).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Save definition' }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
        webhookApiKey: '12345678123442348234123456789abc',
      }));
    });
    randomUuid.mockRestore();
    mathRandom.mockRestore();
  });

  it('shows the full webhook trigger URL and copies it on click', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn() },
    });
    renderDialog({
      task: { ...job, trigger: 'webhook', schedule: '', webhookConfigured: true },
    });

    const expectedUrl = new URL('/api/v1/automation/webhook/job-1', window.location.origin).toString();
    expect(screen.getByDisplayValue(expectedUrl)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Copy' }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expectedUrl);
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: 'Copied' }));
  });

  it('shows a destructive toast when copying the webhook trigger URL fails', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error('Clipboard denied')) },
    });
    renderDialog({
      task: { ...job, trigger: 'webhook', schedule: '', webhookConfigured: true },
    });

    await userEvent.click(screen.getByRole('button', { name: 'Copy' }));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Copy failed',
        variant: 'destructive',
      }));
    });
  });
});
