export const resolvePreferredWorkspaceUrl = (
  ...candidates: Array<string | null | undefined>
): string | null => {
  for (const candidate of candidates) {
    const normalized = candidate?.trim();
    if (normalized) {
      return normalized;
    }
  }
  return null;
};

export const toWebSocketUrl = (baseUrl: string, pathname: string = '/ws'): string => {
  const normalizedBaseUrl = baseUrl.trim();
  const url = new URL(normalizedBaseUrl);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = pathname.startsWith('/') ? pathname : `/${pathname}`;
  url.search = '';
  url.hash = '';
  return url.toString();
};
