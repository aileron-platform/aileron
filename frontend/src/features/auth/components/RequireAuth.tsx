import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { LoadingSpinner } from '@/shared/components/ui/LoadingSpinner';

interface RequireAuthProps {
  children: React.ReactElement;
}

interface LocationState {
  from?: { pathname: string };
}

/**
 * Protected Route Component
 *
 * Redirects to login page if user is not authenticated.
 * Shows loading spinner while checking authentication status.
 */
export const RequireAuth: React.FC<RequireAuthProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <LoadingSpinner label="正在驗證使用者..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

/**
 * Public Route Component
 *
 * Redirects to home page if user is already authenticated.
 * Useful for login/register pages.
 */
export const PublicRoute: React.FC<RequireAuthProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <LoadingSpinner label="載入中..." />
      </div>
    );
  }

  if (isAuthenticated) {
    const from = (location.state as LocationState)?.from?.pathname || '/workspaces';
    return <Navigate to={from} replace />;
  }

  return children;
};

export default RequireAuth;
