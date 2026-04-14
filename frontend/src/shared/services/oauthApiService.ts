/**
 * OAuth API 服務 - 處理與後端的 OAuth 相關 API 呼叫
 */

import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('OAuthApiService');

export interface OAuthExchangeRequest {
  authCode: string;
  verifier: string;
}

export interface OAuthExchangeResponse {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;  // 毫秒時間戳
}

export interface OAuthRefreshRequest {
  refreshToken: string;
}

export interface OAuthRefreshResponse {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;  // 毫秒時間戳
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
  expiresAt: number;  // 毫秒時間戳
  needsSync?: boolean;  // 是否需要同步到 workspace
  oauthAccount?: OAuthAccountInfo;  // OAuth 帳戶資訊
}

export class OAuthApiService {
  /**
   * OAuth 認證並儲存到資料庫（推薦使用）
   *
   * 這個方法會：
   * 1. 使用 authCode 和 verifier 呼叫 Anthropic OAuth API
   * 2. 取得 access_token, refresh_token
   * 3. 直接儲存到資料庫
   *
   * @param authCode - OAuth 認證碼（格式：code#state）
   * @param verifier - PKCE code verifier
   * @returns OAuth 認證結果
   */
  static async authenticate(authCode: string, verifier: string): Promise<OAuthAuthenticateResponse> {
    const response = await apiClient.post<OAuthAuthenticateResponse>('/oauth/authenticate', {
      authCode,
      verifier,
    });
    return response;
  }

  /**
   * 交換 OAuth 認證碼取得 Access Token（不儲存到資料庫）
   *
   * @deprecated 建議使用 authenticate() 方法，會直接儲存到資料庫
   */
  static async exchangeCode(authCode: string, verifier: string): Promise<OAuthExchangeResponse> {
    const response = await apiClient.post<OAuthExchangeResponse>('/oauth/exchange', {
      authCode,
      verifier,
    });
    return response;
  }

  /**
   * 更新 Access Token
   */
  static async refreshToken(refreshToken: string): Promise<OAuthRefreshResponse> {
    const response = await apiClient.post<OAuthRefreshResponse>('/oauth/refresh', {
      refreshToken,
    });
    return response;
  }
}

