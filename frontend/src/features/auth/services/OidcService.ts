/**
 * OAuth2/OIDC Authentication Service for Keycloak
 *
 * Implements Authorization Code Flow with PKCE (Proof Key for Code Exchange)
 * for secure authentication without storing client secrets.
 */

import type {
  OidcConfig,
  OidcTokens,
  OidcUserProfile,
  OidcCallbackResponse,
} from '../types';
import { createLogger } from '@/shared/services/logger';
import { generateCodeChallenge } from '@/shared/utils/oauth';

const logger = createLogger('OidcService');

// OAuth2 PKCE state management
interface OidcState {
  codeVerifier: string;
  state: string;
  timestamp: number;
}

// Storage keys
const STORAGE_KEYS = {
  TOKENS: 'oidc_tokens',
  USER_PROFILE: 'oidc_user_profile',
  STATE: 'oidc_state',
} as const;

/**
 * Generate random string for PKCE code verifier and state
 */
const generateRandomString = (length: number = 32): string => {
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const values = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(values, (byte) => charset[byte % charset.length]).join('');
};

/**
 * OIDC Authentication Service
 */
export class OidcService {
  private config: OidcConfig;
  private tokens: OidcTokens | null = null;
  private userProfile: OidcUserProfile | null = null;
  private tokenRefreshTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(config: OidcConfig) {
    this.config = config;
    this.loadFromStorage();
    this.startTokenRefresh();
  }

  /**
   * Build authorization URL for Keycloak login
   */
  buildAuthorizationUrl(): string {
    const codeVerifier = generateRandomString(64);
    const state = generateRandomString(32);

    // Store PKCE state
    const oidcState: OidcState = {
      codeVerifier,
      state,
      timestamp: Date.now(),
    };
    sessionStorage.setItem(STORAGE_KEYS.STATE, JSON.stringify(oidcState));

    // Generate code challenge
    generateCodeChallenge(codeVerifier).then((codeChallenge) => {
      // Build authorization URL
      const params = new URLSearchParams({
        client_id: this.config.clientId,
        redirect_uri: this.config.redirectUri,
        response_type: this.config.responseType,
        scope: this.config.scope,
        state: state,
        code_challenge: codeChallenge,
        code_challenge_method: 'S256',
      });

      const authUrl = `${this.config.authority}/protocol/openid-connect/auth?${params.toString()}`;
      logger.info('Redirecting to Keycloak for authentication');

      // Redirect to Keycloak
      window.location.assign(authUrl);
    }).catch((error) => {
      logger.error('Failed to generate code challenge for login', { error });
    });

    // Return empty string (redirect will happen)
    return '';
  }

  /**
   * Build registration URL for Keycloak registration page
   */
  buildRegistrationUrl(): void {
    const codeVerifier = generateRandomString(64);
    const state = generateRandomString(32);

    // Store PKCE state (same as login)
    const oidcState: OidcState = {
      codeVerifier,
      state,
      timestamp: Date.now(),
    };
    sessionStorage.setItem(STORAGE_KEYS.STATE, JSON.stringify(oidcState));

    generateCodeChallenge(codeVerifier).then((codeChallenge) => {
      const params = new URLSearchParams({
        client_id: this.config.clientId,
        redirect_uri: this.config.redirectUri,
        response_type: this.config.responseType,
        scope: this.config.scope,
        state: state,
        code_challenge: codeChallenge,
        code_challenge_method: 'S256',
      });

      const registrationUrl = `${this.config.authority}/protocol/openid-connect/registrations?${params.toString()}`;
      logger.info('Redirecting to Keycloak for registration');
      window.location.assign(registrationUrl);
    }).catch((error) => {
      logger.error('Failed to generate code challenge for registration', { error });
    });
  }

  /**
   * Handle OAuth2 callback and exchange authorization code for tokens
   */
  async handleCallback(callback: OidcCallbackResponse): Promise<void> {
    logger.info('Handling OAuth2 callback', { state: callback.state });

    // Verify state parameter
    const storedState = sessionStorage.getItem(STORAGE_KEYS.STATE);
    if (!storedState) {
      throw new Error('No state found in session storage');
    }

    const oidcState: OidcState = JSON.parse(storedState);

    // Validate state (CSRF protection)
    if (callback.state !== oidcState.state) {
      throw new Error('Invalid state parameter');
    }

    // Validate timestamp to prevent state replay attacks (max 10 minutes)
    const STATE_MAX_AGE_MS = 10 * 60 * 1000;
    if (Date.now() - oidcState.timestamp > STATE_MAX_AGE_MS) {
      sessionStorage.removeItem(STORAGE_KEYS.STATE);
      throw new Error('Authorization request expired. Please try logging in again.');
    }

    // Exchange authorization code for tokens
    const tokenResponse = await this.exchangeCodeForTokens(
      callback.code,
      oidcState.codeVerifier,
    );

    // Store tokens
    this.tokens = tokenResponse;
    this.saveToStorage();

    // Load user profile
    if (this.config.loadUserInfo) {
      await this.loadUserProfile();
    }

    // Clean up state
    sessionStorage.removeItem(STORAGE_KEYS.STATE);

    logger.info('Authentication successful', {
      userId: this.userProfile?.sub,
    });
  }

  /**
   * Exchange authorization code for access tokens
   */
  private async exchangeCodeForTokens(
    code: string,
    codeVerifier: string,
  ): Promise<OidcTokens> {
    const tokenUrl = `${this.config.authority}/protocol/openid-connect/token`;
    const params = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: this.config.clientId,
      code: code,
      redirect_uri: this.config.redirectUri,
      code_verifier: codeVerifier,
    });

    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Token exchange failed: ${error}`);
    }

    return await response.json();
  }

  /**
   * Parse JWT token without verification (for reading claims only)
   */
  private parseJwt(token: string): Record<string, unknown> | null {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map((c) => {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      return JSON.parse(jsonPayload);
    } catch (error) {
      logger.error('Failed to parse JWT', { error });
      return null;
    }
  }

  /**
   * Load user profile from ID token or userinfo endpoint
   */
  private async loadUserProfile(): Promise<void> {
    // Try to load from ID token first (recommended approach)
    if (this.tokens?.id_token) {
      const idTokenClaims = this.parseJwt(this.tokens.id_token);
      if (idTokenClaims) {
        // Map ID token claims to OidcUserProfile format
        this.userProfile = {
          sub: idTokenClaims.sub,
          email: idTokenClaims.email,
          email_verified: idTokenClaims.email_verified,
          name: idTokenClaims.name,
          given_name: idTokenClaims.given_name,
          family_name: idTokenClaims.family_name,
          preferred_username: idTokenClaims.preferred_username,
        };
        this.saveToStorage();
        logger.info('User profile loaded from ID token');
        return;
      }
    }

    // Fallback to userinfo endpoint if ID token is not available
    if (!this.tokens?.access_token) {
      throw new Error('No access token available');
    }

    try {
      const userInfoUrl = `${this.config.authority}/protocol/openid-connect/userinfo`;
      const response = await fetch(userInfoUrl, {
        headers: {
          Authorization: `Bearer ${this.tokens.access_token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Userinfo request failed: ${response.status}`);
      }

      this.userProfile = await response.json();
      this.saveToStorage();
      logger.info('User profile loaded from userinfo endpoint');
    } catch (error) {
      logger.warn('Failed to load user profile from userinfo endpoint', { error });
      // Don't throw error - continue with ID token data only
    }
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshToken(): Promise<void> {
    if (!this.tokens?.refresh_token) {
      const error = 'No refresh token available';
      logger.error('Token refresh failed: no refresh token');
      throw new Error(error);
    }

    // 記錄刷新嘗試（不記錄 refresh token）
    const oldTokenExpiresIn = this.tokens.expires_in;
    logger.info(`Token refresh attempt: token expires in ${oldTokenExpiresIn}s`);

    const tokenUrl = `${this.config.authority}/protocol/openid-connect/token`;
    const params = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: this.config.clientId,
      refresh_token: this.tokens.refresh_token,
    });

    try {
      const response = await fetch(tokenUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params.toString(),
      });

      if (!response.ok) {
        const error = await response.text();
        logger.error(`Token refresh failed: HTTP ${response.status}, error=${error}`);
        throw new Error(`Token refresh failed: ${error}`);
      }

      this.tokens = await response.json();
      this.saveToStorage();

      // 記錄刷新成功
      const newExpiresIn = this.tokens.expires_in;
      logger.info(`Token refreshed successfully: old=${oldTokenExpiresIn}s, new=${newExpiresIn}s`);
    } catch (error) {
      // 記錄刷新失敗
      logger.error('Token refresh error', { error: error instanceof Error ? error.message : String(error) });
      throw error;
    }
  }

  /**
   * Start automatic token refresh
   */
  private startTokenRefresh(): void {
    if (!this.config.automaticSilentRenew || !this.tokens) {
      return;
    }

    // Clear existing timer
    if (this.tokenRefreshTimer) {
      clearTimeout(this.tokenRefreshTimer);
    }

    // Schedule token refresh (5 minutes before expiration)
    const expiresIn = this.tokens.expires_in * 1000;
    const refreshTime = Math.max(expiresIn - 5 * 60 * 1000, 60000); // At least 1 minute

    this.tokenRefreshTimer = setTimeout(async () => {
      try {
        logger.info(`Automatic token refresh triggered: ${refreshTime}ms scheduled`);
        await this.refreshToken();
        this.startTokenRefresh(); // Schedule next refresh
      } catch (error) {
        logger.error('Automatic token refresh failed', { error: error instanceof Error ? error.message : String(error) });
        logger.info('Session expired due to token refresh failure, redirecting to login');
        // Clear local tokens
        this.tokens = null;
        this.userProfile = null;
        sessionStorage.removeItem('oidc_tokens');
        sessionStorage.removeItem('oidc_user_profile');
        sessionStorage.removeItem('oidc_state');
        if (this.tokenRefreshTimer) {
          clearTimeout(this.tokenRefreshTimer);
          this.tokenRefreshTimer = null;
        }
        // Notify app layer via custom event
        window.dispatchEvent(new CustomEvent('oidc:session-expired'));
      }
    }, refreshTime);
  }

  /**
   * Logout user and clear tokens
   *
   * 清除本地 token 並通知 Keycloak 撤銷 session（fire-and-forget）。
   * 不使用 window.location.href 跳轉，讓呼叫方負責 UI 導向，
   * 避免 React state 更新和 navigate() 被中斷。
   */
  async logout(): Promise<void> {
    logger.info('Logging out user');

    const idToken = this.tokens?.id_token;

    // Clear tokens
    this.tokens = null;
    this.userProfile = null;
    sessionStorage.removeItem(STORAGE_KEYS.TOKENS);
    sessionStorage.removeItem(STORAGE_KEYS.USER_PROFILE);
    sessionStorage.removeItem(STORAGE_KEYS.STATE);

    // Clear refresh timer
    if (this.tokenRefreshTimer) {
      clearTimeout(this.tokenRefreshTimer);
      this.tokenRefreshTimer = null;
    }

    // 通知 Keycloak 撤銷 SSO session（Keycloak 18+ 使用 post_logout_redirect_uri）
    // 使用 fire-and-forget，不阻塞 UI 導向
    try {
      const params = new URLSearchParams({
        post_logout_redirect_uri: this.config.postLogoutRedirectUri,
        ...(idToken ? { id_token_hint: idToken } : {}),
      });
      const logoutUrl = `${this.config.authority}/protocol/openid-connect/logout?${params.toString()}`;
      // 使用 fetch 而非 window.location.href，避免打斷 React 的 state 更新
      await fetch(logoutUrl, { method: 'GET', mode: 'no-cors' });
    } catch {
      // 忽略錯誤，本地已清除 token，不影響登出流程
    }
  }

  /**
   * Get current access token
   */
  getAccessToken(): string | null {
    return this.tokens?.access_token || null;
  }

  /**
   * Get current user profile
   */
  getUserProfile(): OidcUserProfile | null {
    return this.userProfile;
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.tokens !== null && this.userProfile !== null;
  }

  /**
   * Load tokens from storage
   */
  private loadFromStorage(): void {
    try {
      const tokensJson = sessionStorage.getItem(STORAGE_KEYS.TOKENS);
      const profileJson = sessionStorage.getItem(STORAGE_KEYS.USER_PROFILE);

      if (tokensJson) {
        this.tokens = JSON.parse(tokensJson);
      }
      if (profileJson) {
        this.userProfile = JSON.parse(profileJson);
      }

      if (this.tokens) {
        logger.info('Tokens loaded from storage');
      }
    } catch (error) {
      logger.error('Failed to load tokens from storage', { error });
    }
  }

  /**
   * Save tokens to storage
   */
  private saveToStorage(): void {
    try {
      if (this.tokens) {
        sessionStorage.setItem(STORAGE_KEYS.TOKENS, JSON.stringify(this.tokens));
      }
      if (this.userProfile) {
        sessionStorage.setItem(
          STORAGE_KEYS.USER_PROFILE,
          JSON.stringify(this.userProfile),
        );
      }
    } catch (error) {
      logger.error('Failed to save tokens to storage', { error });
    }
  }
}

/**
 * Create singleton OIDC service instance
 */
let oidcServiceInstance: OidcService | null = null;

export const createOidcService = (config: OidcConfig): OidcService => {
  if (!oidcServiceInstance) {
    oidcServiceInstance = new OidcService(config);
  }
  return oidcServiceInstance;
};

export const getOidcService = (): OidcService | null => {
  return oidcServiceInstance;
};
