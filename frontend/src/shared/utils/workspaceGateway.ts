export type WorkspaceGatewayTarget = 'runtime' | 'browser' | 'canvas';

const CANONICAL_WORKSPACE_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const normalizeSuffix = (suffix: string): string => {
  if (!suffix) return '';
  if (!suffix.startsWith('/') || suffix.startsWith('//') || suffix.includes('\\')) {
    throw new Error('WORKSPACE_GATEWAY_PATH_INVALID');
  }
  const segments = suffix.split('/');
  if (segments.some((segment) => segment === '..')) {
    throw new Error('WORKSPACE_GATEWAY_PATH_INVALID');
  }
  return suffix;
};

export const buildWorkspaceGatewayPath = (
  workspaceId: string,
  target: WorkspaceGatewayTarget,
  suffix = '',
): string => {
  if (!CANONICAL_WORKSPACE_ID_PATTERN.test(workspaceId)) {
    throw new Error('WORKSPACE_GATEWAY_ID_INVALID');
  }
  return `/workspaces/${workspaceId}/${target}${normalizeSuffix(suffix)}`;
};

export const toSameOriginWebSocketUrl = (
  path: string,
  origin: string = window.location.origin,
): string => {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new Error('WORKSPACE_GATEWAY_PATH_INVALID');
  }
  const url = new URL(path, origin);
  if (url.origin !== new URL(origin).origin) {
    throw new Error('WORKSPACE_GATEWAY_PATH_INVALID');
  }
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
};
