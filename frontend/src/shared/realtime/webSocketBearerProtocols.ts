const BEARER_PROTOCOL_PREFIX = 'bearer.';

export const createWebSocketBearerProtocols = (
  applicationProtocol: string,
  token: string,
): [string, string] => {
  if (
    !applicationProtocol
    || applicationProtocol !== applicationProtocol.trim()
    || /[\s\0]/.test(applicationProtocol)
  ) {
    throw new Error('WebSocket application protocol is invalid');
  }
  if (!token || token !== token.trim() || /[\s\0]/.test(token)) {
    throw new Error('WebSocket bearer token is invalid');
  }

  const bytes = new TextEncoder().encode(token);
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  const encodedToken = btoa(binary)
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
  return [applicationProtocol, BEARER_PROTOCOL_PREFIX + encodedToken];
};
