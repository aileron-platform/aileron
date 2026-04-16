import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OidcService } from './OidcService';
import type { OidcConfig } from '../types';

const TEST_CONFIG: OidcConfig = {
  authority: 'http://keycloak.localtest.me/realms/aileron',
  clientId: 'aileron-frontend',
  redirectUri: 'http://app.localtest.me/callback',
  postLogoutRedirectUri: 'http://app.localtest.me/login',
  responseType: 'code',
  scope: 'openid profile email',
  automaticSilentRenew: false,
  loadUserInfo: false,
};

describe('OidcService', () => {
  beforeEach(() => {
    sessionStorage.clear();
    window.location.href = 'http://app.localtest.me/login';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('在 crypto.subtle 可用時建立登入導向網址', async () => {
    const service = new OidcService(TEST_CONFIG);
    const assignSpy = vi.spyOn(window.location, 'assign').mockImplementation(() => {});

    service.buildAuthorizationUrl();
    await vi.waitFor(() => {
      expect(assignSpy).toHaveBeenCalledTimes(1);
    });

    const redirectedUrl = assignSpy.mock.calls[0]?.[0];
    expect(redirectedUrl).toBeTruthy();
    const url = new URL(String(redirectedUrl));

    expect(url.origin + url.pathname).toBe(
      'http://keycloak.localtest.me/realms/aileron/protocol/openid-connect/auth',
    );
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.searchParams.get('code_challenge')).toBeTruthy();
  });

  it('在 crypto.subtle 不可用時仍使用標準 SHA-256 產生 PKCE challenge', async () => {
    const originalCrypto = globalThis.crypto;
    const fallbackCrypto = {
      getRandomValues: originalCrypto.getRandomValues.bind(originalCrypto),
      subtle: undefined,
    } as Crypto;
    vi.stubGlobal('crypto', fallbackCrypto);
    const assignSpy = vi.spyOn(window.location, 'assign').mockImplementation(() => {});

    const service = new OidcService(TEST_CONFIG);
    service.buildAuthorizationUrl();
    await vi.waitFor(() => {
      expect(assignSpy).toHaveBeenCalledTimes(1);
    });

    const redirectedUrl = assignSpy.mock.calls[0]?.[0];
    expect(redirectedUrl).toBeTruthy();
    const url = new URL(String(redirectedUrl));
    const codeChallenge = url.searchParams.get('code_challenge');
    const stateJson = sessionStorage.getItem('oidc_state');

    expect(codeChallenge).toBeTruthy();
    expect(codeChallenge).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(stateJson).not.toBeNull();

    const { codeVerifier } = JSON.parse(stateJson!);
    expect(codeVerifier).toHaveLength(64);
  });

  it('fallback 路徑會產生 RFC 7636 範例相符的 code challenge', async () => {
    const { generateCodeChallengeSync } = await import('@/shared/utils/oauth');
    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';

    expect(generateCodeChallengeSync(verifier)).toBe(
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    );
  });
});
