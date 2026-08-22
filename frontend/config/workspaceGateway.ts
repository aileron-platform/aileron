import type { IncomingMessage } from 'node:http';

type WorkspaceGatewayRequest = {
  forwardedPrefix: string;
  target: string;
  rewrittenPath: string;
};

type WorkspaceGatewayAuthorizationOptions = {
  fetchImpl?: typeof fetch;
  managerTarget: string;
};

type WorkspaceGatewayHttpResponse = {
  end: () => void;
  statusCode: number;
};

type WorkspaceGatewayUpgradeSocket = {
  end: (data?: string) => void;
};

const WORKSPACE_GATEWAY_PATTERN =
  /^\/workspaces\/([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\/(runtime|browser|canvas)(\/.*)$/;

const TARGET_PORTS = {
  runtime: 3002,
  browser: 6080,
  canvas: 3003,
} as const;

const WORKSPACE_CREDENTIAL_HEADERS = [
  'cookie',
  'proxy-authorization',
  'x-api-key',
  'x-csrf-token',
] as const;

const WORKSPACE_GATEWAY_SESSION_COOKIE_NAME = 'aileron_workspace_gateway_session';
const MANAGER_SESSION_COOKIE_NAME = 'aileron_session';
const WORKSPACE_GATEWAY_AUTHORIZATION_PATH = '/api/v1/workspaces/gateway/authorize';
const WORKSPACE_GATEWAY_AUTHORIZATION_TIMEOUT_MS = 3_000;

export const WORKSPACE_GATEWAY_PROXY_PATTERN =
  '^/workspaces/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/(?:canvas/.*|(?:runtime|browser)/.+)';

const matchWorkspaceGatewayRequest = (requestPath: string | undefined) => {
  const path = (requestPath ?? '').split('?', 1)[0];
  const match = WORKSPACE_GATEWAY_PATTERN.exec(path);
  if (match?.[2] !== 'canvas' && match?.[3] === '/') return null;
  return match;
};

export const resolveWorkspaceGatewayRequest = (
  requestPath: string | undefined,
): WorkspaceGatewayRequest | null => {
  const match = matchWorkspaceGatewayRequest(requestPath);
  if (!match) return null;

  const [, workspaceId, target, suffix] = match;
  const queryIndex = requestPath?.indexOf('?') ?? -1;
  const query = queryIndex >= 0 ? requestPath?.slice(queryIndex) ?? '' : '';
  const isTerminal = target === 'runtime' && suffix.startsWith('/ws/terminal');
  const port = isTerminal ? 3004 : TARGET_PORTS[target as keyof typeof TARGET_PORTS];

  return {
    forwardedPrefix: `/workspaces/${workspaceId}/${target}`,
    target: `http://workspace-${target}-${workspaceId}:${port}`,
    rewrittenPath: `${suffix}${query}`,
  };
};

const readWorkspaceGatewaySession = (cookieHeader: string | undefined): string | null => {
  if (!cookieHeader) return null;

  const values = cookieHeader
    .split(';')
    .map((cookie) => cookie.trim())
    .filter((cookie) => cookie.startsWith(`${WORKSPACE_GATEWAY_SESSION_COOKIE_NAME}=`))
    .map((cookie) => cookie.slice(WORKSPACE_GATEWAY_SESSION_COOKIE_NAME.length + 1));

  if (values.length !== 1 || !values[0] || /[\r\n;]/.test(values[0])) return null;
  return values[0];
};

export const authorizeWorkspaceGatewayRequest = async (
  request: IncomingMessage,
  options: WorkspaceGatewayAuthorizationOptions,
): Promise<boolean> => {
  const match = matchWorkspaceGatewayRequest(request.url);
  const session = readWorkspaceGatewaySession(request.headers.cookie);
  if (!match || !session) return false;
  const workspaceId = match[1];

  try {
    const response = await (options.fetchImpl ?? fetch)(
      new URL(WORKSPACE_GATEWAY_AUTHORIZATION_PATH, options.managerTarget).toString(),
      {
        headers: {
          cookie: `${MANAGER_SESSION_COOKIE_NAME}=${session}`,
          'x-aileron-workspace-id': workspaceId,
        },
        method: 'GET',
        redirect: 'manual',
        signal: AbortSignal.timeout(WORKSPACE_GATEWAY_AUTHORIZATION_TIMEOUT_MS),
      },
    );
    return response.status === 204;
  } catch {
    return false;
  }
};

const rejectWorkspaceGatewayUpgrade = (socket: WorkspaceGatewayUpgradeSocket): void => {
  socket.end(
    'HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n',
  );
};

export const createWorkspaceGatewayAuthorizationGate = (
  options: WorkspaceGatewayAuthorizationOptions,
) => ({
  handleHttp: async (
    request: IncomingMessage,
    response: WorkspaceGatewayHttpResponse,
    next: () => void,
  ): Promise<void> => {
    if (!resolveWorkspaceGatewayRequest(request.url)) {
      next();
      return;
    }
    if (await authorizeWorkspaceGatewayRequest(request, options)) {
      next();
      return;
    }
    response.statusCode = 403;
    response.end();
  },
  handleUpgrade: async (
    request: IncomingMessage,
    socket: WorkspaceGatewayUpgradeSocket,
    onAuthorized: () => void,
  ): Promise<void> => {
    if (!resolveWorkspaceGatewayRequest(request.url)) return;
    if (!await authorizeWorkspaceGatewayRequest(request, options)) {
      rejectWorkspaceGatewayUpgrade(socket);
      return;
    }
    try {
      onAuthorized();
    } catch {
      rejectWorkspaceGatewayUpgrade(socket);
    }
  },
});

export const workspaceGatewayCredentialHeaders = (
  requestPath: string | undefined,
): readonly string[] => {
  const path = (requestPath ?? '').split('?', 1)[0];
  const target = WORKSPACE_GATEWAY_PATTERN.exec(path)?.[2];
  if (!target) return [];
  if (target === 'runtime') return WORKSPACE_CREDENTIAL_HEADERS;
  return ['authorization', ...WORKSPACE_CREDENTIAL_HEADERS];
};

export const removeWorkspaceGatewayCredentials = (request: IncomingMessage): void => {
  for (const header of workspaceGatewayCredentialHeaders(request.url)) {
    delete request.headers[header];
  }
};
