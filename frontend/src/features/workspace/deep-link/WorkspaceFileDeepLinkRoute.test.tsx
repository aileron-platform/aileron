import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceFileDeepLinkRoute } from './WorkspaceFileDeepLinkRoute';

const fetchDefaultWorkspaceIdMock = vi.hoisted(() => vi.fn());
let selectedWorkspaceId: string | null = 'ws-selected';

vi.mock('../selection/WorkspaceSelectionContext', () => ({
  useWorkspaceSelection: () => ({
    selectedWorkspaceId,
  }),
}));

vi.mock('@/features/workspace/api/workspaceRuntimeApi', () => ({
  fetchDefaultWorkspaceId: () => fetchDefaultWorkspaceIdMock(),
}));

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
};

const renderRoute = (initialEntry: string) => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route path="/workspace/*" element={<WorkspaceFileDeepLinkRoute />} />
      <Route path="/workspaces/:workspaceId/files" element={<LocationProbe />} />
      <Route path="/workspaces" element={<LocationProbe />} />
    </Routes>
  </MemoryRouter>,
);

describe('WorkspaceFileDeepLinkRoute', () => {
  beforeEach(() => {
    selectedWorkspaceId = 'ws-selected';
    fetchDefaultWorkspaceIdMock.mockReset().mockResolvedValue('ws-default');
  });

  it('redirects a raw workspace file path to the canonical files route with open query', async () => {
    renderRoute('/workspace/.aileron/canvases/demo/page.tsx');

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/workspaces/ws-selected/files?open=%2F.aileron%2Fcanvases%2Fdemo%2Fpage.tsx',
      );
    });
    expect(fetchDefaultWorkspaceIdMock).not.toHaveBeenCalled();
  });

  it('falls back to the default workspace id when none is selected', async () => {
    selectedWorkspaceId = null;

    renderRoute('/workspace/app/projects/page.tsx');

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/workspaces/ws-default/files?open=%2Fapp%2Fprojects%2Fpage.tsx',
      );
    });
    expect(fetchDefaultWorkspaceIdMock).toHaveBeenCalledTimes(1);
  });

  it('drops invalid paths and redirects to canonical files route without open query', async () => {
    renderRoute('/workspace/%2e%2e/secret.ts');

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-selected/files');
    });
  });

  it('rejects encoded slash before React Router splat decoding can rewrite it', async () => {
    renderRoute('/workspace/dir%2Fsecret.ts');

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-selected/files');
    });
  });

  it('rejects traversal hidden behind encoded slash', async () => {
    renderRoute('/workspace/..%2f..%2fsecret.ts');

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-selected/files');
    });
  });

  it('rejects NUL paths without open query', async () => {
    renderRoute('/workspace/dir/%00secret.ts');

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-selected/files');
    });
  });
});
