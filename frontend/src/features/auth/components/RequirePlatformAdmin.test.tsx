import { render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authState = vi.hoisted(() => ({
  isLoading: false,
  isPlatformAdmin: false,
}));

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => authState,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import { RequirePlatformAdmin } from './RequirePlatformAdmin';

const LocationProbe = () => {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
};

const renderGuard = () => render(
  <MemoryRouter initialEntries={['/user-management/users']}>
    <LocationProbe />
    <RequirePlatformAdmin>
      <div>protected-content</div>
    </RequirePlatformAdmin>
  </MemoryRouter>,
);

describe('RequirePlatformAdmin', () => {
  beforeEach(() => {
    authState.isLoading = false;
    authState.isPlatformAdmin = false;
  });

  it('shows loading state while authorization is loading', () => {
    authState.isLoading = true;
    renderGuard();
    expect(screen.getByTestId('entry-frame')).toBeInTheDocument();
    expect(screen.queryByText('protected-content')).not.toBeInTheDocument();
  });

  it('renders protected content for a platform admin', () => {
    authState.isPlatformAdmin = true;
    renderGuard();
    expect(screen.getByText('protected-content')).toBeInTheDocument();
  });

  it('fails closed for a member without changing the requested URL', () => {
    renderGuard();
    expect(screen.getByRole('alert')).toHaveTextContent(
      'common.authorization.accessDeniedTitle',
    );
    expect(screen.getByTestId('location')).toHaveTextContent(
      '/user-management/users',
    );
    expect(screen.queryByText('protected-content')).not.toBeInTheDocument();
  });
});
