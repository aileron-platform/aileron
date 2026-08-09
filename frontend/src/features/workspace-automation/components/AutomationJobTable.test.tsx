import { render, screen } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AutomationJob } from '../model/automationTypes';
import { AutomationJobTable } from './AutomationJobTable';

const mocks = vi.hoisted(() => ({
  t: vi.fn((key: string) => key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: mocks.t,
    state: { currentLanguage: 'en-US' },
  }),
}));

const job = {
  id: 'job-1',
  name: 'Nightly',
  description: 'Checks',
  workspaceName: 'Workspace Alpha',
  status: 'active',
  trigger: 'manual',
  nextRunAt: '2026-07-18T00:00:00Z',
  lastRunAt: '2026-07-17T00:00:00Z',
} as AutomationJob;

const callbacks = {
  onPageChange: vi.fn(),
  onViewExecutions: vi.fn(),
  onEdit: vi.fn(),
  onExecute: vi.fn(),
  onDelete: vi.fn(),
};

describe('AutomationJobTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('preserves the global table DOM and value interpolation keys', () => {
    render(
      <AutomationJobTable
        scope="global"
        jobs={[job]}
        page={1}
        totalPages={1}
        totalItems={1}
        pageSize={6}
        {...callbacks}
      />,
    );

    const workspaceName = screen.getByText('Workspace Alpha');
    expect(workspaceName.parentElement).toHaveClass('inline-flex', 'items-center', 'gap-1');
    expect(workspaceName.parentElement?.parentElement).toHaveClass('mt-0.5');

    const status = screen.getByText('automation.dashboard.table.status.active');
    expect(status.parentElement).toHaveClass('space-y-1');

    expect(mocks.t).toHaveBeenCalledWith(
      'automation.dashboard.table.nextRunLabel',
      { value: expect.any(String) },
    );
    expect(mocks.t).toHaveBeenCalledWith(
      'automation.dashboard.table.lastRunLabel',
      { value: expect.any(String) },
    );
    expect(mocks.t).toHaveBeenCalledWith(
      'automation.dashboard.pagination.summary',
      { start: 1, end: 1, total: 1 },
    );
  });

  it('preserves the workspace table DOM and time interpolation keys', () => {
    render(
      <AutomationJobTable
        scope="workspace"
        jobs={[job]}
        page={1}
        totalPages={1}
        totalItems={1}
        pageSize={6}
        locale="zh-TW"
        {...callbacks}
      />,
    );

    expect(screen.queryByText('Workspace Alpha')).not.toBeInTheDocument();

    const status = screen.getByText('workspace.automation.status.active');
    expect(status.parentElement?.tagName).toBe('TD');
    expect(status.parentElement).not.toHaveClass('space-y-1');

    expect(mocks.t).toHaveBeenCalledWith(
      'workspace.automation.table.nextRun',
      { time: expect.any(String) },
    );
    expect(mocks.t).toHaveBeenCalledWith(
      'workspace.automation.table.lastRun',
      { time: expect.any(String) },
    );
    expect(mocks.t).toHaveBeenCalledWith(
      'workspace.automation.pagination.range',
      { start: 1, end: 1, total: 1 },
    );
  });
});
