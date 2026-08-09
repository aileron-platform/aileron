import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkspaceWizard } from './useWorkspaceWizard';

const { createWorkspaceMock, getMock, startWorkspaceMock } = vi.hoisted(() => ({
  createWorkspaceMock: vi.fn(),
  getMock: vi.fn(),
  startWorkspaceMock: vi.fn(),
}));

vi.mock('../services/workspaceWizardService', () => ({
  workspaceWizardService: {
    createWorkspace: createWorkspaceMock,
    startWorkspace: startWorkspaceMock,
  },
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: getMock,
  },
}));

describe('useWorkspaceWizard', () => {
  beforeEach(() => {
    createWorkspaceMock.mockReset();
    getMock.mockReset();
    startWorkspaceMock.mockReset();
    createWorkspaceMock.mockResolvedValue({ workspaceId: 'workspace-1' });
    startWorkspaceMock.mockResolvedValue({
      workspaceId: 'workspace-1',
      status: 'queued',
      jobId: 'job-2',
    });
  });

  it('stops polling on provisioning failure and starts a new lifecycle job on retry', async () => {
    getMock
      .mockResolvedValueOnce({
        runtimeStatus: { status: 'error' },
        bootstrap: { phase: 'error' },
        components: {
          runtime: { phase: 'error' },
          browser: { phase: 'error' },
          canvas: { phase: 'error' },
        },
        runtimeJob: { status: 'failed' },
      })
      .mockResolvedValue({ runtimeStatus: { status: 'running' } });
    const { result } = renderHook(() => useWorkspaceWizard());

    await act(async () => {
      await result.current.submitRuntimeConfig();
    });

    await waitFor(() => {
      expect(result.current.state.createdWorkspaceId).toBe('workspace-1');
      expect(result.current.state.isPolling).toBe(false);
      expect(result.current.state.error).toBe('error.provisionWorkspace');
    });

    await act(async () => {
      await result.current.retryWorkspaceCreation();
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(2);
      expect(result.current.state.error).toBeNull();
    });

    expect(createWorkspaceMock).toHaveBeenCalledTimes(1);
    expect(startWorkspaceMock).toHaveBeenCalledTimes(1);
    expect(startWorkspaceMock).toHaveBeenCalledWith('workspace-1');
    expect(result.current.state.createdWorkspaceId).toBe('workspace-1');
  });

  it('shows a terminal error when retry cannot enqueue a start job', async () => {
    getMock.mockResolvedValue({
      runtimeStatus: { status: 'error' },
      runtimeJob: { status: 'failed' },
    });
    startWorkspaceMock.mockRejectedValue(new Error('request failed'));
    const { result } = renderHook(() => useWorkspaceWizard());

    await act(async () => {
      await result.current.submitRuntimeConfig();
    });
    await waitFor(() => {
      expect(result.current.state.error).toBe('error.provisionWorkspace');
    });

    await act(async () => {
      await result.current.retryWorkspaceCreation();
    });

    expect(result.current.state.isPolling).toBe(false);
    expect(result.current.state.error).toBe('error.retryWorkspace');
    expect(getMock).toHaveBeenCalledTimes(1);
  });
});
