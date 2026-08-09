import React, { Suspense } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkspaceDeepLinkRoute, WorkspaceRoute } from './WorkspaceRoute';

vi.mock('@/app/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <header data-testid="global-navigation" />,
}));

vi.mock('@/features/workspace/public', () => ({
  WorkspaceFileDeepLinkRoute: () => <div data-testid="workspace-deep-link" />,
  loadWorkspaceModule: () => Promise.resolve({
    default: ({ navigationSlot }: { navigationSlot: React.ReactNode }) => (
      <div data-testid="workspace-module">{navigationSlot}</div>
    ),
  }),
}));

describe('WorkspaceRoute', () => {
  it('injects GlobalNavigation into the lazy Workspace module', async () => {
    render(
      <Suspense fallback={null}>
        <WorkspaceRoute />
      </Suspense>,
    );

    const navigation = await screen.findByTestId('global-navigation');
    expect(navigation.parentElement).toBe(screen.getByTestId('workspace-module'));
  });

  it('renders the deep-link route eagerly without a Suspense boundary', () => {
    render(<WorkspaceDeepLinkRoute />);

    expect(screen.getByTestId('workspace-deep-link')).toBeInTheDocument();
  });
});
