import { apiClient } from '@/shared/api/apiClient';

export interface OAuthRefreshRequest {
  refreshToken: string;
}

export interface OAuthRefreshResponse {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export interface OAuthAccountInfo {
  accountUuid?: string;
  emailAddress?: string;
  organizationUuid?: string;
  displayName?: string;
  organizationBillingType?: string;
  organizationRole?: string;
  workspaceRole?: string | null;
  organizationName?: string;
}

export interface OAuthAuthenticateResponse {
  success: boolean;
  message: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  needsSync?: boolean;
  oauthAccount?: OAuthAccountInfo;
}

export class OAuthApiService {
  static async authenticate(authCode: string, verifier: string): Promise<OAuthAuthenticateResponse> {
    const response = await apiClient.post<OAuthAuthenticateResponse>('/oauth/authenticate', {
      authCode,
      verifier,
    });
    return response;
  }

  static async refreshToken(refreshToken: string): Promise<OAuthRefreshResponse> {
    const response = await apiClient.post<OAuthRefreshResponse>('/oauth/refresh', {
      refreshToken,
    });
    return response;
  }
}
