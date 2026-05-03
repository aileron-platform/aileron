import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('GeminiOAuthService', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    localStorage.clear();
  });

  it('uses env-based Gemini OAuth configuration', async () => {
    vi.stubEnv('VITE_GEMINI_GOOGLE_CLIENT_ID', 'google-client-id');
    vi.stubEnv('VITE_GEMINI_GOOGLE_REDIRECT_URI', 'https://example.com/oauth/callback');

    const { GeminiOAuthService } = await import('./geminiOauthService');
    const result = await GeminiOAuthService.buildAuthorizationURL();
    const url = new URL(result.url);

    expect(url.searchParams.get('client_id')).toBe('google-client-id');
    expect(url.searchParams.get('redirect_uri')).toBe('https://example.com/oauth/callback');
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(result.verifier).toBeTruthy();
  });

  it('throws i18n error key when client ID is missing', async () => {
    const { GeminiOAuthService } = await import('./geminiOauthService');

    expect(() => GeminiOAuthService.getOAuthConfig()).toThrowError('gemini_oauth.client_not_configured');
  });
});
