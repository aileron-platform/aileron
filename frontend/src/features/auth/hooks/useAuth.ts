/**
 * useAuth Hook
 *
 * Convenience hook to access authentication context.
 */

import { useAuthContext } from '../contexts/AuthContext';

/**
 * Hook to access authentication state and methods
 *
 * @example
 * ```tsx
 * const { isAuthenticated, user, login, logout } = useAuth();
 * ```
 */
export const useAuth = () => {
  const context = useAuthContext();
  return context;
};

/**
 * Hook to check if user is authenticated
 *
 * @example
 * ```tsx
 * const isAuthenticated = useIsAuthenticated();
 * if (!isAuthenticated) {
 *   return <LoginRequired />;
 * }
 * ```
 */
export const useIsAuthenticated = (): boolean => {
  const { isAuthenticated } = useAuthContext();
  return isAuthenticated;
};

/**
 * Hook to get current user
 *
 * @example
 * ```tsx
 * const user = useCurrentUser();
 * return <div>Welcome, {user?.email}</div>;
 * ```
 */
export const useCurrentUser = () => {
  const { user } = useAuthContext();
  return user;
};
