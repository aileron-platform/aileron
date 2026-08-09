import type React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authState = vi.hoisted(() => ({
  isAuthenticated: false,
  isLoading: false,
  error: null as string | null,
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => authState,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import { PublicRoute, RequireAuth } from './RequireAuth';

const LocationStateProbe: React.FC = () => {
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string; search?: string; hash?: string } } | null)?.from;
  return (
    <div data-testid="login-state">
      {`${from?.pathname ?? ''}${from?.search ?? ''}${from?.hash ?? ''}`}
    </div>
  );
};

const renderProtectedRoute = (initialEntry = '/workspaces/ws-1/files?open=readme.md#preview') => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route
        path="/workspaces/*"
        element={(
          <RequireAuth navigationSlot={<div data-testid="navigation-slot" />}>
            <div>protected-content</div>
          </RequireAuth>
        )}
      />
      <Route path="/login" element={<LocationStateProbe />} />
    </Routes>
  </MemoryRouter>
);

describe('RequireAuth', () => {
  beforeEach(() => {
    authState.isAuthenticated = false;
    authState.isLoading = false;
    authState.error = null;
  });

  it('uses the shared identity frame while authentication is loading', () => {
    authState.isLoading = true;
    renderProtectedRoute();

    expect(screen.getByTestId('entry-frame')).toBeInTheDocument();
    expect(screen.getByTestId('navigation-slot')).toBeInTheDocument();
    expect(screen.queryByText('protected-content')).not.toBeInTheDocument();
  });

  it('preserves the requested path, query, and hash for unauthenticated users', () => {
    renderProtectedRoute();

    expect(screen.getByTestId('login-state')).toHaveTextContent(
      '/workspaces/ws-1/files?open=readme.md#preview',
    );
  });

  it('renders protected content after authentication resolves', () => {
    authState.isAuthenticated = true;
    renderProtectedRoute();

    expect(screen.getByText('protected-content')).toBeInTheDocument();
  });

  it('renders authorization denied instead of returning a locally denied user to login', () => {
    authState.error = 'PLATFORM_AUTHORIZATION_DENIED';
    renderProtectedRoute();

    expect(screen.getByRole('alert')).toHaveTextContent(
      'common.authorization.accessDeniedTitle',
    );
    expect(screen.queryByTestId('login-state')).not.toBeInTheDocument();
  });
});

describe('PublicRoute', () => {
  beforeEach(() => {
    authState.isAuthenticated = true;
    authState.isLoading = false;
    authState.error = null;
  });

  it('returns an authenticated user to a safe internal destination', () => {
    render(
      <MemoryRouter
        initialEntries={[{
          pathname: '/login',
          state: { from: { pathname: '/workspaces/ws-1/home', search: '?tab=files', hash: '#top' } },
        }]}
      >
        <Routes>
          <Route
            path="/login"
            element={(
              <PublicRoute>
                <div>login-content</div>
              </PublicRoute>
            )}
          />
          <Route path="/workspaces/*" element={<div>workspace-destination</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('workspace-destination')).toBeInTheDocument();
  });
});
