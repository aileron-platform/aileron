import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MarketplaceEditorPage } from './MarketplaceEditorPage';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

const apiMock = vi.hoisted(() => ({
  getPackage: vi.fn(),
  getRootDocument: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../../api/marketplaceApi', async () => {
  const actual = await vi.importActual<typeof import('../../api/marketplaceApi')>('../../api/marketplaceApi');
  return {
    ...actual,
    getPackage: (...args: unknown[]) => apiMock.getPackage(...args),
    getRootDocument: (...args: unknown[]) => apiMock.getRootDocument(...args),
  };
});

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange, placeholder }: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  }) => (
    <textarea
      aria-label={placeholder ?? 'markdown-editor'}
      value={value}
      onChange={event => onChange(event.target.value)}
    />
  ),
}));

const packageDetail = (): MarketplacePackageDetail => ({
  targetClient: 'codex',
  packageFormat: 'codex-native',
  catalogPluginId: 'codex-toolkit',
  userCopyTargetClient: 'codex',
  packageType: 'plugin',
  packageId: 'codex-toolkit',
  displayName: 'Codex Toolkit',
  version: '0.1.0',
  description: 'Package description',
  category: 'coding',
  tags: [],
  indexedResourceNames: [],
  validationSeverity: 'none',
  authoringCapabilities: {
    basic: 'read-write',
    agentsMd: 'read-write',
    hooks: 'read-write',
    mcp: 'read-write',
    agents: 'read-write',
    commands: 'read-write',
    outputStyle: 'unsupported',
    skills: 'read-write',
    files: 'read-write',
  },
  registryPath: 'codex/plugins/codex-toolkit',
  revision: 'rev1',
  updatedAt: '2026-06-26T00:00:00.000Z',
  variants: [{
    targetClient: 'codex',
    packageFormat: 'codex-native',
    packageId: 'codex-toolkit',
    displayName: 'Codex Toolkit',
  }],
  catalogMetadata: {},
  manifestMetadata: {},
  validationResults: [],
});

const renderEditor = (initialEntry = '/marketplace/packages/codex/codex-toolkit/edit/basic') => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route path="/marketplace/packages/:targetClient/:packageId/edit/:section?" element={<MarketplaceEditorPage mode="edit" />} />
      <Route path="/marketplace/packages" element={<div>marketplace-center-route</div>} />
    </Routes>
  </MemoryRouter>,
);

describe('MarketplaceEditorPage', () => {
  beforeEach(() => {
    apiMock.getPackage.mockReset();
    apiMock.getPackage.mockResolvedValue(packageDetail());
    apiMock.getRootDocument.mockReset();
    apiMock.getRootDocument.mockResolvedValue({
      path: 'AGENTS.md',
      content: '# Instructions',
    });
  });

  it('loads package detail and renders packageId as read-only on the basic page', async () => {
    renderEditor();

    await screen.findByDisplayValue('codex/plugins/codex-toolkit');
    expect(screen.getAllByDisplayValue('codex-toolkit')[0]).toHaveAttribute('readonly');
    expect(apiMock.getPackage).toHaveBeenCalledWith('codex', 'codex-toolkit');
  });

  it('renders editor breadcrumbs in the shell bar', async () => {
    renderEditor('/marketplace/packages/codex/codex-toolkit/edit/agentsMd');

    const breadcrumbBar = await screen.findByTestId('feature-shell-breadcrumb-bar');
    expect(breadcrumbBar).toHaveClass('h-10');
    expect(breadcrumbBar).toHaveTextContent('marketplace.breadcrumbs.root');
    expect(breadcrumbBar).toHaveTextContent('marketplace.center.header.title');
    expect(breadcrumbBar).toHaveTextContent('Codex Toolkit');
    expect(breadcrumbBar).toHaveTextContent('marketplace.editor.tabs.agentsMd');
    expect(screen.getAllByTestId('feature-shell-breadcrumb-bar')).toHaveLength(1);
  });

  it('routes the instructions tab to the root document page', async () => {
    renderEditor('/marketplace/packages/codex/codex-toolkit/edit/agentsMd');

    await waitFor(() => expect(apiMock.getPackage).toHaveBeenCalled());
    expect(await screen.findByDisplayValue('# Instructions')).toBeInTheDocument();
  });

  it('does not render overview-derived resource counts in navigation', async () => {
    renderEditor();

    const skillsNavigation = await screen.findByRole('button', { name: 'marketplace.editor.tabs.skills' });
    expect(skillsNavigation).not.toHaveTextContent(/\d/);
  });

  it('shows a recoverable error when the package detail load fails', async () => {
    const user = userEvent.setup();
    apiMock.getPackage.mockRejectedValueOnce(new Error('detail failed'));

    renderEditor();

    expect(await screen.findByText('marketplace.editor.loadError.description')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.loadError.action' }));

    expect(await screen.findByText('marketplace-center-route')).toBeInTheDocument();
  });
});
