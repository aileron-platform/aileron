import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '@/shared/api/apiClient';
import { AUTHORIZATION_ERROR_CODES } from '@/shared/authorization/authorizationErrorCodes';
import { executionGrantBroker } from './ExecutionGrantBroker';
import { managerSessionService } from './ManagerSessionService';
import { managerSessionRecovery } from '@/shared/auth/ManagerSessionRecovery';

const setManagerCsrfToken = (csrfToken: string): void => {
  Object.defineProperty(managerSessionService, 'csrfToken', {
    configurable: true,
    value: csrfToken,
    writable: true,
  });
};

const availabilityResponse = (runtimeInstanceId: string) => new Response(JSON.stringify({
  runtimeInstanceId,
  runtimeAccessDesiredRevision: 7,
}), { status: 200 });

const grantResponse = (grant: string) => new Response(JSON.stringify({
  grant,
  expiresIn: 60,
}), { status: 200 });

const managerErrorResponse = (status: number, errorCode: string) => new Response(JSON.stringify({
  detail: {
    errorCode,
    message: 'manager.request.rejected',
    details: {},
  },
}), { status });

const sessionResponse = (csrfToken: string) => new Response(JSON.stringify({
  user: {
    id: 'user-1',
    subject: 'oidc-subject-1',
    username: 'nova',
    email: null,
    display_name: null,
    platform_role: 'member',
    allowed_operations: [],
  },
  csrf_token: csrfToken,
  absolute_expires_at: '2026-08-12T08:00:00Z',
}), { status: 200 });

describe('ExecutionGrantBroker', () => {
  beforeEach(() => {
    managerSessionService.clear();
    vi.restoreAllMocks();
  });

  it('checks availability before reusing a grant for the same runtime generation', async () => {
    vi.spyOn(managerSessionService, 'bootstrap').mockImplementation(async () => {
      Object.defineProperty(managerSessionService, 'csrfToken', {
        configurable: true,
        value: 'csrf-1',
        writable: true,
      });
      return null;
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        runtimeInstanceId: 'runtime-1',
        runtimeAccessDesiredRevision: 7,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        grant: 'grant-1', expiresIn: 60,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        runtimeInstanceId: 'runtime-1',
        runtimeAccessDesiredRevision: 7,
      }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const first = await executionGrantBroker.getGrant(
      'https://terminal.example.test', 'workspace-terminal', 'terminal', 'workspace-1',
    );
    const second = await executionGrantBroker.getGrant(
      'https://terminal.example.test', 'workspace-terminal', 'terminal', 'workspace-1',
    );

    expect(first).toBe('grant-1');
    expect(second).toBe('grant-1');
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('does not reuse a grant after runtime instance or access revision changes', async () => {
    Object.defineProperty(managerSessionService, 'csrfToken', {
      configurable: true,
      value: 'csrf-1',
      writable: true,
    });
    const availability = (runtimeInstanceId: string, runtimeAccessDesiredRevision: number) => (
      new Response(JSON.stringify({ runtimeInstanceId, runtimeAccessDesiredRevision }), { status: 200 })
    );
    const grant = (value: string) => new Response(JSON.stringify({
      grant: value,
      expiresIn: 60,
    }), { status: 200 });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(availability('runtime-1', 7))
      .mockResolvedValueOnce(grant('grant-1'))
      .mockResolvedValueOnce(availability('runtime-2', 7))
      .mockResolvedValueOnce(grant('grant-2'))
      .mockResolvedValueOnce(availability('runtime-2', 8))
      .mockResolvedValueOnce(grant('grant-3'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(executionGrantBroker.getGrant(
      'https://runtime-generation.test', 'workspace-runtime', 'runtime_read', 'workspace-generation',
    )).resolves.toBe('grant-1');
    await expect(executionGrantBroker.getGrant(
      'https://runtime-generation.test', 'workspace-runtime', 'runtime_read', 'workspace-generation',
    )).resolves.toBe('grant-2');
    await expect(executionGrantBroker.getGrant(
      'https://runtime-generation.test', 'workspace-runtime', 'runtime_read', 'workspace-generation',
    )).resolves.toBe('grant-3');

    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it('refreshes stale Manager CSRF evidence once and rebuilds grant headers', async () => {
    setManagerCsrfToken('csrf-stale');
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(availabilityResponse('runtime-csrf-refresh'))
      .mockResolvedValueOnce(managerErrorResponse(
        403,
        AUTHORIZATION_ERROR_CODES.managerSessionCsrfInvalid,
      ))
      .mockResolvedValueOnce(sessionResponse('csrf-current'))
      .mockResolvedValueOnce(grantResponse('grant-after-refresh'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(executionGrantBroker.getGrant(
      'https://csrf-refresh.test',
      'workspace-runtime',
      'runtime_write',
      'workspace-csrf-refresh',
    )).resolves.toBe('grant-after-refresh');

    expect(bootstrap).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('/execution-grants'),
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-stale' }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      expect.stringContaining('/execution-grants'),
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-current' }),
      }),
    );
  });

  it('bounds CSRF recovery when the retried grant request is also rejected', async () => {
    setManagerCsrfToken('csrf-stale-second-failure');
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(availabilityResponse('runtime-csrf-second-failure'))
      .mockResolvedValueOnce(managerErrorResponse(
        403,
        AUTHORIZATION_ERROR_CODES.managerSessionCsrfInvalid,
      ))
      .mockResolvedValueOnce(sessionResponse('csrf-current-second-failure'))
      .mockResolvedValueOnce(managerErrorResponse(
        403,
        AUTHORIZATION_ERROR_CODES.managerSessionCsrfInvalid,
      ));
    vi.stubGlobal('fetch', fetchMock);

    await expect(executionGrantBroker.getGrant(
      'https://csrf-second-failure.test',
      'workspace-runtime',
      'runtime_write',
      'workspace-csrf-second-failure',
    )).rejects.toMatchObject({
      status: 403,
      errorCode: AUTHORIZATION_ERROR_CODES.managerSessionCsrfInvalid,
    });

    expect(bootstrap).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it('coalesces stale-CSRF bootstrap across concurrent grant issuances', async () => {
    setManagerCsrfToken('csrf-stale-concurrent');
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap');
    let releaseStaleRequests = (): void => {};
    const staleRequestsReady = new Promise<void>((resolve) => {
      releaseStaleRequests = resolve;
    });
    let staleRequestCount = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/availability')) {
        return availabilityResponse(`runtime-${url.includes('concurrent-a') ? 'a' : 'b'}`);
      }
      if (url.endsWith('/oauth2/session')) return sessionResponse('csrf-current-concurrent');
      if (url.includes('/execution-grants')) {
        const headers = init?.headers as Record<string, string> | undefined;
        if (headers?.['X-CSRF-Token'] === 'csrf-stale-concurrent') {
          staleRequestCount += 1;
          if (staleRequestCount === 2) releaseStaleRequests();
          await staleRequestsReady;
          return managerErrorResponse(
            403,
            AUTHORIZATION_ERROR_CODES.managerSessionCsrfInvalid,
          );
        }
        return grantResponse(url.includes('concurrent-a') ? 'grant-a' : 'grant-b');
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(Promise.all([
      executionGrantBroker.getGrant(
        'https://concurrent-a.test',
        'workspace-runtime',
        'runtime_write',
        'workspace-concurrent-a',
      ),
      executionGrantBroker.getGrant(
        'https://concurrent-b.test',
        'workspace-runtime',
        'runtime_write',
        'workspace-concurrent-b',
      ),
    ])).resolves.toEqual(['grant-a', 'grant-b']);

    expect(staleRequestCount).toBe(2);
    expect(bootstrap).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(7);
  });

  it.each([
    ['an unrelated 403', 403, 'UNRELATED_FORBIDDEN'],
    ['an origin failure', 403, AUTHORIZATION_ERROR_CODES.managerSessionOriginInvalid],
    ['an authorization denial', 403, AUTHORIZATION_ERROR_CODES.platformAuthorizationDenied],
    ['a Manager 401', 401, AUTHORIZATION_ERROR_CODES.managerSessionRequired],
  ])('does not refresh CSRF evidence for %s', async (name, status, errorCode) => {
    setManagerCsrfToken(`csrf-${name}`);
    const caseKey = errorCode.toLowerCase().replace(/_/g, '-');
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap');
    const recovery = vi.spyOn(managerSessionRecovery, 'handle').mockReturnValue(true);
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(availabilityResponse(`runtime-${name}`))
      .mockResolvedValueOnce(managerErrorResponse(status, errorCode));
    vi.stubGlobal('fetch', fetchMock);

    await expect(executionGrantBroker.getGrant(
      `https://${caseKey}.test`,
      'workspace-runtime',
      'runtime_write',
      `workspace-${caseKey}`,
    )).rejects.toMatchObject({ status, errorCode });

    expect(bootstrap).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    if (status === 401) {
      expect(recovery).toHaveBeenCalledWith(
        401,
        AUTHORIZATION_ERROR_CODES.managerSessionRequired,
        expect.any(String),
      );
    } else {
      expect(recovery).not.toHaveBeenCalled();
    }
  });

  it('does not refresh CSRF evidence for a network error', async () => {
    setManagerCsrfToken('csrf-network-error');
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap');
    const networkError = new TypeError('network unavailable');
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(availabilityResponse('runtime-network-error'))
      .mockRejectedValueOnce(networkError);
    vi.stubGlobal('fetch', fetchMock);

    await expect(executionGrantBroker.getGrant(
      'https://network-error.test',
      'workspace-runtime',
      'runtime_write',
      'workspace-network-error',
    )).rejects.toBe(networkError);

    expect(bootstrap).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not refresh for a malformed thrown value resembling a CSRF error', async () => {
    setManagerCsrfToken('csrf-malformed-error');
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap');
    const malformedError = {
      status: 403,
      errorCode: AUTHORIZATION_ERROR_CODES.managerSessionCsrfInvalid,
    };
    vi.spyOn(apiClient, 'post').mockRejectedValueOnce(malformedError);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      availabilityResponse('runtime-malformed-error'),
    ));

    await expect(executionGrantBroker.getGrant(
      'https://malformed-error.test',
      'workspace-runtime',
      'runtime_write',
      'workspace-malformed-error',
    )).rejects.toBe(malformedError);

    expect(bootstrap).not.toHaveBeenCalled();
    expect(apiClient.post).toHaveBeenCalledTimes(1);
  });

  it('routes Manager API session failures through the process-wide recovery seam', async () => {
    const recovery = vi.spyOn(managerSessionRecovery, 'handle').mockReturnValue(true);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        errorCode: 'MANAGER_SESSION_REQUIRED',
        message: 'auth.manager_session.required',
        details: {},
      },
    }), { status: 401 })));

    await expect(executionGrantBroker.getGrant(
      'https://runtime-auth.test', 'workspace-runtime', 'runtime_read', 'workspace-auth',
    )).rejects.toMatchObject({
      status: 401,
      errorCode: 'MANAGER_SESSION_REQUIRED',
    });
    expect(recovery).toHaveBeenCalledWith(
      401,
      'MANAGER_SESSION_REQUIRED',
      expect.any(String),
    );
  });
});
