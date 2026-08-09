import { act, renderHook, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  WorkspaceDeleteTimeoutError,
} from '../api/workspaceLifecycleApi';
import { useWorkspaceDeletion } from './useWorkspaceDeletion';

const {
  deleteWorkspaceMock,
  getWorkspaceDeletionStatusMock,
  waitForWorkspaceDeletionMock,
  resolveDeleteFallbackMock,
  toastMock,
} = vi.hoisted(() => ({
  deleteWorkspaceMock: vi.fn(),
  getWorkspaceDeletionStatusMock: vi.fn(),
  waitForWorkspaceDeletionMock: vi.fn(),
  resolveDeleteFallbackMock: vi.fn(),
  toastMock: vi.fn(),
}));

vi.mock('../api/workspaceLifecycleApi', async () => {
  const actual = await vi.importActual<typeof import('../api/workspaceLifecycleApi')>(
    '../api/workspaceLifecycleApi',
  );
  return {
    ...actual,
    workspaceLifecycleApi: {
      ...actual.workspaceLifecycleApi,
      deleteWorkspace: deleteWorkspaceMock,
      getWorkspaceDeletionStatus: getWorkspaceDeletionStatusMock,
      waitForWorkspaceDeletion: waitForWorkspaceDeletionMock,
    },
  };
});

vi.mock('../hooks/useWorkspaceDeleteFallback', () => ({
  useWorkspaceDeleteFallback: () => resolveDeleteFallbackMock,
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe('useWorkspaceDeletion', () => {
  beforeEach(() => {
    deleteWorkspaceMock.mockReset();
    getWorkspaceDeletionStatusMock.mockReset();
    waitForWorkspaceDeletionMock.mockReset();
    resolveDeleteFallbackMock.mockReset();
    toastMock.mockReset();
    getWorkspaceDeletionStatusMock.mockResolvedValue({ runtimeJob: null });
    resolveDeleteFallbackMock.mockResolvedValue({
      fallbackWorkspaceId: 'ws-2',
      workspaceList: { items: [{ id: 'ws-2' }] },
    });
  });

  it('submits one delete intent, follows the accepted job, and only finalizes after completion', async () => {
    deleteWorkspaceMock.mockResolvedValue({
      workspaceId: 'ws-1',
      status: 'deleting',
      jobId: 'job-1',
      correlationId: 'correlation-1',
      rootCorrelationId: 'correlation-1',
    });
    waitForWorkspaceDeletionMock.mockImplementation(async (_workspaceId, _jobId, options) => {
      options?.onProgress?.({
        jobId: 'job-1',
        status: 'running',
        phase: 'cancelling_automations',
        errorCode: null,
      });
    });

    const { result } = renderHook(() => useWorkspaceDeletion({
      workspaceId: 'ws-1',
      workspaceName: 'Workspace One',
      runtimeBaseUrl: 'http://runtime.test',
      canDelete: true,
      shouldDiscoverExistingJob: false,
      isDeletionInProgress: false,
    }));

    let accepted = false;
    await act(async () => {
      accepted = await result.current.requestDelete('Workspace One');
    });

    expect(accepted).toBe(true);
    expect(deleteWorkspaceMock).toHaveBeenCalledTimes(1);
    expect(waitForWorkspaceDeletionMock).toHaveBeenCalledWith(
      'ws-1',
      'job-1',
      expect.objectContaining({ onProgress: expect.any(Function) }),
    );
    await waitFor(() => {
      expect(resolveDeleteFallbackMock).toHaveBeenCalledWith({
        deletedWorkspaceId: 'ws-1',
        deletedRuntimeBaseUrl: 'http://runtime.test',
      });
    });
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      title: 'workspace.workspaceSettings.reset.delete.success.title',
    }));
  });

  it('keeps the workspace available for a retry after timeout and reuses the confirmation seam', async () => {
    deleteWorkspaceMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        status: 'deleting',
        jobId: 'job-1',
        correlationId: 'correlation-1',
        rootCorrelationId: 'correlation-1',
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        status: 'deleting',
        jobId: 'job-2',
        correlationId: 'correlation-2',
        rootCorrelationId: 'correlation-2',
      });
    waitForWorkspaceDeletionMock
      .mockRejectedValueOnce(new WorkspaceDeleteTimeoutError())
      .mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useWorkspaceDeletion({
      workspaceId: 'ws-1',
      workspaceName: 'Workspace One',
      runtimeBaseUrl: null,
      canDelete: true,
      shouldDiscoverExistingJob: false,
      isDeletionInProgress: false,
    }));

    await act(async () => {
      await result.current.requestDelete('Workspace One');
    });
    await waitFor(() => {
      expect(result.current.progress?.status).toBe('failed');
    });
    expect(resolveDeleteFallbackMock).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.requestDelete('Workspace One');
    });
    await waitFor(() => {
      expect(resolveDeleteFallbackMock).toHaveBeenCalledTimes(1);
    });
    expect(deleteWorkspaceMock).toHaveBeenCalledTimes(2);
  });

  it('rejects a duplicate click before the accepted job is returned', async () => {
    deleteWorkspaceMock.mockResolvedValue({
      workspaceId: 'ws-1',
      status: 'deleting',
      jobId: 'job-1',
      correlationId: 'correlation-1',
      rootCorrelationId: 'correlation-1',
    });
    waitForWorkspaceDeletionMock.mockResolvedValue(undefined);

    const { result } = renderHook(() => useWorkspaceDeletion({
      workspaceId: 'ws-1',
      workspaceName: 'Workspace One',
      runtimeBaseUrl: null,
      canDelete: true,
      shouldDiscoverExistingJob: false,
      isDeletionInProgress: false,
    }));

    let responses: [boolean, boolean] = [false, false];
    await act(async () => {
      const first = result.current.requestDelete('Workspace One');
      const second = result.current.requestDelete('Workspace One');
      responses = await Promise.all([first, second]);
    });

    expect(responses).toEqual([true, false]);
    expect(deleteWorkspaceMock).toHaveBeenCalledTimes(1);
  });

  it('recovers an existing failed deletion job after a gate reload without creating a new request', async () => {
    getWorkspaceDeletionStatusMock.mockResolvedValue({
      runtimeJob: {
        id: 'job-1',
        operation: 'workspace_delete',
        status: 'failed',
        phase: 'deleting_resources',
        errorCode: 'WORKSPACE_DELETE_FAILED',
      },
    });

    const { result } = renderHook(() => useWorkspaceDeletion({
      workspaceId: 'ws-1',
      workspaceName: 'Workspace One',
      runtimeBaseUrl: null,
      canDelete: true,
      shouldDiscoverExistingJob: true,
      isDeletionInProgress: false,
    }));

    await waitFor(() => {
      expect(result.current.progress).toMatchObject({
        status: 'failed',
        phase: 'deleting_resources',
        jobId: 'job-1',
      });
    });
    expect(deleteWorkspaceMock).not.toHaveBeenCalled();
    expect(waitForWorkspaceDeletionMock).not.toHaveBeenCalled();
  });
});
