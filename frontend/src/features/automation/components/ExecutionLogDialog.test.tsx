import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  ExecutionLogDialog,
  type ExecutionLogDialogCopy,
  type ExecutionLogDialogExecution,
} from './ExecutionLogDialog';
import type { TaskLog } from '@/shared/types/task';

const execution: ExecutionLogDialogExecution = {
  id: 'exec-1',
  jobId: 'job-1',
  status: 'success',
  trigger: 'manual',
  startedAt: '2026-04-30T03:00:00.000Z',
  finishedAt: '2026-04-30T03:01:00.000Z',
  duration: 60,
  summary: 'Completed nightly backup',
};

const copy: ExecutionLogDialogCopy<ExecutionLogDialogExecution> = {
  description: 'Execution details',
  fields: {
    executionId: 'Execution ID',
    jobId: 'Job ID',
    startedAt: 'Started at',
    finishedAt: 'Finished at',
    trigger: 'Trigger',
    duration: 'Duration',
  },
  statusLabel: status => `status:${status}`,
  formatTrigger: item => `trigger:${item.trigger}`,
  formatDuration: item => `${item.duration} seconds`,
  logs: {
    title: 'Execution logs',
    empty: 'No logs',
    loading: 'Loading logs',
    reload: 'Reload logs',
    filters: {
      all: 'All',
      info: 'Info',
      error: 'Error',
      warning: 'Warning',
      success: 'Success',
    },
  },
};

const logs: TaskLog[] = [
  { timestamp: '2026-04-30T03:00:10.000Z', level: 'INFO', message: 'Started job' },
  { timestamp: '2026-04-30T03:00:20.000Z', level: 'ERROR', message: 'Failed branch skipped' },
  { timestamp: '2026-04-30T03:00:30.000Z', level: 'SUCCESS', message: 'Completed job' },
];

describe('ExecutionLogDialog', () => {
  it('renders execution metadata and filters logs by level', async () => {
    const user = userEvent.setup();
    render(
      <ExecutionLogDialog
        isOpen
        execution={execution}
        onClose={vi.fn()}
        locale="en-US"
        copy={copy}
        createLogs={() => logs}
      />,
    );

    expect(screen.getByText('Completed nightly backup')).toBeInTheDocument();
    expect(screen.getByText('status:success')).toBeInTheDocument();
    expect(screen.getByText('Execution details')).toBeInTheDocument();
    expect(screen.getByText('trigger:manual')).toBeInTheDocument();
    expect(screen.getByText('60 seconds')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Started job')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByRole('combobox'), 'error');

    expect(screen.queryByText('Started job')).not.toBeInTheDocument();
    expect(screen.getByText('Failed branch skipped')).toBeInTheDocument();
  });

  it('reloads logs with the provided log builder', async () => {
    const user = userEvent.setup();
    const createLogs = vi.fn(() => logs);

    render(
      <ExecutionLogDialog
        isOpen
        execution={execution}
        onClose={vi.fn()}
        locale="en-US"
        copy={copy}
        createLogs={createLogs}
      />,
    );

    await waitFor(() => {
      expect(createLogs).toHaveBeenCalledTimes(1);
    });

    await user.click(screen.getByRole('button', { name: /reload logs/i }));

    await waitFor(() => {
      expect(createLogs).toHaveBeenCalledTimes(2);
    });
  });
});
