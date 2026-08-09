import { render, screen, waitFor, within } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/apiClient';
import type { AutomationJob, JobUpdateInput } from '../model/automationTypes';
import { WorkspaceAutomationPage } from './WorkspaceAutomationPage';

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(),
  deleteJob: vi.fn(),
  detailProps: vi.fn(),
  getJob: vi.fn(),
  getMetrics: vi.fn(),
  listSlashCommands: vi.fn(),
  listJobs: vi.fn(),
  listWorkspaces: vi.fn(),
  executeJob: vi.fn(),
  toast: vi.fn(),
  updateJob: vi.fn(),
}));

vi.stubGlobal('confirm', mocks.confirm);

vi.mock('../api/automationApi', () => ({
  automationApi: {
    listJobs: mocks.listJobs,
    getMetrics: mocks.getMetrics,
    executeJob: mocks.executeJob,
    deleteJob: mocks.deleteJob,
    getJob: mocks.getJob,
    updateJob: mocks.updateJob,
  },
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('../components/execution/JobExecutionsDialog', () => ({
  JobExecutionsDialog: ({ isOpen, onViewExecution }: {
    isOpen: boolean;
    onViewExecution(id: string): void;
  }) => isOpen ? <button onClick={() => onViewExecution('execution-1')}>open execution</button> : null,
}));

vi.mock('../components/execution/ExecutionDetailDialog', () => ({
  ExecutionDetailDialog: (props: { open: boolean; executionId: string | null }) => {
    mocks.detailProps(props);
    return null;
  },
}));

vi.mock('../components/job-form/AutomationJobEditDialog', () => ({
  AutomationJobEditDialog: ({ isOpen, task, onSave }: {
    isOpen: boolean;
    task: AutomationJob | null;
    onSave(payload: JobUpdateInput): Promise<void>;
  }) => isOpen && task ? (
    <button
      onClick={() => void onSave({
        id: task.id,
        name: 'Updated nightly',
        description: task.description,
        prompt: task.prompt,
        trigger: task.trigger,
        schedule: task.schedule,
        exact: task.exact,
        agenticTool: task.agenticTool,
        model: task.model,
        agentConfig: { mode: task.agentConfig.mode },
        deliveryWebhookUrl: task.deliveryWebhookUrl,
        failureDestination: task.failureDestination,
        status: 'active',
      })}
    >
      save edit
    </button>
  ) : null,
}));

vi.mock('../api/automationWorkspaceApi', () => ({
  automationWorkspaceApi: {
    list: mocks.listWorkspaces,
    listSlashCommands: mocks.listSlashCommands,
  },
}));

const job: AutomationJob = {
  id: 'job-1', workspaceId: 'workspace-1', creatorUserId: 'user-1',
  creatorDisplayName: 'Operator', name: 'Nightly', description: 'Checks', prompt: 'Run',
  status: 'active', trigger: 'manual', schedule: '', exact: false, agenticTool: 'claude',
  model: 'claude-sonnet', agentConfig: { mode: null, permissionMode: 'bypassPermissions' },
  worktreeKey: 'automation/job-1', worktreeBranch: 'automation/job-1',
  createdAt: '2026-07-15T00:00:00Z', updatedAt: '2026-07-15T00:00:00Z',
  successRate: 1, totalExecutions: 1, averageDuration: 1, webhookConfigured: false,
  deliveryWebhookUrl: null, failureDestination: null, deletedAt: null,
};

const renderPage = () => render(
  <WorkspaceAutomationPage
    workspaceId="workspace-1"
    runtimeBaseUrl={null}
    isRuntimeLoading={false}
    locale="en-US"
  />,
);

describe('WorkspaceAutomationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.confirm.mockReturnValue(false);
    mocks.deleteJob.mockResolvedValue(undefined);
    mocks.getJob.mockResolvedValue(job);
    mocks.listJobs.mockResolvedValue([job]);
    mocks.listSlashCommands.mockResolvedValue([]);
    mocks.listWorkspaces.mockResolvedValue([]);
    mocks.getMetrics.mockResolvedValue({
      activeCount: 1, pausedCount: 0, failedCount: 0, draftCount: 0,
      successRate: 1, runningExecutions: 0, queuedExecutions: 0, averageDuration: 1,
    });
    mocks.executeJob.mockResolvedValue(undefined);
    mocks.updateJob.mockResolvedValue(undefined);
  });

  it('loads Manager data without Runtime and opens the single execution detail action', async () => {
    renderPage();

    expect(await screen.findByText('Nightly')).toBeInTheDocument();
    expect(mocks.listJobs).toHaveBeenCalledWith('workspace-1');
    expect(mocks.getMetrics).toHaveBeenCalledWith('workspace-1');
    expect(screen.getByPlaceholderText('workspace.automation.table.searchPlaceholder')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'workspace.automation.table.viewButton' }));
    await userEvent.click(await screen.findByRole('button', { name: 'open execution' }));
    await waitFor(() => {
      expect(mocks.detailProps).toHaveBeenLastCalledWith(expect.objectContaining({
        open: true,
        executionId: 'execution-1',
        runtimeBaseUrl: undefined,
      }));
    });
  });

  it('shows localized queue-full feedback when a manual run is rejected', async () => {
    mocks.executeJob.mockRejectedValue(
      new ApiError('raw queue message', 409, 'automation_queue_full'),
    );
    renderPage();

    const row = (await screen.findByText('Nightly')).closest('tr');
    expect(row).not.toBeNull();
    await userEvent.click(within(row!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('workspace.automation.table.executeAction'));

    await waitFor(() => {
      expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({
        variant: 'destructive',
        description: 'automation.errors.automation_queue_full',
      }));
    });
  });

  it('filters seven jobs and resets pagination when the search changes', async () => {
    const jobs = Array.from({ length: 7 }, (_, index): AutomationJob => ({
      ...job,
      id: `job-${index + 1}`,
      name: `Job ${index + 1}`,
      description: `Checks ${index + 1}`,
    }));
    mocks.listJobs.mockResolvedValue(jobs);
    renderPage();

    expect(await screen.findByText('Job 1')).toBeInTheDocument();
    expect(screen.queryByText('Job 7')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', {
      name: 'workspace.automation.pagination.next',
    }));
    expect(await screen.findByText('Job 7')).toBeInTheDocument();
    expect(screen.queryByText('Job 1')).not.toBeInTheDocument();

    await userEvent.type(
      screen.getByPlaceholderText('workspace.automation.table.searchPlaceholder'),
      'Job 1',
    );
    expect(await screen.findByText('Job 1')).toBeInTheDocument();
    expect(screen.queryByText('Job 7')).not.toBeInTheDocument();
  });

  it('loads an editable job, saves the update, and reloads the page data', async () => {
    renderPage();

    const row = (await screen.findByText('Nightly')).closest('tr');
    expect(row).not.toBeNull();
    await userEvent.click(within(row!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('workspace.automation.table.editAction'));

    expect(mocks.getJob).toHaveBeenCalledWith('job-1');
    await userEvent.click(await screen.findByRole('button', { name: 'save edit' }));

    await waitFor(() => {
      expect(mocks.updateJob).toHaveBeenCalledWith(expect.objectContaining({
        id: 'job-1',
        name: 'Updated nightly',
      }));
      expect(mocks.listJobs).toHaveBeenCalledTimes(2);
    });
  });

  it('does not delete before confirmation and reloads after a confirmed delete', async () => {
    renderPage();

    const row = (await screen.findByText('Nightly')).closest('tr');
    expect(row).not.toBeNull();
    await userEvent.click(within(row!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('workspace.automation.table.deleteAction'));
    expect(mocks.confirm).toHaveBeenCalledTimes(1);
    expect(mocks.deleteJob).not.toHaveBeenCalled();

    mocks.confirm.mockReturnValue(true);
    await userEvent.click(within(row!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('workspace.automation.table.deleteAction'));

    await waitFor(() => {
      expect(mocks.deleteJob).toHaveBeenCalledWith('job-1');
      expect(mocks.listJobs).toHaveBeenCalledTimes(2);
    });
  });

  it('reloads page data after a successful manual execution', async () => {
    renderPage();

    const row = (await screen.findByText('Nightly')).closest('tr');
    expect(row).not.toBeNull();
    await userEvent.click(within(row!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('workspace.automation.table.executeAction'));

    await waitFor(() => {
      expect(mocks.executeJob).toHaveBeenCalledWith('job-1');
      expect(mocks.listJobs).toHaveBeenCalledTimes(2);
    });
  });
});
