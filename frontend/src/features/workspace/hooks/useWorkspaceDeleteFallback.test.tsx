import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, renderWithoutRouter, screen, waitFor, createTestQueryClient } from '@/__tests__/utils/render';
import {
  WorkspaceSelectionProvider,
  useWorkspaceSelection,
} from '../selection/WorkspaceSelectionContext';
import {
  useWorkspaceDeleteFallback,
} from './useWorkspaceDeleteFallback';

const fetchWorkspaceListMock = vi.fn();

vi.mock('../api/workspaceListApi', () => ({
  fetchWorkspaceList: (...args: unknown[]) => fetchWorkspaceListMock(...args),
}));

const DeleteFallbackProbe = () => {
  const resolveDeleteFallback = useWorkspaceDeleteFallback();
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();
  const location = useLocation();

  return (
    <div>
      <div data-testid="selected-workspace">{selectedWorkspaceId ?? 'null'}</div>
      <div data-testid="current-path">{location.pathname}</div>
      <button
        type="button"
        onClick={() => setSelectedWorkspaceId('ws-a')}
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

  it('switches to a fallback workspace after deleting the active workspace', async () => {
    fetchWorkspaceListMock.mockResolvedValue({
      items: [
        { id: 'ws-b', name: 'Workspace B', accessRole: 'owner' },
        { id: 'ws-c', name: 'Workspace C', accessRole: 'owner' },
      ],
    });

    const queryClient = createTestQueryClient();
    queryClient.setQueryDefaults(['chat', 'ws-b'], { gcTime: Infinity });
    queryClient.setQueryData(['chat', 'ws-a'], { id: 'deleted' });
    queryClient.setQueryData(['canvas', 'https://runtime-a.example'], { id: 'runtime' });
    queryClient.setQueryData(['chat', 'ws-b'], { id: 'kept' });

    renderWithoutRouter(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/workspaces/ws-a/workspace-settings/reset']}>
          <WorkspaceSelectionProvider>
            <DeleteFallbackProbe />
          </WorkspaceSelectionProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-workspace-a' }));
    fireEvent.click(screen.getByRole('button', { name: 'resolve-delete' }));

    await waitFor(() => {
      expect(screen.getByTestId('selected-workspace')).toHaveTextContent('ws-b');
    });
    expect(screen.getByTestId('current-path')).toHaveTextContent('/workspaces/ws-b/home');
    expect(queryClient.getQueryData(['chat', 'ws-a'])).toBeUndefined();
    expect(queryClient.getQueryData(['canvas', 'https://runtime-a.example'])).toBeUndefined();
    expect(queryClient.getQueryData(['chat', 'ws-b'])).toEqual({ id: 'kept' });
  });

  it('navigates to the workspace root when no fallback workspace remains', async () => {
    fetchWorkspaceListMock.mockResolvedValue({ items: [] });

    renderWithoutRouter(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter initialEntries={['/workspaces/ws-a/workspace-settings/reset']}>
          <WorkspaceSelectionProvider>
            <DeleteFallbackProbe />
          </WorkspaceSelectionProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-workspace-a' }));
    fireEvent.click(screen.getByRole('button', { name: 'resolve-delete' }));

    await waitFor(() => {
      expect(screen.getByTestId('selected-workspace')).toHaveTextContent('null');
    });
    expect(screen.getByTestId('current-path')).toHaveTextContent('/workspaces');
  });

  it('clears selection and navigates to the workspace root when fallback loading fails', async () => {
    fetchWorkspaceListMock.mockRejectedValue(new Error('list unavailable'));

    renderWithoutRouter(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter initialEntries={['/workspaces/ws-a/home']}>
          <WorkspaceSelectionProvider>
            <DeleteFallbackProbe />
          </WorkspaceSelectionProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'select-workspace-a' }));
    fireEvent.click(screen.getByRole('button', { name: 'resolve-delete' }));

    await waitFor(() => {
      expect(screen.getByTestId('selected-workspace')).toHaveTextContent('null');
    });
    expect(screen.getByTestId('current-path')).toHaveTextContent('/workspaces');
  });
});
