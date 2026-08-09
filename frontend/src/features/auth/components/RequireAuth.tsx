import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { AuthorizationDeniedState } from './AuthorizationDeniedState';
import { ROUTES } from '@/shared/constants/routes';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import { projectPlatformIdentityEntry } from '@/shared/components/entry/platformIdentityEntryProjection';
import { AUTHORIZATION_ERROR_CODES } from '@/shared/authorization/authorizationErrorCodes';

interface RequireAuthProps {
  children: React.ReactElement;
  navigationSlot?: React.ReactNode;
}

interface LocationState {
  from?: {
    pathname: string;
    search?: string;
    hash?: string;
  };
}

const identityProjection = projectPlatformIdentityEntry({ status: 'checking' });
const identityResolvedProjection = projectPlatformIdentityEntry({ status: 'authenticated' });

const toSafeReturnTarget = (from: LocationState['from']): string | null => {
  if (!from?.pathname || !from.pathname.startsWith('/') || from.pathname.startsWith('//')) {
    return null;
  }
  return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`;
};

/**
 * Protected Route Component
 *
 * Redirects to login page if user is not authenticated.
 * Shows the shared identity entry surface while checking authentication status.
 */
export const RequireAuth: React.FC<RequireAuthProps> = ({ children, navigationSlot }) => {
  const { error, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <EntryFrame
        isPending
        transitionKey="platform-identity"
        projection={identityProjection}
        navigationSlot={navigationSlot}
        onAction={() => undefined}
      >
        {null}
      </EntryFrame>
    );
  }

  if (error === AUTHORIZATION_ERROR_CODES.platformAuthorizationDenied) {
    return (
      <EntryFrame
        isPending={false}
        keepFrame
        transitionKey="platform-identity"
        projection={identityResolvedProjection}
        navigationSlot={navigationSlot}
        onAction={() => undefined}
      >
        <AuthorizationDeniedState />
      </EntryFrame>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={ROUTES.login}
        state={{
          from: {
            pathname: location.pathname,
            search: location.search,
            hash: location.hash,
          },
        }}
        replace
      />
    );
  }

  return children;
};

/**
 * Public Route Component
 *
 * Redirects to home page if user is already authenticated.
 * Useful for login/register pages.
 */
export const PublicRoute: React.FC<RequireAuthProps> = ({ children, navigationSlot }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <EntryFrame
        isPending
        transitionKey="platform-identity"
        projection={identityProjection}
        navigationSlot={navigationSlot}
        onAction={() => undefined}
      >
        {null}
      </EntryFrame>
    );
  }

  if (isAuthenticated) {
    const from = toSafeReturnTarget((location.state as LocationState | null)?.from)
      ?? ROUTES.workspace.root;
    return <Navigate to={from} replace />;
  }

  return children;
};

export default RequireAuth;
