/**
 * Authentication Context
 *
 * Provides authentication state and methods to the entire application.
 * Uses OAuth2/OIDC (Keycloak) as the sole authentication mechanism.
 */

import { FC, createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from 'react';
import type { OidcUserProfile } from '../types';
import { createOidcService, getOidcService } from '../services/OidcService';
import { getOidcConfig } from '../config/oidcConfig';
import { createLogger } from '@/shared/services/logger';
import { registerAuthTokenProvider, registerTokenRefreshHandler, registerSessionExpiredHandler } from '@/shared/api/apiClient';

const logger = createLogger('AuthContext');

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: OidcUserProfile | null;
  error: string | null;
}

export interface AuthContextValue extends AuthState {
  logout: () => Promise<void>;
  loginWithKeycloak: () => Promise<void>;
  registerWithKeycloak: () => void;
  handleKeycloakCallback: (code: string, state: string) => Promise<void>;

  // Token management — 使用 getAccessToken() 取得最新 token，而非靜態快照
  refreshToken: () => Promise<void>;
  getAccessToken: () => string | null;

  // Clear errors
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    user: null,
    error: null,
  });

  // Initialize authentication on mount
  useEffect(() => {
    // Handler for session expiry — called from apiClient and OidcService auto-refresh
    const handleSessionExpired = () => {
      logger.warn('Session expired, redirecting to login');
      sessionStorage.removeItem('oidc_tokens');
      sessionStorage.removeItem('oidc_user_profile');
      sessionStorage.removeItem('oidc_state');
      setState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });
      window.location.href = '/login';
    };

    // Register API client handlers — 使用 oidcService 取得最新 token，而非讀取 sessionStorage 快照
    registerAuthTokenProvider(() => {
      const oidcService = getOidcService();
      if (oidcService) {
        return oidcService.getAccessToken();
      }
      return null;
    });

    registerTokenRefreshHandler(async () => {
      const oidcService = getOidcService();
      if (oidcService) {
        await oidcService.refreshToken();
      }
    });

    registerSessionExpiredHandler(handleSessionExpired);

    // Listen for session-expired events from OidcService auto-refresh timer
    window.addEventListener('oidc:session-expired', handleSessionExpired);

    // Initialize Keycloak OAuth2/OIDC
    const initAuth = async () => {
      try {
        const oidcConfig = getOidcConfig();
        const oidcService = createOidcService(oidcConfig);
        const isAuthenticated = oidcService.isAuthenticated();
        const userProfile = oidcService.getUserProfile();

        setState({
          isAuthenticated,
          isLoading: false,
          user: userProfile,
          error: null,
          });

        logger.info('Keycloak authentication initialized', {
          isAuthenticated,
          userId: userProfile?.sub,
        });
      } catch (error) {
        logger.error('Failed to initialize Keycloak authentication', { error });
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: 'Failed to initialize authentication',
        }));
      }
    };

    initAuth();

    return () => {
      window.removeEventListener('oidc:session-expired', handleSessionExpired);
      registerAuthTokenProvider(null);
      registerTokenRefreshHandler(null);
      registerSessionExpiredHandler(null);
    };
  }, []);

  // Keycloak login method
  const loginWithKeycloak = useCallback(async () => {
    try {
      const oidcService = getOidcService();
      if (oidcService) {
        oidcService.buildAuthorizationUrl();
      } else {
        const error = 'OIDC service not initialized';
        setState((prev) => ({ ...prev, error }));
        logger.error(error);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed';
      setState((prev) => ({ ...prev, error: message }));
      logger.error('loginWithKeycloak failed', { error });
    }
  }, []);

  // Keycloak registration method
  const registerWithKeycloak = useCallback(() => {
    const oidcService = getOidcService();
    if (oidcService) {
      oidcService.buildRegistrationUrl();
    } else {
      const error = 'OIDC service not initialized';
      setState((prev) => ({ ...prev, error }));
      logger.error(error);
    }
  }, []);

  // Handle Keycloak OAuth2 callback
  const handleKeycloakCallback = useCallback(async (code: string, state: string) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const oidcService = getOidcService();
      if (!oidcService) {
        throw new Error('OIDC service not initialized');
      }

      await oidcService.handleCallback({ code, state });

      const userProfile = oidcService.getUserProfile();

      setState({
        isAuthenticated: true,
        isLoading: false,
        user: userProfile,
        error: null,
      });

      logger.info('Keycloak authentication successful', {
        userId: userProfile?.sub,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Authentication failed';
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      logger.error('Keycloak callback failed', { error });
      throw error;
    }
  }, []);

  // Logout method
  const logout = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true }));

    try {
      const oidcService = getOidcService();
      if (oidcService) {
        await oidcService.logout();
      }
      setState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });
      logger.info('Logout successful');
    } catch (error) {
      logger.error('Logout failed', { error });
      setState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });
    }
  }, []);

  // Refresh token method
  const refreshToken = useCallback(async () => {
    const oidcService = getOidcService();
    if (!oidcService) {
      throw new Error('OIDC service not initialized');
    }
    await oidcService.refreshToken();
    const userProfile = oidcService.getUserProfile();
    setState((prev) => ({ ...prev, user: userProfile }));
  }, []);

  // Get access token method
  const getAccessToken = useCallback((): string | null => {
    const oidcService = getOidcService();
    return oidcService ? oidcService.getAccessToken() : null;
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  // Context value
  const value: AuthContextValue = useMemo(
    () => ({
      ...state,
      logout,
      loginWithKeycloak,
      registerWithKeycloak,
      handleKeycloakCallback,
      // 注意：移除靜態 accessToken 快照，改由呼叫方使用 getAccessToken() 取得最新 token
      refreshToken,
      getAccessToken,
      clearError,
    }),
    [
      state,
      logout,
      loginWithKeycloak,
      registerWithKeycloak,
      handleKeycloakCallback,
      refreshToken,
      getAccessToken,
      clearError,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Hook to use authentication context
 */
export const useAuthContext = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }
  return context;
};
