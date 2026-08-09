import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseSidebar } from './KnowledgeBaseSidebar';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const LocationProbe: React.FC = () => {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
};

const renderSidebar = (overrides: Partial<React.ComponentProps<typeof KnowledgeBaseSidebar>> = {}, initialPath = '/knowledge-bases/kb-1/files') => {
  const props: React.ComponentProps<typeof KnowledgeBaseSidebar> = {
    knowledgeBaseId: 'kb-1',
    accessRole: 'owner',
    accessSource: 'owned',
    storageInfo: '2 KB / 4 KB',
    ownerLabel: 'user-1',
    shareCount: 3,
    attachmentCount: 1,
    ...overrides,
  };
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/knowledge-bases/:knowledgeBaseId/*"
          element={(
            <>
              <KnowledgeBaseSidebar {...props} />
              <LocationProbe />
            </>
          )}
        />
      </Routes>
    </MemoryRouter>,
  );
  return props;
};

describe('KnowledgeBaseSidebar', () => {
  it('renders all navigation items and status content', () => {
    renderSidebar();
    for (const key of ['files', 'versionControl', 'sharing', 'workspaces', 'settings']) {
      expect(screen.getByText(`knowledgeBase.navigation.${key}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId('kb-sidebar-status-bar')).toBeInTheDocument();
  });

  it('shows count badges for sharing and workspaces', () => {
    renderSidebar();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('navigates when a navigation item is clicked', () => {
    renderSidebar();
    fireEvent.click(screen.getByText('knowledgeBase.navigation.sharing'));
    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/sharing');
  });

  it('expands the version control submenu and navigates to history', () => {
    renderSidebar();
    fireEvent.click(screen.getByText('knowledgeBase.navigation.versionControl'));
    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/version-control/changes');
    fireEvent.click(screen.getByText('shared.versionControl.mode.commitHistory'));
    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/version-control/history');
  });

  it('renders icon-only navigation content when shell collapses the region', () => {
    renderSidebar({ collapsed: true });
    expect(screen.queryByText('knowledgeBase.navigation.files')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kb-sidebar-status-bar')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.files' })).toBeInTheDocument();
  });

  it('moves role and storage into the bottom status bar', () => {
    renderSidebar();
    const sidebar = screen.getByTestId('kb-sidebar');
    const status = screen.getByTestId('kb-sidebar-status-bar');
    expect(sidebar).toHaveClass('flex', 'h-full', 'min-h-0', 'flex-col');
    expect(screen.getByRole('navigation')).toHaveClass('min-h-0', 'flex-1');
    expect(status.parentElement).toHaveClass('shrink-0');
    expect(status).toHaveTextContent('knowledgeBase.common.role.owner');
    expect(status).toHaveTextContent('2 KB / 4 KB');
  });

  it('navigates to the settings page when the settings item is clicked', () => {
    renderSidebar();
    fireEvent.click(screen.getByText('knowledgeBase.navigation.settings'));
    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/settings');
  });

  it('keeps management routes discoverable for read-only users', () => {
    renderSidebar({ accessRole: 'reader', accessSource: 'direct_share' });
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.sharing' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.workspaces' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.settings' })).toBeInTheDocument();
  });

  it('keeps only status info in the bottom bar without action buttons', () => {
    renderSidebar();
    const status = screen.getByTestId('kb-sidebar-status-bar');
    expect(status).toHaveTextContent('knowledgeBase.common.role.owner');
    expect(within(status).queryAllByRole('button')).toHaveLength(0);
  });

  it('expands the submenu automatically when mounted on a sub route', () => {
    renderSidebar({}, '/knowledge-bases/kb-1/version-control/history');
    expect(screen.getByText('shared.versionControl.mode.commitHistory')).toBeInTheDocument();
  });

  it('shows a hover popup with sub items when collapsed', () => {
    renderSidebar({ collapsed: true });
    fireEvent.mouseEnter(screen.getByRole('button', { name: 'knowledgeBase.navigation.versionControl' }));
    expect(screen.getByText('shared.versionControl.mode.fileChanges')).toBeInTheDocument();
    fireEvent.click(screen.getByText('shared.versionControl.mode.commitHistory'));
    expect(screen.getByTestId('location')).toHaveTextContent('/knowledge-bases/kb-1/version-control/history');
  });
});
