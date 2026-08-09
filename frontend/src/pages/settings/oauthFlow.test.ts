// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { generateCodeChallengeMock, generateCodeVerifierMock } = vi.hoisted(() => ({
  generateCodeChallengeMock: vi.fn(),
  generateCodeVerifierMock: vi.fn(),
}));

vi.mock('@/shared/utils/oauth', () => ({
  generateCodeChallenge: generateCodeChallengeMock,
  generateCodeVerifier: generateCodeVerifierMock,
}));

vi.mock('@/shared/services/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
  }),
}));

import { clearOAuthVerifier, openOAuthWindow } from './oauthFlow';

describe('OAuth flow', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    generateCodeVerifierMock.mockReturnValue('verifier');
    generateCodeChallengeMock.mockResolvedValue('challenge');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    localStorage.clear();
  });

  it('preserves the authorization URL, popup options, and verifier storage key', async () => {
    const popup = { closed: true } as Window;
    const openWindow = vi.spyOn(window, 'open').mockReturnValue(popup);

    await expect(openOAuthWindow()).resolves.toEqual({ verifier: 'verifier' });

    const params = new URLSearchParams({
      code: 'true',
      client_id: '9d1c250a-e61b-44d9-88ed-5944d1962f5e',
      response_type: 'code',
      redirect_uri: 'https://console.anthropic.com/oauth/code/callback',
      scope: 'org:create_api_key user:profile user:inference',
      code_challenge: 'challenge',
      code_challenge_method: 'S256',
      state: 'verifier',
    });
    expect(openWindow).toHaveBeenCalledWith(
      `https://claude.ai/oauth/authorize?${params.toString()}`,
      'claude-oauth',
      'width=600,height=700,scrollbars=yes,resizable=yes,menubar=no,toolbar=no,location=yes',
    );
    expect(localStorage.getItem('claude_oauth_verifier')).toBe('verifier');

    vi.advanceTimersByTime(1000);
    clearOAuthVerifier();
    expect(localStorage.getItem('claude_oauth_verifier')).toBeNull();
  });
});
