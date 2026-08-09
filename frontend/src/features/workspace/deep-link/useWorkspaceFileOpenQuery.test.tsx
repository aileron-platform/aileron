import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { useWorkspaceFileOpenQuery } from './useWorkspaceFileOpenQuery';

const useWorkspaceMock = vi.hoisted(() => vi.fn());

vi.mock('../providers/WorkspaceProvider', () => ({
  useWorkspace: () => useWorkspaceMock(),
}));

const Probe = () => {
  const location = useLocation();
  useWorkspaceFileOpenQuery();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
};

describe('useWorkspaceFileOpenQuery', () => {
  it('opens a query file after runtime and restore status match the route workspace id and context', async () => {
    const dispatch = vi.fn();
    const openFileInTab = vi.fn();
    useWorkspaceMock.mockReturnValue({
      dispatch,
      fileManagementTabsRestoreStatus: {
        ready: true,
        workspaceId: 'ws-1',
        contextId: null,
      },
      state: {
        versionControl: {
          selectedGitContextId: null,
        },
      },
      openFileInTab,
      workspaceRuntime: { workspaceId: 'ws-1' },
    });

    render(
      <MemoryRouter initialEntries={['/workspaces/ws-1/files?open=%2Fnew%2Ffile.ts']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/files" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(openFileInTab).toHaveBeenCalledWith('/new/file.ts');
    });
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_CURRENT_FEATURE', payload: 'file-management' });
    expect(dispatch).toHaveBeenCalledWith({ type: 'ENSURE_NAVIGATION_ITEM_EXPANDED', payload: 'file-management' });
    expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-1/files');
  });

  it('does not open query until runtime and restore status match the route workspace id', async () => {
    const openFileInTab = vi.fn();
    useWorkspaceMock.mockReturnValue({
      dispatch: vi.fn(),
      fileManagementTabsRestoreStatus: {
        ready: true,
        workspaceId: 'ws-old',
        contextId: null,
      },
      state: {
        versionControl: {
          selectedGitContextId: null,
        },
      },
      openFileInTab,
      workspaceRuntime: { workspaceId: 'ws-old' },
    });

    render(
      <MemoryRouter initialEntries={['/workspaces/ws-new/files?open=%2Fnew%2Ffile.ts']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/files" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(openFileInTab).not.toHaveBeenCalled();
    });
  });

  it('does not open query until restore status context matches selected git context', async () => {
    const openFileInTab = vi.fn();
    useWorkspaceMock.mockReturnValue({
      dispatch: vi.fn(),
      fileManagementTabsRestoreStatus: {
        ready: true,
        workspaceId: 'ws-1',
        contextId: null,
      },
      state: {
        versionControl: {
          selectedGitContextId: 'worktree:feature',
        },
      },
      openFileInTab,
      workspaceRuntime: { workspaceId: 'ws-1' },
    });

    render(
      <MemoryRouter initialEntries={['/workspaces/ws-1/files?open=%2Fnew%2Ffile.ts']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/files" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(openFileInTab).not.toHaveBeenCalled();
    });
  });
});
