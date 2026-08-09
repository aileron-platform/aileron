import {
  FC,
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useLocation } from 'react-router-dom';
import { subscribeApiError } from '@/shared/api/apiClient';
import {
  AUTHORIZATION_ERROR_CODES,
  shouldRefreshPlatformAuthorization,
} from '@/shared/authorization/authorizationErrorCodes';
import { hasAllowedOperation, type OperationId } from '@/shared/authorization/operationIds';
import { AUTH_ERROR_CODES } from '../model/authErrorCodes';
import {
  managerSessionService,
  type ManagerSessionUser,
} from '../services/ManagerSessionService';
import '../services/ExecutionGrantBroker';

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: ManagerSessionUser | null;
  error: string | null;
  platformRole: 'admin' | 'member' | null;
  allowedOperations: OperationId[];
}

export interface AuthContextValue extends AuthState {
  isPlatformAdmin: boolean;
  hasPlatformOperation: (operationId: OperationId) => boolean;
  logout: () => Promise<void>;
  login: () => Promise<void>;
  register: () => void;
  clearError: () => void;
}

const anonymousState: AuthState = {
  isAuthenticated: false,
  isLoading: false,
  user: null,
  error: null,
  platformRole: null,
  allowedOperations: [],
};

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const location = useLocation();
  const [state, setState] = useState<AuthState>({ ...anonymousState, isLoading: true });

  const bootstrap = useCallback(async () => {
    try {
      const session = await managerSessionService.bootstrap();
      if (!session) {
        setState(anonymousState);
        return;
      }
      setState({
        isAuthenticated: true,
        isLoading: false,
        user: session.user,
        error: null,
        platformRole: session.user.platform_role,
        allowedOperations: session.user.allowed_operations as OperationId[],
      });
    } catch (error) {
      const errorCode = error instanceof Error ? error.message : null;
      setState({
        ...anonymousState,
        error: errorCode === AUTHORIZATION_ERROR_CODES.platformAuthorizationDenied
          ? errorCode
          : AUTH_ERROR_CODES.initializationFailed,
      });
    }
  }, []);

  useEffect(() => {
    void bootstrap();
    const unsubscribe = subscribeApiError((event) => {
      if (shouldRefreshPlatformAuthorization(event.errorCode)) void bootstrap();
    });
    return () => {
      unsubscribe();
    };
  }, [bootstrap]);

  const login = useCallback(async () => {
    managerSessionService.login(`${location.pathname}${location.search}${location.hash}`);
  }, [location.hash, location.pathname, location.search]);

  const register = useCallback(() => {
    managerSessionService.login('/');
  }, []);

  const logout = useCallback(async () => {
    setState((current) => ({ ...current, isLoading: true }));
    try {
      await managerSessionService.logout();
    } finally {
      setState(anonymousState);
    }
  }, []);

  const clearError = useCallback(() => {
    setState((current) => ({ ...current, error: null }));
  }, []);

  const hasPlatformOperation = useCallback(
    (operationId: OperationId) => hasAllowedOperation(state.allowedOperations, operationId),
    [state.allowedOperations],
  );

  const value = useMemo<AuthContextValue>(() => ({
    ...state,
    isPlatformAdmin: state.platformRole === 'admin',
    hasPlatformOperation,
    logout,
    login,
    register,
    clearError,
  }), [clearError, hasPlatformOperation, login, logout, register, state]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuthContext = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuthContext must be used within AuthProvider');
  return context;
};
