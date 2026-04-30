import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobExecutionsDialog } from './JobExecutionsDialog';
import type { AutomationJob, JobExecution } from '@/features/automation/types';

const { cancelExecutionMock, toastMock, tMock } = vi.hoisted(() => ({
  cancelExecutionMock: vi.fn(),
  toastMock: vi.fn(),
  tMock: (key: string, params?: Record<string, string | number>) =>
    ({
      'workspace.automation.dialogs.executions.recordTitle': `Executions for ${params?.name}`,
      'workspace.automation.dialogs.executions.recordDescription': 'Execution records',
      'workspace.automation.dialogs.executions.filter.title': 'Filters',
      'workspace.automation.dialogs.executions.filter.description': 'Filter executions',
      'workspace.automation.dialogs.executions.refresh': 'Refresh',
      'workspace.automation.dialogs.executions.rangeTabs.all': 'All',
      'workspace.automation.dialogs.executions.rangeTabs.today': 'Today',
      'workspace.automation.dialogs.executions.rangeTabs.tomorrow': 'Tomorrow',
      'workspace.automation.dialogs.executions.rangeTabs.week': 'Week',
      'workspace.automation.dialogs.executions.rangeTabs.month': 'Month',
      'workspace.automation.dialogs.executions.rangeTabs.custom': 'Custom',
      'workspace.automation.dialogs.executions.empty': 'No executions',
      'workspace.automation.dialogs.executions.startedAt': `Started ${params?.time}`,
      'workspace.automation.dialogs.executions.triggerLabel': `Trigger ${params?.trigger}`,
      'workspace.automation.dialogs.executions.durationLabel': `${params?.seconds} seconds`,
      'workspace.automation.dialogs.executions.queuePosition': `Queue #${params?.position}`,
      'workspace.automation.dialogs.executions.cancelButton': 'Cancel execution',
      'workspace.automation.dialogs.executions.viewLog': 'View logs',
      'workspace.automation.dialogs.executions.viewSession': 'View conversation',
      'workspace.automation.dialogs.executions.status.waiting': 'Waiting',
      'workspace.automation.dialogs.executions.status.success': 'Success',
      'workspace.automation.dialogs.executionLog.description': 'Execution log details',
      'workspace.automation.dialogs.executionLog.fields.executionId': 'Execution ID',
      'workspace.automation.dialogs.executionLog.fields.jobId': 'Job ID',
      'workspace.automation.dialogs.executionLog.fields.startedAt': 'Started at',
      'workspace.automation.dialogs.executionLog.fields.finishedAt': 'Finished at',
      'workspace.automation.dialogs.executionLog.fields.trigger': 'Trigger',
      'workspace.automation.dialogs.executionLog.fields.duration': 'Duration',
      'workspace.automation.dialogs.executionLog.durationSeconds': `${params?.seconds} seconds`,
      'workspace.automation.dialogs.executionLog.logs.title': 'Execution logs',
      'workspace.automation.dialogs.executionLog.logs.empty': 'No logs',
      'workspace.automation.dialogs.executionLog.logs.loading': 'Loading logs',
      'workspace.automation.dialogs.executionLog.logs.reload': 'Reload logs',
      'workspace.automation.dialogs.executionLog.logs.filters.all': 'All',
      'workspace.automation.dialogs.executionLog.logs.filters.info': 'Info',
      'workspace.automation.dialogs.executionLog.logs.filters.error': 'Error',
      'workspace.automation.dialogs.executionLog.logs.filters.warning': 'Warning',
      'workspace.automation.dialogs.executionLog.logs.filters.success': 'Success',
      'workspace.automation.dialogs.executionLog.mock.start': 'Started',
      'workspace.automation.dialogs.executionLog.mock.loadEnvironment': 'Loaded environment',
      'workspace.automation.dialogs.executionLog.mock.completed': 'Completed',
      'workspace.automation.dialogs.executions.cancel.success.title': 'Cancelled',
      'workspace.automation.dialogs.executions.cancel.success.description': 'Execution cancelled',
      'workspace.automation.triggers.manual': 'Manual',
    }[key] ?? key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock, state: { currentLanguage: 'en' } }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/features/automation/services/automationApi', () => ({
  automationApi: {
    cancelExecution: cancelExecutionMock,
  },
}));

vi.mock('@/features/workspace/components/session-viewer/SessionViewerDialog', () => ({
  SessionViewerDialog: ({ sessionId }: { sessionId: string | null }) => (
    <div data-testid="session-viewer">session:{sessionId}</div>
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
  trigger: 'manual',
  schedule: '',
  tags: [],
  createdAt: '2026-04-30T00:00:00.000Z',
  updatedAt: '2026-04-30T00:00:00.000Z',
  successRate: 100,
  failureRate: 0,
  totalExecutions: 2,
  averageDuration: 12,
  notifications: { email: false, slack: false, webhook: false },
  metadata: {},
};

const executions: JobExecution[] = [
  {
    id: 'exec-waiting',
    jobId: 'job-1',
    status: 'waiting',
    trigger: 'manual',
    startedAt: '2026-04-30T03:00:00.000Z',
    duration: 8,
    sessionId: 'session-1',
    summary: 'Waiting execution',
    queuePosition: 2,
  },
  {
    id: 'exec-success',
    jobId: 'job-1',
    status: 'success',
    trigger: 'manual',
    startedAt: '2026-04-30T04:00:00.000Z',
    finishedAt: '2026-04-30T04:01:00.000Z',
    duration: 60,
    summary: 'Completed execution',
  },
];

describe('JobExecutionsDialog', () => {
  it('renders executions and opens log/session dialogs', async () => {
    const user = userEvent.setup();

    render(
      <JobExecutionsDialog
        isOpen
        job={job}
        executions={executions}
        onClose={vi.fn()}
        runtimeBaseUrl="http://runtime.test"
      />,
    );

    expect(screen.getByText('Executions for Nightly backup')).toBeInTheDocument();
    expect(screen.getByText('Waiting execution')).toBeInTheDocument();
    expect(screen.getByText('Completed execution')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /view conversation/i }));
    expect(screen.getByTestId('session-viewer')).toHaveTextContent('session:session-1');

    await user.click(screen.getAllByRole('button', { name: /view logs/i })[0]);
    expect(screen.getByText('Execution log details')).toBeInTheDocument();
  });

  it('refreshes and cancels cancellable executions', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    cancelExecutionMock.mockResolvedValue({ cancelled: true, message: 'ok' });

    render(
      <JobExecutionsDialog
        isOpen
        job={job}
        executions={executions}
        onClose={vi.fn()}
        onRefresh={onRefresh}
        runtimeBaseUrl="http://runtime.test"
      />,
    );

    await user.click(screen.getByRole('button', { name: /refresh/i }));
    expect(onRefresh).toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /cancel execution/i }));

    await waitFor(() => {
      expect(cancelExecutionMock).toHaveBeenCalledWith('exec-waiting');
      expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ variant: 'success' }));
    });
  });
});
