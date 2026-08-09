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
