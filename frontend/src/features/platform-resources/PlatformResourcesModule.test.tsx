import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { PlatformResourcesModule } from './PlatformResourcesModule';

vi.mock('@/shared/components/shell', () => ({
  ProductShell: ({ topBar, body }: { topBar?: React.ReactNode; body: { main: { content: React.ReactNode } } }) => (
    <>{topBar}{body.main.content}</>
  ),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('./PlatformResourcesPage', () => ({
  PlatformResourcesPage: ({
    kind,
    section,
  }: {
    kind: string;
    section: string;
  }) => <div>{`${section}:${kind}`}</div>,
}));

const renderModule = (path: string) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route
        path="/platform-resources/*"
        element={<PlatformResourcesModule navigationSlot={null} />}
      />
    </Routes>
  </MemoryRouter>,
);

describe('PlatformResourcesModule', () => {
  it('keeps the root route focused on workspace management', async () => {
    renderModule('/platform-resources');

    expect(await screen.findByText('management:workspaces')).toBeInTheDocument();
  });

  it('routes analytics independently for both resource kinds', async () => {
    const view = renderModule('/platform-resources/analytics/knowledge-bases');
    expect(await screen.findByText('analytics:knowledge-bases')).toBeInTheDocument();

    view.unmount();
    renderModule('/platform-resources/analytics/workspaces');
    expect(await screen.findByText('analytics:workspaces')).toBeInTheDocument();
  });
});
