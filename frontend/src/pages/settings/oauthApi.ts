import { apiClient } from '@/shared/api/apiClient';
import type { OAuthAccountInfo } from '@/shared/types/user';

export interface OAuthAuthenticateResponse {
  success: boolean;
  message: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  needsSync?: boolean;
  oauthAccount?: OAuthAccountInfo;
}

export const authenticateOAuth = async (
  authCode: string,
  verifier: string,
): Promise<OAuthAuthenticateResponse> => (
  apiClient.post<OAuthAuthenticateResponse>('/oauth/authenticate', {
    authCode,
    verifier,
  })
);
