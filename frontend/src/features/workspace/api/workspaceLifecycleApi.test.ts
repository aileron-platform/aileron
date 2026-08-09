import { beforeEach, describe, expect, it, vi } from 'vitest';

const { deleteMock, getMock, postMock } = vi.hoisted(() => ({
  deleteMock: vi.fn(),
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', async () => {
  const actual = await vi.importActual<typeof import('@/shared/api/apiClient')>(
    '@/shared/api/apiClient',
  );
  return {
    ...actual,
    apiClient: {
      delete: deleteMock,
      get: getMock,
      post: postMock,
    },
  };
});

import { ApiError } from '@/shared/api/apiClient';
import {
  parseWorkspaceAvailabilityResponse,
  workspaceLifecycleApi,
  WorkspaceDeleteJobError,
} from './workspaceLifecycleApi';

const availabilityPayload = (reasonCode: string): unknown => ({
  workspaceId: 'ws-123',
  availability: 'blocked',
  reasonCode,
  runtimeStatus: 'error',
  runtimeInstanceId: null,
  runtimeAccessDesiredRevision: 1,
  runtimeAccessObservedRevision: 1,
  retryable: false,
  allowedActions: [],
  retryAfterMs: null,
  knowledgeMountStatus: {
    status: 'ready',
    desiredRevision: 1,
    observedRevision: 1,
    lastKnownGoodRevision: 1,
    errorCode: null,
    compensating: false,
  },
  deletion: {
    availability: 'blocked',
    allowedActions: ['delete'],
    phase: null,
    status: null,
    errorCode: null,
  },
});

describe('workspaceLifecycleApi', () => {
  beforeEach(() => {
    deleteMock.mockReset();
    getMock.mockReset();
    postMock.mockReset();
  });

  it('parses execution plane drift as a fail-closed availability response', () => {
    expect(parseWorkspaceAvailabilityResponse(
      availabilityPayload('WORKSPACE_EXECUTION_PLANE_DRIFT'),
    )).toMatchObject({
      availability: 'blocked',
      reasonCode: 'WORKSPACE_EXECUTION_PLANE_DRIFT',
      allowedActions: [],
    });
  });

  it('rejects availability responses with an unknown reason code', () => {
    expect(() => parseWorkspaceAvailabilityResponse(
      availabilityPayload('WORKSPACE_UNKNOWN_STATE'),
    )).toThrow('workspace_availability_contract_invalid');
  });

  it('maps deleteWorkspace to the delete endpoint', async () => {
    deleteMock.mockResolvedValue({ status: 'deleting' });

    await workspaceLifecycleApi.deleteWorkspace('ws/123', 'Workspace 123');

    expect(deleteMock).toHaveBeenCalledWith(
      '/workspaces/ws%2F123',
      undefined,
      { confirmationName: 'Workspace 123' },
    );
  });

  it('maps availability reads and authorized actions to control-plane endpoints', async () => {
    getMock.mockResolvedValue(availabilityPayload('WORKSPACE_EXECUTION_PLANE_DRIFT'));
    postMock.mockResolvedValue({
      workspaceId: 'ws/123',
      action: 'retry',
      jobId: 'job-1',
      status: 'queued',
      reasonCode: 'WORKSPACE_RUNTIME_RECOVERY_QUEUED',
    });

    await workspaceLifecycleApi.getAvailability('ws/123');
    await expect(
      workspaceLifecycleApi.runAvailabilityAction('ws/123', 'retry'),
    ).resolves.toEqual({
      workspaceId: 'ws/123',
      action: 'retry',
      jobId: 'job-1',
      status: 'queued',
      reasonCode: 'WORKSPACE_RUNTIME_RECOVERY_QUEUED',
    });

    expect(getMock).toHaveBeenCalledWith(
      '/workspaces/ws%2F123/availability',
      { signal: undefined },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/workspaces/ws%2F123/availability/actions/retry',
    );
  });

  it('maps workspace stop to the workspace lifecycle endpoint', async () => {
    postMock.mockResolvedValue({
      workspaceId: 'ws/123',
      status: 'stopping',
      jobId: 'job-stop-1',
      correlationId: 'correlation-1',
      rootCorrelationId: 'correlation-1',
    });

    await workspaceLifecycleApi.stopWorkspace('ws/123');

    expect(postMock).toHaveBeenCalledWith('/workspaces/ws%2F123/stop');
  });

  it('polls the accepted job until the workspace is absent', async () => {
    getMock
      .mockResolvedValueOnce({
        runtimeJob: {
          id: 'job-1',
          status: 'running',
        },
      })
      .mockRejectedValueOnce(new ApiError('not found', 404));

    await expect(
      workspaceLifecycleApi.waitForWorkspaceDeletion('ws/123', 'job-1', {
        pollIntervalMs: 0,
        timeoutMs: 1_000,
      }),
    ).resolves.toBeUndefined();

    expect(getMock).toHaveBeenCalledTimes(2);
    expect(getMock).toHaveBeenNthCalledWith(1, '/workspaces/ws%2F123');
    expect(getMock).toHaveBeenNthCalledWith(2, '/workspaces/ws%2F123');
  });

  it('reports backend deletion phases while polling and can discover an existing job', async () => {
    const onProgress = vi.fn();
    getMock
      .mockResolvedValueOnce({
        runtimeJob: {
          id: 'job-1',
          operation: 'workspace_delete',
          status: 'running',
          phase: 'stopping_runtime',
        },
      })
      .mockRejectedValueOnce(new ApiError('not found', 404));

    await expect(
      workspaceLifecycleApi.waitForWorkspaceDeletion('ws-123', undefined, {
        pollIntervalMs: 0,
        timeoutMs: 1_000,
        onProgress,
      }),
    ).resolves.toBeUndefined();

    expect(onProgress).toHaveBeenCalledWith({
      jobId: 'job-1',
      status: 'running',
      phase: 'stopping_runtime',
      errorCode: null,
    });
  });

  it('resolves when the backend reports a succeeded deletion job', async () => {
    getMock
      .mockResolvedValueOnce({
        runtimeJob: {
          id: 'job-1',
          operation: 'workspace_delete',
          status: 'succeeded',
          phase: 'finalizing',
        },
      })
      .mockRejectedValueOnce(new ApiError('not found', 404));

    await expect(
      workspaceLifecycleApi.waitForWorkspaceDeletion('ws-123', 'job-1', {
        pollIntervalMs: 0,
        timeoutMs: 1_000,
      }),
    ).resolves.toBeUndefined();

    expect(getMock).toHaveBeenCalledTimes(2);
  });

  it('reads the current workspace deletion job without starting a polling loop', async () => {
    getMock.mockResolvedValue({
      runtimeJob: {
        id: 'job-1',
        operation: 'workspace_delete',
        status: 'failed',
        phase: 'deleting_resources',
        errorCode: 'WORKSPACE_DELETE_FAILED',
      },
    });

    await expect(
      workspaceLifecycleApi.getWorkspaceDeletionStatus('ws-123'),
    ).resolves.toEqual({
      runtimeJob: {
        id: 'job-1',
        operation: 'workspace_delete',
        status: 'failed',
        phase: 'deleting_resources',
        errorCode: 'WORKSPACE_DELETE_FAILED',
      },
    });
    expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
  });

  it('fails when the accepted delete job reports failed', async () => {
    getMock.mockResolvedValue({
      runtimeJob: {
        id: 'job-1',
        status: 'failed',
        errorCode: 'WORKSPACE_DELETE_FAILED',
      },
    });

    await expect(
      workspaceLifecycleApi.waitForWorkspaceDeletion('ws-123', 'job-1', {
        pollIntervalMs: 0,
        timeoutMs: 10,
      }),
    ).rejects.toMatchObject<WorkspaceDeleteJobError>({
      name: 'WorkspaceDeleteJobError',
      errorCode: 'WORKSPACE_DELETE_FAILED',
    });
  });

  it('maps component restart actions to component-scoped endpoints', async () => {
    postMock.mockResolvedValue({ status: 'restarting' });

    await workspaceLifecycleApi.restartComponent('ws/123', 'runtime');
    await workspaceLifecycleApi.restartComponent('ws-123', 'browser');
    await workspaceLifecycleApi.restartComponent('ws-123', 'canvas');

    expect(postMock).toHaveBeenNthCalledWith(1, '/workspaces/ws%2F123/components/runtime/restart');
    expect(postMock).toHaveBeenNthCalledWith(2, '/workspaces/ws-123/components/browser/restart');
    expect(postMock).toHaveBeenNthCalledWith(3, '/workspaces/ws-123/components/canvas/restart');
  });

  it('maps Browser credential access and rotation endpoints', async () => {
    postMock.mockResolvedValue({});

    await workspaceLifecycleApi.accessBrowser('ws/123');
    await workspaceLifecycleApi.rotateBrowserCredentials('ws/123');

    expect(postMock).toHaveBeenNthCalledWith(
      1,
      '/workspaces/ws%2F123/browser/access',
    );
    expect(postMock).toHaveBeenNthCalledWith(
      2,
      '/workspaces/ws%2F123/browser/credentials/rotate',
    );
  });
});
