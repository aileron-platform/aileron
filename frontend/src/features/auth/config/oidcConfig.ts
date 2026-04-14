/**
 * OIDC Configuration Factory
 *
 * Creates OIDC configuration from environment variables.
 * Authentication via Keycloak is always required — there is no toggle.
 */

import type { OidcConfig } from '../types';

const LOCALHOST_HOSTNAMES = new Set(['localhost', '127.0.0.1', '0.0.0.0']);

const isLocalhostUrl = (value: string): boolean => {
  try {
    return LOCALHOST_HOSTNAMES.has(new URL(value).hostname);
  } catch {
    return false;
  }
};

const getOriginFromUrl = (value: string | undefined): string | null => {
  if (!value) {
    return null;
  }

  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
};

const normalizeAuthority = (serverUrl: string, realm: string): string => {
  const normalizedServerUrl = serverUrl.replace(/\/+$/, '');
  if (normalizedServerUrl.includes('/realms/')) {
    return normalizedServerUrl.endsWith(`/${realm}`)
      ? normalizedServerUrl
      : `${normalizedServerUrl}/${realm}`;
  }
  return `${normalizedServerUrl}/realms/${realm}`;
};

export const getFrontendPublicUrl = (): string => {
  const configuredPublicUrl = import.meta.env.VITE_FRONTEND_PUBLIC_URL?.trim();
  if (configuredPublicUrl) {
    return configuredPublicUrl.replace(/\/+$/, '');
  }

  const currentOrigin = window.location.origin;
  if (!isLocalhostUrl(currentOrigin)) {
    return currentOrigin;
  }

  const apiOrigin = getOriginFromUrl(import.meta.env.VITE_API_BASE_URL);
  if (apiOrigin && !isLocalhostUrl(apiOrigin)) {
    return apiOrigin;
  }

  const keycloakOrigin = getOriginFromUrl(import.meta.env.VITE_KEYCLOAK_SERVER_URL);
  if (keycloakOrigin && !isLocalhostUrl(keycloakOrigin)) {
    return keycloakOrigin;
  }

  return currentOrigin;
};

export const getOidcConfig = (): OidcConfig => {
  const serverUrl = import.meta.env.VITE_KEYCLOAK_SERVER_URL;
  const realm = import.meta.env.VITE_KEYCLOAK_REALM;
  const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID;
  const frontendPublicUrl = getFrontendPublicUrl();

  const authority = normalizeAuthority(serverUrl, realm);
  const redirectUri = `${frontendPublicUrl}/callback`;

  return {
    authority,
    clientId,
    redirectUri,
    postLogoutRedirectUri: `${frontendPublicUrl}/login`,
    responseType: 'code',
    scope: 'openid profile email',
    automaticSilentRenew: true,
    loadUserInfo: true,
  };
};
