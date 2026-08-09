import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { JobExecutionsDialog } from './JobExecutionsDialog';
import type { AutomationJob, JobExecution } from '../../model/automationTypes';

const mocks = vi.hoisted(() => ({
  getJobExecutions: vi.fn(),
}));

vi.mock('../../api/automationApi', () => ({
  automationApi: { getJobExecutions: mocks.getJobExecutions },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      key === 'workspace.automation.dialogs.executions.recordTitle'
        ? `Executions for ${params?.name}`
        : params ? `${key}:${JSON.stringify(params)}` : key,
    state: { currentLanguage: 'en' },
  }),
}));

const job: AutomationJob = {
  id: 'job-1',
  workspaceId: 'workspace-1',
  creatorUserId: 'user-1',
  creatorDisplayName: 'Operator',
  name: 'Nightly backup',
  description: 'Back up workspace',
  prompt: '/backup',
  status: 'active',
  trigger: 'manual',
  schedule: '',
  exact: false,
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
  webhookConfigured: false,
  deliveryWebhookUrl: null,
  failureDestination: null,
  deletedAt: null,
};

const executions: JobExecution[] = [
  {
    id: 'execution-queued',
    jobId: 'job-1',
    workspaceId: 'workspace-1',
    status: 'queued',
    trigger: 'manual',
    scheduledFor: '2026-04-30T03:00:00.000Z',
    queuedAt: '2026-04-30T03:00:01.000Z',
    startedAt: null,
    finishedAt: null,
    cancelRequestedAt: null,
    queuePosition: 1,
    errorCode: null,
    errorMessage: null,
  },
  {
    id: 'execution-success',
    jobId: 'job-1',
    workspaceId: 'workspace-1',
    status: 'success',
    trigger: 'manual',
    scheduledFor: '2026-04-30T04:00:00.000Z',
    queuedAt: '2026-04-30T04:00:01.000Z',
    startedAt: '2026-04-30T04:00:02.000Z',
    finishedAt: '2026-04-30T04:01:00.000Z',
    cancelRequestedAt: null,
    queuePosition: null,
    errorCode: null,
    errorMessage: null,
  },
];

describe('JobExecutionsDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getJobExecutions.mockResolvedValue({
      items: executions,
      total: 12,
      page: 1,
      pageSize: 10,
    });
  });

  it('renders server-backed executions as a table with one viewing action per row', async () => {
    const onViewExecution = vi.fn();
    render(
      <JobExecutionsDialog
        isOpen
        job={job}
        onClose={vi.fn()}
        onViewExecution={onViewExecution}
      />,
    );

    expect(screen.getByText('Executions for Nightly backup')).toBeInTheDocument();
    expect(await screen.findAllByRole('button', {
      name: 'workspace.automation.dialogs.executions.viewExecution',
    })).toHaveLength(2);
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(mocks.getJobExecutions).toHaveBeenCalledWith('job-1', {
      page: 1,
      pageSize: 10,
      rangeStart: undefined,
      rangeEnd: undefined,
    });
    await userEvent.click(screen.getAllByRole('button', {
      name: 'workspace.automation.dialogs.executions.viewExecution',
    })[0]);
    expect(onViewExecution).toHaveBeenCalledWith('execution-queued');
  });

  it('refreshes, paginates, and preserves the fixed-height date tabs', async () => {
    render(
      <JobExecutionsDialog
        isOpen
        job={job}
        onClose={vi.fn()}
        onViewExecution={vi.fn()}
      />,
    );

    expect(await screen.findByText(/position.*1/)).toBeInTheDocument();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('h-[min(760px,90vh)]');
    expect(screen.getAllByRole('tab')).toHaveLength(6);
    expect(screen.getByRole('button', {
      name: 'workspace.automation.dialogs.executions.refresh',
    }).closest('.border-b')).not.toBeNull();
    await userEvent.click(screen.getByRole('button', {
      name: 'workspace.automation.dialogs.executions.refresh',
    }));
    expect(mocks.getJobExecutions).toHaveBeenCalledTimes(2);

    const nextPageButton = screen.getByRole('button', {
      name: 'workspace.automation.dialogs.executions.nextPage',
    });
    await waitFor(() => expect(nextPageButton).toBeEnabled());
    await userEvent.click(nextPageButton);
    await waitFor(() => {
      expect(mocks.getJobExecutions).toHaveBeenLastCalledWith('job-1', expect.objectContaining({
        page: 2,
        pageSize: 10,
      }));
    });

    await userEvent.click(screen.getByRole('tab', {
      name: 'workspace.automation.dialogs.executions.rangeTabs.custom',
    }));
    expect(screen.getAllByDisplayValue('')).toHaveLength(2);
    expect(dialog).toHaveClass('h-[min(760px,90vh)]');
  });
});
