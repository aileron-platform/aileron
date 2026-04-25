import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, renderWithoutRouter, screen, waitFor, createTestQueryClient } from '@/__tests__/utils/render';
import { NavigationProvider, useNavigation } from '@/app/providers/NavigationProvider';
import {
  cleanupDeletedWorkspaceQueries,
  useWorkspaceDeleteFallback,
} from './useWorkspaceDeleteFallback';

const fetchWorkspaceListMock = vi.fn();

vi.mock('../services/workspaceRuntimeApi', () => ({
  fetchWorkspaceList: (...args: unknown[]) => fetchWorkspaceListMock(...args),
}));

const DeleteFallbackProbe = () => {
  const resolveDeleteFallback = useWorkspaceDeleteFallback();
  const { state, dispatch } = useNavigation();
  const location = useLocation();

  return (
    <div>
      <div data-testid="selected-workspace">{state.selectedWorkspaceId ?? 'null'}</div>
      <div data-testid="current-path">{location.pathname}</div>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_SELECTED_WORKSPACE', payload: 'ws-a' })}
      >
        select-workspace-a
      </button>
      <button
        type="button"
        onClick={() => {
          void resolveDeleteFallback({
            deletedWorkspaceId: 'ws-a',
            deletedRuntimeBaseUrl: 'https://runtime-a.example',
          });
        }}
      >
        resolve-delete
      </button>
    </div>
  );
};

describe('useWorkspaceDeleteFallback', () => {
  beforeEach(() => {
    localStorage.clear();
    fetchWorkspaceListMock.mockReset();
  });

  it('removes workspace-scoped queries for the deleted workspace identity', async () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(['chat', 'ws-a'], { id: 'deleted' });
    queryClient.setQueryData(['canvas', 'https://runtime-a.example'], { id: 'runtime' });
    queryClient.setQueryData(['chat', 'ws-b'], { id: 'kept' });

    await cleanupDeletedWorkspaceQueries(queryClient, 'ws-a', 'https://runtime-a.example');

    expect(queryClient.getQueryData(['chat', 'ws-a'])).toBeUndefined();
    expect(queryClient.getQueryData(['canvas', 'https://runtime-a.example'])).toBeUndefined();
    expect(queryClient.getQueryData(['chat', 'ws-b'])).toEqual({ id: 'kept' });
  });

  it('switches to a fallback workspace after deleting the active workspace', async () => {
    fetchWorkspaceListMock.mockResolvedValue({
      items: [{ id: 'ws-b', name: 'Workspace B' }, { id: 'ws-c', name: 'Workspace C' }],
    });

    const queryClient = createTestQueryClient();
    queryClient.setQueryData(['chat', 'ws-a'], { id: 'deleted' });
    queryClient.setQueryData(['chat', 'ws-b'], { id: 'kept' });

    renderWithoutRouter(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/workspaces/workspace-settings/reset']}>
          <NavigationProvider>
            <DeleteFallbackProbe />
          </NavigationProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-workspace-a' }));
    fireEvent.click(screen.getByRole('button', { name: 'resolve-delete' }));

    await waitFor(() => {
      expect(screen.getByTestId('selected-workspace')).toHaveTextContent('ws-b');
    });
    expect(screen.getByTestId('current-path')).toHaveTextContent('/workspaces');
    expect(queryClient.getQueryData(['chat', 'ws-a'])).toBeUndefined();
  });

  it('navigates to the workspace wizard when no fallback workspace remains', async () => {
    fetchWorkspaceListMock.mockResolvedValue({ items: [] });

    renderWithoutRouter(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter initialEntries={['/workspaces/workspace-settings/reset']}>
          <NavigationProvider>
            <DeleteFallbackProbe />
          </NavigationProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-workspace-a' }));
    fireEvent.click(screen.getByRole('button', { name: 'resolve-delete' }));

    await waitFor(() => {
      expect(screen.getByTestId('selected-workspace')).toHaveTextContent('null');
    });
    expect(screen.getByTestId('current-path')).toHaveTextContent('/workspaces/workspace-wizard');
  });
});
