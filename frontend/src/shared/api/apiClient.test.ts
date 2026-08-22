import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiClient,
  ApiError,
  registerCsrfTokenProvider,
  registerExecutionGrantProvider,
  registerExecutionGrantRejectionHandler,
  registerLanguageProvider,
  subscribeApiError,
} from './apiClient';
import { managerSessionRecovery } from '../auth/ManagerSessionRecovery';

describe('ApiClient', () => {
  beforeEach(() => {
    registerCsrfTokenProvider(null);
    registerExecutionGrantProvider(null);
    registerExecutionGrantRejectionHandler(null);
    registerLanguageProvider(null);
    managerSessionRecovery.reset();
    window.location.pathname = '/';
    window.location.search = '';
    window.location.hash = '';
  });

  afterEach(() => vi.restoreAllMocks());

  it('normalizes a complete API root without duplicating the prefix', () => {
    const client = new ApiClient({ baseUrl: 'https://runtime.example/api/v1/' });

    expect(client.buildUrl('/files/tree')).toBe(
      'https://runtime.example/api/v1/files/tree',
    );
  });

  it('sends cookies and the in-memory CSRF token for manager mutations', async () => {
    registerCsrfTokenProvider(() => 'csrf-secret');
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    const client = new ApiClient({ baseUrl: 'https://manager.example/api/v1' });

    await client.post('/workspaces', { name: 'demo' });

    expect(fetchMock).toHaveBeenCalledWith(
      'https://manager.example/api/v1/workspaces',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-secret' }),
      }),
    );
  });

  it('does not attach CSRF to safe requests', async () => {
    registerCsrfTokenProvider(() => 'csrf-secret');
    const client = new ApiClient();

    const headers = await client.getRequestHeaders({ method: 'GET' });

    expect(headers).not.toHaveProperty('X-CSRF-Token');
  });

  it('obtains an audience-bound execution grant for Runtime requests', async () => {
    const grantProvider = vi.fn().mockResolvedValue('signed-grant');
    registerExecutionGrantProvider(grantProvider);
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const client = new ApiClient({
      baseUrl: 'https://runtime.example/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });

    await client.get('/files/tree');

    expect(grantProvider).toHaveBeenCalledWith({
      targetUrl: 'https://runtime.example/api/v1',
      method: 'GET',
      path: '/files/tree',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      'https://runtime.example/api/v1/files/tree',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({ Authorization: 'Bearer signed-grant' }),
      }),
    );
  });

  it('hands a parsed Manager Session failure to recovery with the complete return target', async () => {
    window.location.pathname = '/workspaces/workspace-1/files';
    window.location.search = '?tab=changes';
    window.location.hash = '#diff';
    const recover = vi.spyOn(managerSessionRecovery, 'handle').mockReturnValue(true);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        detail: { errorCode: 'MANAGER_SESSION_REQUIRED' },
      }), { status: 401 }),
    );
    const client = new ApiClient();

    await expect(client.get('/workspaces')).rejects.toBeInstanceOf(ApiError);

    expect(recover).toHaveBeenCalledWith(
      401,
      'MANAGER_SESSION_REQUIRED',
      '/workspaces/workspace-1/files?tab=changes#diff',
    );
  });

  it.each([
    [401, 'PLATFORM_AUTHORIZATION_DENIED'],
    [403, 'PLATFORM_AUTHORIZATION_DENIED'],
    [403, 'MANAGER_SESSION_ORIGIN_INVALID'],
    [403, 'MANAGER_SESSION_CSRF_INVALID'],
    [401, 'WORKSPACE_RUNTIME_ACCESS_DENIED'],
    [503, 'WORKSPACE_RUNTIME_UNAVAILABLE'],
  ])('does not hand HTTP %s with %s to Manager Session recovery', async (status, errorCode) => {
    const recover = vi.spyOn(managerSessionRecovery, 'handle');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: { errorCode } }), { status }),
    );
    const client = new ApiClient();

    await expect(client.get('/workspaces')).rejects.toMatchObject({ status, errorCode });

    expect(recover).not.toHaveBeenCalled();
  });

  it('does not hand a Runtime grant rejection to Manager Session recovery', async () => {
    const recover = vi.spyOn(managerSessionRecovery, 'handle');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        detail: { errorCode: 'MANAGER_SESSION_REQUIRED' },
      }), { status: 401 }),
    );
    const client = new ApiClient({ unauthorizedBehavior: 'propagate' });

    await expect(client.get('/threads')).rejects.toMatchObject({ status: 401 });

    expect(recover).not.toHaveBeenCalled();
  });

  it('parses a Blob error before handing a Manager Session failure to recovery', async () => {
    const recover = vi.spyOn(managerSessionRecovery, 'handle').mockReturnValue(true);
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        detail: { errorCode: 'MANAGER_SESSION_REQUIRED' },
      }), { status: 401 }),
    );
    const client = new ApiClient();

    await expect(client.getBlob('/exports/report')).rejects.toMatchObject({
      status: 401,
      errorCode: 'MANAGER_SESSION_REQUIRED',
    });
    expect(recover).toHaveBeenCalledTimes(1);
  });

  it('preserves structured authorization metadata and publishes it', async () => {
    const listener = vi.fn();
    const unsubscribe = subscribeApiError(listener);
    const response = new Response(JSON.stringify({
      detail: {
        errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH',
        message: 'stale generation',
      },
    }), { status: 423 });

    try {
      await expect(
        (new ApiClient() as unknown as { handleResponse: (value: Response) => Promise<never> })
          .handleResponse(response),
      ).rejects.toMatchObject({
        status: 423,
        errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH',
      });
      expect(listener).toHaveBeenCalledWith({
        status: 423,
        errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH',
        responseUrl: '',
      });
    } finally {
      unsubscribe();
    }
  });

  it('preserves Runtime operation metadata from a FastAPI detail envelope', async () => {
    const operationStatus = {
      isActive: true,
      operation: 'changes.numstat',
      actorDisplayName: 'Another user',
      startedAt: '2026-08-12T08:15:30+00:00',
      blockingScope: 'common_repository',
      stale: false,
      retryable: true,
      progressCurrent: 2,
      progressTotal: 5,
      phase: 'reading-index',
      cancellable: true,
      cancelRequested: false,
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        detail: {
          errorCode: 'VC_OPERATION_IN_PROGRESS',
          messageKey: 'VC_OPERATION_IN_PROGRESS',
          blockingScope: 'common_repository',
          operationStatus,
          stale: false,
          canForceUnlock: false,
        },
      }), { status: 409 }),
    );

    await expect(new ApiClient().get('/version-control/changes/numstat'))
      .rejects.toMatchObject({
        status: 409,
        errorCode: 'VC_OPERATION_IN_PROGRESS',
        messageKey: 'VC_OPERATION_IN_PROGRESS',
        blockingScope: 'common_repository',
        operationStatus,
        stale: false,
        canForceUnlock: false,
      });
  });

  it.each([
    ['string retryable', { retryable: 'true' }],
    ['nested retryable', { retryable: { value: true } }],
  ])('does not trust malformed Runtime operation metadata: %s', async (_label, override) => {
    const operationStatus = {
      isActive: true,
      operation: 'changes.numstat',
      actorDisplayName: null,
      startedAt: '2026-08-12T08:15:30+00:00',
      blockingScope: 'working_tree_target',
      stale: false,
      retryable: true,
      progressCurrent: 0,
      progressTotal: 0,
      phase: '',
      cancellable: false,
      cancelRequested: false,
      ...override,
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        detail: {
          errorCode: 'VC_OPERATION_IN_PROGRESS',
          messageKey: 'VC_OPERATION_IN_PROGRESS',
          blockingScope: 'not-a-scope',
          operationStatus,
          stale: 'false',
          canForceUnlock: 1,
        },
      }), { status: 409 }),
    );

    let caught: unknown;
    try {
      await new ApiClient().get('/version-control/changes/numstat');
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect(caught).toMatchObject({
      messageKey: 'VC_OPERATION_IN_PROGRESS',
      blockingScope: undefined,
      operationStatus: undefined,
      stale: undefined,
      canForceUnlock: undefined,
    });
  });

  it('reissues an Execution Grant once after a runtime generation mismatch', async () => {
    const grants = vi.fn()
      .mockResolvedValueOnce('stale-grant')
      .mockResolvedValueOnce('fresh-grant');
    const rejectGrant = vi.fn().mockReturnValue(true);
    registerExecutionGrantProvider(grants);
    registerExecutionGrantRejectionHandler(rejectGrant);
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { errorCode: 'WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH' },
      }), { status: 423 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const client = new ApiClient({
      baseUrl: 'https://runtime.example/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });

    await expect(client.get('/files/tree')).resolves.toEqual({ ok: true });

    expect(rejectGrant).toHaveBeenCalledTimes(1);
    expect(grants).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer fresh-grant' }),
    }));
  });

  it('never retries an Execution Grant rejection more than once', async () => {
    const grants = vi.fn()
      .mockResolvedValueOnce('stale-grant')
      .mockResolvedValueOnce('still-stale-grant');
    registerExecutionGrantProvider(grants);
    registerExecutionGrantRejectionHandler(vi.fn().mockReturnValue(true));
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({
      detail: { errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH' },
    }), { status: 423 }));
    const client = new ApiClient({
      baseUrl: 'https://runtime.example/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });

    await expect(client.get('/files/tree')).rejects.toMatchObject({
      errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH',
    });
    expect(grants).toHaveBeenCalledTimes(2);
  });

  it('reissues an Execution Grant once for a Blob request after a generation mismatch', async () => {
    const grants = vi.fn()
      .mockResolvedValueOnce('stale-blob-grant')
      .mockResolvedValueOnce('fresh-blob-grant');
    const rejectGrant = vi.fn().mockReturnValue(true);
    registerExecutionGrantProvider(grants);
    registerExecutionGrantRejectionHandler(rejectGrant);
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { errorCode: 'WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH' },
      }), { status: 423 }))
      .mockResolvedValueOnce(new Response('fresh image', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      }));
    const client = new ApiClient({
      baseUrl: 'https://runtime.example/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });

    const blob = await client.getBlob('/skills/content?path=logo.png&raw=true');

    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBe(new Blob(['fresh image']).size);
    expect(blob.type).toBe('image/png');
    expect(rejectGrant).toHaveBeenCalledTimes(1);
    expect(grants).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer fresh-blob-grant' }),
    }));
  });

  it('does not retry a Blob execution-grant rejection more than once', async () => {
    const grants = vi.fn()
      .mockResolvedValueOnce('stale-blob-grant')
      .mockResolvedValueOnce('still-stale-blob-grant');
    const rejectGrant = vi.fn().mockReturnValue(true);
    registerExecutionGrantProvider(grants);
    registerExecutionGrantRejectionHandler(rejectGrant);
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { errorCode: 'WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH' },
      }), { status: 423 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        detail: { errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH' },
      }), { status: 423 }));
    const client = new ApiClient({
      baseUrl: 'https://runtime.example/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });

    await expect(client.getBlob('/skills/content?path=logo.png&raw=true'))
      .rejects.toMatchObject({
        status: 423,
        errorCode: 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH',
      });
    expect(rejectGrant).toHaveBeenCalledTimes(1);
    expect(grants).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('adds the selected language without overriding an explicit header', async () => {
    registerLanguageProvider(() => 'en');
    const client = new ApiClient();

    await expect(client.getRequestHeaders()).resolves.toMatchObject({
      'X-Language': 'en',
    });
    await expect(client.getRequestHeaders({ headers: { 'X-Language': 'zh-TW' } }))
      .resolves.toMatchObject({ 'X-Language': 'zh-TW' });
  });
});
