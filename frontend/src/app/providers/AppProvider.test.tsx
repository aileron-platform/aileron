// @vitest-environment jsdom
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useResolvedTheme } from '@/shared/contexts/ResolvedThemeContext';
import { AppProvider, useApp } from './AppProvider';

const authState = vi.hoisted(() => ({
  current: {
    isAuthenticated: false,
    isLoading: false,
    user: null as null | {
      id: string;
      username: string;
      email: string | null;
      display_name: string | null;
      platform_role: 'admin' | 'member';
      allowed_operations: string[];
    },
  },
}));

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('@/features/auth/public', () => ({
  useAuth: () => authState.current,
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

const UserProjection = () => {
  const { state } = useApp();
  return (
    <output data-testid="app-user">
      {JSON.stringify({
        id: state.user.id,
        name: state.user.name,
        email: state.user.email,
      })}
    </output>
  );
};

const ThemeProbe = () => {
  const theme = useResolvedTheme();
  return <div data-testid="resolved-theme">{theme}</div>;
};

describe('AppProvider', () => {
  beforeEach(() => {
    authState.current = {
      isAuthenticated: false,
      isLoading: false,
      user: null,
    };
    apiClientMock.get.mockReset();
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
    document.body.classList.remove('dark');
  });

  it('projects the authenticated manager session without calling the removed user-info route', async () => {
    authState.current = {
      isAuthenticated: true,
      isLoading: false,
      user: {
        id: 'user-1',
        username: 'admin',
        email: 'admin@example.com',
        display_name: 'Local Admin',
        platform_role: 'admin',
        allowed_operations: [],
      },
    };

    render(
      <AppProvider>
        <UserProjection />
      </AppProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('app-user')).toHaveTextContent(JSON.stringify({
        id: 'user-1',
        name: 'Local Admin',
        email: 'admin@example.com',
      }));
    });

    expect(apiClientMock.get).not.toHaveBeenCalled();
  });

  it('provides the stored resolved theme through the shared context', async () => {
    window.localStorage.setItem('mw.settings.general', JSON.stringify({
      theme: 'dark',
      language: 'en',
    }));

    render(
      <AppProvider>
        <ThemeProbe />
      </AppProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('resolved-theme')).toHaveTextContent('dark');
    });
    expect(document.documentElement).toHaveClass('dark');
    expect(document.body).toHaveClass('dark');
  });
});
