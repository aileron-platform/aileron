import { render, screen, waitFor, within } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/apiClient';
import type { AutomationJob } from '../model/automationTypes';
import { AutomationDashboardPage } from './AutomationDashboardPage';

const mocks = vi.hoisted(() => ({
  automationJobs: [] as AutomationJob[],
  deleteTask: vi.fn(),
  detailProps: vi.fn(),
  executeTask: vi.fn(),
  filter: 'all',
  historyProps: vi.fn(),
  openEditDialog: vi.fn(),
  search: '',
  setSearch: vi.fn(),
  toast: vi.fn(),
}));

const job = {
  id: 'job-1', workspaceId: 'workspace-1', creatorUserId: 'user-1',
  creatorDisplayName: 'Operator', name: 'Nightly', description: 'Checks', prompt: 'Run',
  status: 'active', trigger: 'manual', schedule: '', exact: false, agenticTool: 'claude',
  model: 'claude-sonnet', agentConfig: { mode: null, permissionMode: 'bypassPermissions' },
  worktreeKey: 'automation/job-1', worktreeBranch: 'automation/job-1',
  createdAt: '2026-07-15T00:00:00Z', updatedAt: '2026-07-15T00:00:00Z',
  successRate: 1, totalExecutions: 1, averageDuration: 1, webhookConfigured: false,
  deliveryWebhookUrl: null, failureDestination: null, deletedAt: null,
} as const;

const createJob = (overrides: Partial<AutomationJob> = {}): AutomationJob => ({
  ...job,
  ...overrides,
} as AutomationJob);

const globalExecution = {
  id: 'execution-global', jobId: 'job-1', workspaceId: 'workspace-1', status: 'running',
  trigger: 'manual', scheduledFor: '2026-07-15T00:00:00Z', queuedAt: null,
  startedAt: '2026-07-15T00:00:01Z', finishedAt: null, cancelRequestedAt: null,
  queuePosition: null, errorCode: null, errorMessage: null,
} as const;

vi.mock('../providers/AutomationProvider', () => ({
  useAutomation: () => ({
    state: {
      automationJobs: mocks.automationJobs, metrics: null, jobExecutions: [globalExecution],
      filter: mocks.filter, search: mocks.search, creating: false,
    },
    setSearch: mocks.setSearch,
    refresh: vi.fn(), openCreateDialog: vi.fn(), openEditDialog: mocks.openEditDialog,
    executeTask: mocks.executeTask, deleteTask: mocks.deleteTask,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key, state: { currentLanguage: 'en' } }),
}));

vi.mock('../components/execution/JobExecutionsDialog', () => ({
  JobExecutionsDialog: (props: {
    isOpen: boolean;
    job: { id: string } | null;
    onClose: () => void;
    onViewExecution: (executionId: string) => void;
  }) => {
    mocks.historyProps(props);
    return props.isOpen ? (
      <div>
        <span>job history open {props.job?.id}</span>
        <button onClick={props.onClose}>close-history</button>
        <button onClick={() => props.onViewExecution('execution-scoped')}>open-execution-scoped</button>
      </div>
    ) : null;
  },
}));

vi.mock('../components/execution/ExecutionDetailDialog', () => ({
  ExecutionDetailDialog: (props: { open: boolean; executionId: string | null }) => {
    mocks.detailProps(props);
    return null;
  },
}));

describe('AutomationDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.automationJobs = [job as AutomationJob];
    mocks.filter = 'all';
    mocks.search = '';
    mocks.deleteTask.mockResolvedValue(undefined);
    mocks.executeTask.mockResolvedValue(undefined);
  });

  it('preserves the dashboard hierarchy and opens the single execution detail action', async () => {
    render(<AutomationDashboardPage />);

    expect(screen.getByText('automation.dashboard.title')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('automation.dashboard.search.placeholder')).toBeInTheDocument();
    expect(screen.getByText('automation.dashboard.table.title')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', {
      name: 'automation.dashboard.executionCard.viewExecution',
    }));
    expect(mocks.detailProps).toHaveBeenLastCalledWith(expect.objectContaining({
      open: true,
      executionId: 'execution-global',
    }));
  });

  it('opens server-backed history for the selected job', async () => {
    render(<AutomationDashboardPage />);

    await userEvent.click(screen.getByRole('button', { name: 'automation.dashboard.table.viewTask' }));

    expect(mocks.historyProps).toHaveBeenLastCalledWith(expect.objectContaining({
      isOpen: true,
      job: expect.objectContaining({ id: 'job-1' }),
    }));
  });

  it('applies provider search and status filters and wires search input changes', async () => {
    mocks.automationJobs = Array.from({ length: 7 }, (_, index) => createJob({
      id: `job-${index + 1}`,
      name: index === 5 ? 'Needle Paused' : index === 6 ? 'Needle Active' : `Job ${index + 1}`,
      status: index === 5 ? 'paused' : 'active',
    }));
    mocks.filter = 'paused';
    mocks.search = 'needle';

    render(<AutomationDashboardPage />);

    expect(screen.getByText('Needle Paused')).toBeInTheDocument();
    expect(screen.queryByText('Needle Active')).not.toBeInTheDocument();
    expect(screen.queryByText('Job 1')).not.toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText('automation.dashboard.search.placeholder');
    await userEvent.clear(searchInput);
    expect(mocks.setSearch).toHaveBeenLastCalledWith('');
  });

  it('paginates seven provider jobs with six jobs per page', async () => {
    mocks.automationJobs = Array.from({ length: 7 }, (_, index) => createJob({
      id: `job-${index + 1}`,
      name: `Job ${index + 1}`,
    }));

    render(<AutomationDashboardPage />);

    expect(screen.getByText('Job 1')).toBeInTheDocument();
    expect(screen.getByText('Job 6')).toBeInTheDocument();
    expect(screen.queryByText('Job 7')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', {
      name: 'automation.dashboard.pagination.next',
    }));

    expect(await screen.findByText('Job 7')).toBeInTheDocument();
    expect(screen.queryByText('Job 1')).not.toBeInTheDocument();
  });

  it('targets the selected jobs for edit, confirmed delete, and successful execution', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mocks.automationJobs = [
      createJob({ id: 'job-edit', name: 'Edit Target' }),
      createJob({ id: 'job-delete', name: 'Delete Target' }),
      createJob({ id: 'job-run', name: 'Run Target' }),
    ];
    render(<AutomationDashboardPage />);

    const editRow = screen.getByText('Edit Target').closest('tr');
    expect(editRow).not.toBeNull();
    await userEvent.click(within(editRow!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('automation.dashboard.table.edit'));
    expect(mocks.openEditDialog).toHaveBeenCalledWith('job-edit');

    const deleteRow = screen.getByText('Delete Target').closest('tr');
    expect(deleteRow).not.toBeNull();
    await userEvent.click(within(deleteRow!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('automation.dashboard.table.delete'));
    expect(confirm).toHaveBeenCalledWith('automation.dashboard.table.confirmDelete');
    expect(mocks.deleteTask).toHaveBeenCalledWith('job-delete');

    const runRow = screen.getByText('Run Target').closest('tr');
    expect(runRow).not.toBeNull();
    await userEvent.click(within(runRow!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('automation.dashboard.table.runNow'));
    await waitFor(() => expect(mocks.executeTask).toHaveBeenCalledWith('job-run'));
    expect(mocks.toast).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it('shows localized queue-full feedback when a manual run is rejected', async () => {
    mocks.executeTask.mockRejectedValue(
      new ApiError('raw queue message', 409, 'automation_queue_full'),
    );
    render(<AutomationDashboardPage />);

    const row = screen.getByText('Nightly').closest('tr');
    expect(row).not.toBeNull();
    await userEvent.click(within(row!).getAllByRole('button')[1]);
    await userEvent.click(await screen.findByText('automation.dashboard.table.runNow'));

    await waitFor(() => {
      expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({
        variant: 'destructive',
        description: 'automation.errors.automation_queue_full',
      }));
    });
  });
});
