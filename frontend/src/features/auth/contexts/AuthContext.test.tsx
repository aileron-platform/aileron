import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { managerSessionService } from '../services/ManagerSessionService';
import { useAuth } from '../hooks/useAuth';
import { AuthProvider } from './AuthContext';

const AuthErrorProbe = () => {
  const { error } = useAuth();
  return <div>{error}</div>;
};

describe('AuthProvider session bootstrap', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not bootstrap again when the window regains focus or visibility', async () => {
    const bootstrap = vi.spyOn(managerSessionService, 'bootstrap').mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <AuthProvider><div>content</div></AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(bootstrap).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
      document.dispatchEvent(new Event('visibilitychange'));
      await Promise.resolve();
    });

    expect(bootstrap).toHaveBeenCalledTimes(1);
  });

  it('preserves a local platform authorization denial from bootstrap', async () => {
    vi.spyOn(managerSessionService, 'bootstrap').mockRejectedValue(
      new Error('PLATFORM_AUTHORIZATION_DENIED'),
    );
    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <AuthProvider><AuthErrorProbe /></AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('PLATFORM_AUTHORIZATION_DENIED')).toBeInTheDocument();
  });
});
