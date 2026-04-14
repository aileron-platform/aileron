import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('getOidcConfig', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    window.history.replaceState({}, '', '/login');
  });

  it('在未設定公開網址時使用目前 origin', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:3001');
    vi.stubEnv('VITE_KEYCLOAK_SERVER_URL', 'http://localhost:8080');
    vi.stubEnv('VITE_KEYCLOAK_REALM', 'aileron');
    vi.stubEnv('VITE_KEYCLOAK_CLIENT_ID', 'aileron-frontend');
    vi.stubEnv('VITE_FRONTEND_PUBLIC_URL', '');

    const { getOidcConfig } = await import('./oidcConfig');
    const config = getOidcConfig();
    const currentOrigin = window.location.origin;

    expect(config.redirectUri).toBe(`${currentOrigin}/callback`);
    expect(config.postLogoutRedirectUri).toBe(`${currentOrigin}/login`);
  });

  it('目前頁面是 localhost 時，會優先使用非 localhost 的 API origin', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://aileron.localhost/api');
    vi.stubEnv('VITE_KEYCLOAK_SERVER_URL', 'http://keycloak.aileron.localhost');
    vi.stubEnv('VITE_KEYCLOAK_REALM', 'aileron');
    vi.stubEnv('VITE_KEYCLOAK_CLIENT_ID', 'aileron-frontend');
    vi.stubEnv('VITE_FRONTEND_PUBLIC_URL', '');

    const { getOidcConfig } = await import('./oidcConfig');
    const config = getOidcConfig();

    expect(config.redirectUri).toBe('http://aileron.localhost/callback');
    expect(config.postLogoutRedirectUri).toBe('http://aileron.localhost/login');
  });

  it('設定公開網址時應覆蓋自動推導結果', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:3001');
    vi.stubEnv('VITE_KEYCLOAK_SERVER_URL', 'http://localhost:8080');
    vi.stubEnv('VITE_KEYCLOAK_REALM', 'aileron');
    vi.stubEnv('VITE_KEYCLOAK_CLIENT_ID', 'aileron-frontend');
    vi.stubEnv('VITE_FRONTEND_PUBLIC_URL', 'http://aileron.localhost/');

    const { getOidcConfig } = await import('./oidcConfig');
    const config = getOidcConfig();

    expect(config.redirectUri).toBe('http://aileron.localhost/callback');
    expect(config.postLogoutRedirectUri).toBe('http://aileron.localhost/login');
  });

  it('Keycloak 公開網址已包含 realm 路徑時不應重複附加', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://workspace-manager.example.com');
    vi.stubEnv('VITE_KEYCLOAK_SERVER_URL', 'https://keycloak.example.com/realms/aileron');
    vi.stubEnv('VITE_KEYCLOAK_REALM', 'aileron');
    vi.stubEnv('VITE_KEYCLOAK_CLIENT_ID', 'aileron-frontend');
    vi.stubEnv('VITE_FRONTEND_PUBLIC_URL', 'https://app.example.com');

    const { getOidcConfig } = await import('./oidcConfig');
    const config = getOidcConfig();

    expect(config.authority).toBe('https://keycloak.example.com/realms/aileron');
    expect(config.redirectUri).toBe('https://app.example.com/callback');
  });
});
