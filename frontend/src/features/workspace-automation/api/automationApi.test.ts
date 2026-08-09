import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiDeleteMock, apiGetMock, apiPatchMock, apiPostMock } = vi.hoisted(() => ({
  apiDeleteMock: vi.fn(),
  apiGetMock: vi.fn(),
  apiPatchMock: vi.fn(),
  apiPostMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    delete: apiDeleteMock,
    get: apiGetMock,
    patch: apiPatchMock,
    post: apiPostMock,
  },
}));

import { automationApi } from './automationApi';
import type { JobCreateInput, JobUpdateInput } from '../model/automationTypes';

describe('automationApi final contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('runs a job through its encoded route', async () => {
    apiPostMock.mockResolvedValue({ id: 'execution-1' });

    await automationApi.executeJob('job /1');

    expect(apiPostMock).toHaveBeenCalledWith('/automation/jobs/job%20%2F1/run');
  });

  it('gets and deletes a job through encoded routes', async () => {
    apiGetMock.mockResolvedValue({ id: 'job /1' });
    apiDeleteMock.mockResolvedValue(undefined);

    await automationApi.getJob('job /1');
    await automationApi.deleteJob('job /1');

    expect(apiGetMock).toHaveBeenCalledWith('/automation/jobs/job%20%2F1');
    expect(apiDeleteMock).toHaveBeenCalledWith('/automation/jobs/job%20%2F1');
  });

  it('loads job-scoped history and execution detail with encoded identifiers', async () => {
    apiGetMock
      .mockResolvedValueOnce({ items: [], total: 0, page: 2, pageSize: 25 })
      .mockResolvedValueOnce({ id: 'execution-1', status: 'queued' });

    await automationApi.getJobExecutions('job /1', {
      page: 2,
      pageSize: 25,
      rangeStart: '2026-07-15T00:00:00.000Z',
    });
    await automationApi.getExecution('execution /1');

    expect(apiGetMock).toHaveBeenNthCalledWith(
      1,
      '/automation/jobs/job%20%2F1/executions?page=2&pageSize=25&rangeStart=2026-07-15T00%3A00%3A00.000Z'
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/automation/executions/execution%20%2F1'
    );
  });

  it('returns the canonical execution projection from cancel', async () => {
    const canonical = { id: 'execution-1', status: 'running' };
    apiPostMock.mockResolvedValue(canonical);

    await expect(automationApi.cancelExecution('execution /1')).resolves.toBe(canonical);
    expect(apiPostMock).toHaveBeenCalledWith(
      '/automation/executions/execution%20%2F1/cancel'
    );
  });

  it('keeps dashboard reads global and scopes workspace reads with encoded query values', async () => {
    apiGetMock.mockResolvedValue({ items: [], total: 0 });

    await automationApi.listJobs();
    await automationApi.getMetrics();
    await automationApi.getRecentExecutions(10);
    await automationApi.listJobs('workspace /1');
    await automationApi.getMetrics('workspace /1');

    expect(apiGetMock.mock.calls.map(([path]) => path)).toEqual([
      '/automation/jobs',
      '/automation/metrics',
      '/automation/executions?limit=10',
      '/automation/jobs?workspaceId=workspace+%2F1',
      '/automation/metrics?workspaceId=workspace+%2F1',
    ]);
  });

  it('projects create and update bodies onto the public contract', async () => {
    apiPostMock.mockResolvedValue({ id: 'job-1' });
    apiPatchMock.mockResolvedValue({ id: 'job-1' });
    const createPayload = {
      name: 'Nightly',
      description: 'Run checks',
      workspaceId: 'workspace-1',
      prompt: 'Run tests',
      trigger: 'cron',
      schedule: '0 9 * * *',
      exact: false,
      owner: 'legacy owner',
      userId: 'legacy-user',
      notifications: { email: true },
      metadata: { legacy: true },
    } as unknown as JobCreateInput;
    const updatePayload = {
      ...createPayload,
      id: 'job /1',
      status: 'paused',
    } as unknown as JobUpdateInput;

    await automationApi.createJob(createPayload);
    await automationApi.updateJob(updatePayload);

    expect(apiPostMock).toHaveBeenCalledWith('/automation/jobs', {
      name: 'Nightly',
      description: 'Run checks',
      workspaceId: 'workspace-1',
      prompt: 'Run tests',
      trigger: 'cron',
      schedule: '0 9 * * *',
      exact: false,
    });
    expect(apiPatchMock).toHaveBeenCalledWith('/automation/jobs/job%20%2F1', {
      name: 'Nightly',
      description: 'Run checks',
      prompt: 'Run tests',
      status: 'paused',
      trigger: 'cron',
      schedule: '0 9 * * *',
      exact: false,
    });
  });
});
