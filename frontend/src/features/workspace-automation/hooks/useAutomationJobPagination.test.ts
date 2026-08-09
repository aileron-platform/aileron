import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { AutomationJob } from '../model/automationTypes';
import { useAutomationJobPagination } from './useAutomationJobPagination';

const createJob = (id: string): AutomationJob => ({ id }) as AutomationJob;

describe('useAutomationJobPagination', () => {
  it('clamps pages and resets when the filter contract changes', async () => {
    const jobs = Array.from({ length: 7 }, (_, index) => createJob(`job-${index + 1}`));
    const { result, rerender } = renderHook(
      ({ resetKey }) => useAutomationJobPagination(jobs, resetKey),
      { initialProps: { resetKey: 'all:' } },
    );

    act(() => result.current.onPageChange(2));
    expect(result.current.page).toBe(2);
    expect(result.current.paginatedJobs.map(job => job.id)).toEqual(['job-7']);

    rerender({ resetKey: 'paused:' });
    await waitFor(() => expect(result.current.page).toBe(1));
    expect(result.current.pageSize).toBe(6);

    act(() => result.current.onPageChange(99));
    expect(result.current.page).toBe(2);
  });
});
