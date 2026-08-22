import type { IncomingMessage } from 'node:http';

import { describe, expect, it, vi } from 'vitest';
import {
  authorizeWorkspaceGatewayRequest,
  createWorkspaceGatewayAuthorizationGate,
  removeWorkspaceGatewayCredentials,
  resolveWorkspaceGatewayRequest,
  workspaceGatewayCredentialHeaders,
} from './workspaceGateway';

const WORKSPACE_ID = 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6';

const createRequest = (
  url: string,
  cookie?: string,
): IncomingMessage => ({
  headers: {
    authorization: 'Bearer must-not-reach-manager',
    cookie,
    'x-api-key': 'must-not-reach-manager',
  },
  url,
} as IncomingMessage);

describe('resolveWorkspaceGatewayRequest', () => {
  it.each([
    [`/workspaces/${WORKSPACE_ID}/runtime/api/v1/health`, `http://workspace-runtime-${WORKSPACE_ID}:3002`, '/api/v1/health'],
    [`/workspaces/${WORKSPACE_ID}/runtime/ws/terminal`, `http://workspace-runtime-${WORKSPACE_ID}:3004`, '/ws/terminal'],
    [`/workspaces/${WORKSPACE_ID}/browser/ws`, `http://workspace-browser-${WORKSPACE_ID}:6080`, '/ws'],
    [`/workspaces/${WORKSPACE_ID}/canvas/?lang=zh-TW`, `http://workspace-canvas-${WORKSPACE_ID}:3003`, '/?lang=zh-TW'],
    [`/workspaces/${WORKSPACE_ID}/canvas/slides/1`, `http://workspace-canvas-${WORKSPACE_ID}:3003`, '/slides/1'],
  ])('maps %s to a fixed internal target', (path, target, rewrittenPath) => {
    const component = path.split('/')[3];
    expect(resolveWorkspaceGatewayRequest(path)).toEqual({
      forwardedPrefix: `/workspaces/${WORKSPACE_ID}/${component}`,
      target,
      rewrittenPath,
    });
  });

  it.each([
    [
      `/workspaces/${WORKSPACE_ID}/runtime/ws/terminal?workspace_id=${WORKSPACE_ID}`,
      `/ws/terminal?workspace_id=${WORKSPACE_ID}`,
    ],
    [
      `/workspaces/${WORKSPACE_ID}/browser/ws?password=browser-secret&username=user`,
      '/ws?password=browser-secret&username=user',
    ],
  ])('preserves the query string while rewriting %s', (path, rewrittenPath) => {
    expect(resolveWorkspaceGatewayRequest(path)?.rewrittenPath).toBe(rewrittenPath);
  });

  it.each([
    `/workspaces/workspace-1/runtime/api/v1/health`,
    `/workspaces/${WORKSPACE_ID}/unknown/api/v1/health`,
    `/workspaces/${WORKSPACE_ID}/runtime`,
    `/workspaces/${WORKSPACE_ID}/runtime/`,
    `/workspaces/${WORKSPACE_ID}/browser`,
    `/workspaces/${WORKSPACE_ID}/browser/`,
    `/workspaces/${WORKSPACE_ID}/canvas`,
  ])('does not proxy invalid or SPA-only paths: %s', (path) => {
    expect(resolveWorkspaceGatewayRequest(path)).toBeNull();
  });

  it('keeps only the Runtime execution grant while removing platform credentials', () => {
    expect(workspaceGatewayCredentialHeaders(
      `/workspaces/${WORKSPACE_ID}/runtime/api/v1/health`,
    )).toEqual([
      'cookie',
      'proxy-authorization',
      'x-api-key',
      'x-csrf-token',
    ]);
  });

  it.each(['browser', 'canvas'])('removes every platform credential from %s', (target) => {
    expect(workspaceGatewayCredentialHeaders(
      `/workspaces/${WORKSPACE_ID}/${target}/health`,
    )).toEqual([
      'authorization',
      'cookie',
      'proxy-authorization',
      'x-api-key',
      'x-csrf-token',
    ]);
  });

  it('does not remove credentials from a non-Workspace request', () => {
    const request = createRequest('/api/v1/oauth2/session', 'aileron_session=manager-session');

    removeWorkspaceGatewayCredentials(request);

    expect(request.headers).toEqual({
      authorization: 'Bearer must-not-reach-manager',
      cookie: 'aileron_session=manager-session',
      'x-api-key': 'must-not-reach-manager',
    });
  });

  it('removes platform credentials before proxy path rewriting', () => {
    const runtimeRequest = createRequest(
      `/workspaces/${WORKSPACE_ID}/runtime/api/v1/health`,
      'aileron_workspace_gateway_session=gateway-handle',
    );
    runtimeRequest.headers['proxy-authorization'] = 'Basic proxy-secret';
    runtimeRequest.headers['x-csrf-token'] = 'csrf-secret';

    removeWorkspaceGatewayCredentials(runtimeRequest);

    expect(runtimeRequest.headers).toEqual({
      authorization: 'Bearer must-not-reach-manager',
    });

    const browserRequest = createRequest(
      `/workspaces/${WORKSPACE_ID}/browser/ws`,
      'aileron_workspace_gateway_session=gateway-handle',
    );
    removeWorkspaceGatewayCredentials(browserRequest);
    expect(browserRequest.headers).toEqual({});
  });
});

describe('authorizeWorkspaceGatewayRequest', () => {
  it('authorizes a canonical request with only the translated gateway session', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));

    const authorized = await authorizeWorkspaceGatewayRequest(
      createRequest(
        `/workspaces/${WORKSPACE_ID}/canvas/health`,
        'theme=dark; aileron_workspace_gateway_session=gateway-handle; aileron_session=attacker-session',
      ),
      {
        fetchImpl,
        managerTarget: 'http://workspace-manager:3001',
      },
    );

    expect(authorized).toBe(true);
    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, options] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://workspace-manager:3001/api/v1/workspaces/gateway/authorize');
    expect(options).toMatchObject({
      headers: {
        cookie: 'aileron_session=gateway-handle',
        'x-aileron-workspace-id': WORKSPACE_ID,
      },
      method: 'GET',
      redirect: 'manual',
    });
    expect(options?.headers).not.toHaveProperty('authorization');
    expect(options?.headers).not.toHaveProperty('x-api-key');
  });

  it('rejects a request without exactly one gateway session cookie', async () => {
    const fetchImpl = vi.fn<typeof fetch>();

    await expect(authorizeWorkspaceGatewayRequest(
      createRequest(`/workspaces/${WORKSPACE_ID}/runtime/api/v1/health`),
      { fetchImpl, managerTarget: 'http://workspace-manager:3001' },
    )).resolves.toBe(false);
    await expect(authorizeWorkspaceGatewayRequest(
      createRequest(
        `/workspaces/${WORKSPACE_ID}/runtime/api/v1/health`,
        'aileron_workspace_gateway_session=first; aileron_workspace_gateway_session=second',
      ),
      { fetchImpl, managerTarget: 'http://workspace-manager:3001' },
    )).resolves.toBe(false);

    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it.each([200, 302, 401, 403, 500])('rejects Manager status %s', async (status) => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status }));

    await expect(authorizeWorkspaceGatewayRequest(
      createRequest(
        `/workspaces/${WORKSPACE_ID}/browser/health`,
        'aileron_workspace_gateway_session=gateway-handle',
      ),
      { fetchImpl, managerTarget: 'http://workspace-manager:3001' },
    )).resolves.toBe(false);
  });

  it('rejects the request when Manager is unavailable', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValue(new Error('connection refused'));

    await expect(authorizeWorkspaceGatewayRequest(
      createRequest(
        `/workspaces/${WORKSPACE_ID}/canvas/health`,
        'aileron_workspace_gateway_session=gateway-handle',
      ),
      { fetchImpl, managerTarget: 'http://workspace-manager:3001' },
    )).resolves.toBe(false);
  });
});

describe('createWorkspaceGatewayAuthorizationGate', () => {
  it('continues an authorized HTTP request and rejects an unauthorized one', async () => {
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 403 }));
    const gate = createWorkspaceGatewayAuthorizationGate({
      fetchImpl,
      managerTarget: 'http://workspace-manager:3001',
    });
    const next = vi.fn();
    const authorizedResponse = { end: vi.fn(), statusCode: 200 };
    const deniedResponse = { end: vi.fn(), statusCode: 200 };
    const request = createRequest(
      `/workspaces/${WORKSPACE_ID}/runtime/api/v1/health`,
      'aileron_workspace_gateway_session=gateway-handle',
    );

    await gate.handleHttp(request, authorizedResponse, next);
    await gate.handleHttp(request, deniedResponse, next);

    expect(next).toHaveBeenCalledOnce();
    expect(authorizedResponse.end).not.toHaveBeenCalled();
    expect(deniedResponse.statusCode).toBe(403);
    expect(deniedResponse.end).toHaveBeenCalledWith();
  });

  it('upgrades only an authorized WebSocket initial request', async () => {
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }));
    const gate = createWorkspaceGatewayAuthorizationGate({
      fetchImpl,
      managerTarget: 'http://workspace-manager:3001',
    });
    const onAuthorized = vi.fn();
    const authorizedSocket = { end: vi.fn() };
    const deniedSocket = { end: vi.fn() };
    const request = createRequest(
      `/workspaces/${WORKSPACE_ID}/runtime/ws/terminal`,
      'aileron_workspace_gateway_session=gateway-handle',
    );

    await gate.handleUpgrade(request, authorizedSocket, onAuthorized);
    await gate.handleUpgrade(request, deniedSocket, onAuthorized);

    expect(onAuthorized).toHaveBeenCalledOnce();
    expect(authorizedSocket.end).not.toHaveBeenCalled();
    expect(deniedSocket.end).toHaveBeenCalledWith(
      'HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n',
    );
  });
});
