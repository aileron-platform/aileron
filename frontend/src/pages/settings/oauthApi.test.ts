import { beforeEach, describe, expect, it, vi } from 'vitest';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    post: postMock,
  },
}));

import { authenticateOAuth } from './oauthApi';

describe('authenticateOAuth', () => {
  beforeEach(() => {
    postMock.mockReset();
  });

  it('preserves the OAuth authentication endpoint and payload', async () => {
    const response = {
      success: true,
      message: 'ok',
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiresAt: 123,
    };
    postMock.mockResolvedValue(response);

    await expect(authenticateOAuth('auth-code', 'verifier')).resolves.toBe(response);
    expect(postMock).toHaveBeenCalledWith('/oauth/authenticate', {
      authCode: 'auth-code',
      verifier: 'verifier',
    });
  });
});
