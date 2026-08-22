import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import type { MarketplaceActionPermissions } from '../../model/marketplacePermissions';
import { MarketplaceDetailPage } from './MarketplaceDetailPage';

const apiMock = vi.hoisted(() => ({
  getPackage: vi.fn(),
  getMarketplaceReadme: vi.fn(),
  getRootDocument: vi.fn(),
  getHooks: vi.fn(),
  listMCPServers: vi.fn(),
  listDocuments: vi.fn(),
  loadDocument: vi.fn(),
}));
const authState = vi.hoisted(() => ({ platformRole: 'admin' as 'admin' | 'member' | null }));
const componentMocks = vi.hoisted(() => ({
  header: vi.fn(),
  installDialog: vi.fn(),
  exportDialog: vi.fn(),
  deleteDialog: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('@/features/auth/public', () => ({
  useAuth: () => authState,
}));

vi.mock('../../api/marketplaceApi', () => apiMock);
vi.mock('../../components/MarketplaceInstallDialog', () => ({
  MarketplaceInstallDialog: (props: { open: boolean }) => {
    componentMocks.installDialog(props);
    return props.open ? <div role="dialog">marketplace-install-dialog</div> : null;
  },
}));
vi.mock('./components/MarketplaceDetailActionDialogs', () => ({
  MarketplaceDeleteDialog: (props: unknown) => {
    componentMocks.deleteDialog(props);
    return null;
  },
  MarketplaceExportDialog: (props: unknown) => {
    componentMocks.exportDialog(props);
    return null;
  },
}));
vi.mock('./components/MarketplacePackageDetailHeader', () => ({
  MarketplacePackageDetailHeader: (props: {
    detail: MarketplacePackageDetail;
    permissions: MarketplaceActionPermissions;
    onInstall: () => void;
  }) => {
    componentMocks.header(props);
    return (
      <>
        <h1>{props.detail.displayName}</h1>
        {props.permissions.canInstall ? (
          <button type="button" onClick={props.onInstall}>marketplace-install-action</button>
        ) : null}
      </>
    );
  },
}));
vi.mock('./components/MarketplaceDetailContentPanels', () => ({
  MarketplaceBasicInfoPanel: () => <div>basic-overview</div>,
  MarketplaceMarkdownDetailPanel: ({ title, content }: { title: string; content: string }) => <div>{title}:{content}</div>,
  MarketplaceHooksWorkflow: () => <div>hooks-workflow</div>,
  MarketplaceMCPWorkflow: ({ servers }: { servers: Array<{ name: string }> }) => (
    <div>mcp-workflow:{servers.map(server => server.name).join(',')}</div>
  ),
}));
vi.mock('./components/MarketplaceDetailFilesSection', () => ({
  MarketplaceDetailFilesSection: ({ mode }: { mode: string }) => <div>{mode}-files</div>,
}));

const detail: MarketplacePackageDetail = {
  targetClient: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  version: '1.0.0',
  description: 'Review package',
  category: 'coding',
  tags: [],
  indexedResourceNames: [],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/review-tools',
  revision: 'rev-1',
  updatedAt: '2026-07-27T00:00:00Z',
  variants: [],
  catalogMetadata: {},
  manifestMetadata: {},
  validationResults: [],
};

const renderPage = (targetClient: MarketplacePackageDetail['targetClient'] = 'codex') => render(
  <MemoryRouter initialEntries={[`/marketplace/packages/${targetClient}/review-tools`]}>
    <Routes>
      <Route path="/marketplace/packages/:targetClient/:packageId" element={<MarketplaceDetailPage />} />
    </Routes>
  </MemoryRouter>,
);

describe('MarketplaceDetailPage lazy resource loading', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.platformRole = 'admin';
    apiMock.getPackage.mockResolvedValue(detail);
    apiMock.getMarketplaceReadme.mockResolvedValue({ revision: 'rev-1', path: 'README.md', content: '# Readme' });
    apiMock.listDocuments.mockResolvedValue([{ id: 'check', title: 'Check', path: 'commands/check.md', resourceType: 'commands' }]);
    apiMock.loadDocument.mockResolvedValue({ id: 'check', title: 'Check', path: 'commands/check.md', resourceType: 'commands', content: '# Check' });
    apiMock.listMCPServers.mockResolvedValue([]);
  });

  it('keeps member reads and install while excluding canonical mutation dialogs', async () => {
    authState.platformRole = 'member';

    renderPage();

    expect(await screen.findByText('basic-overview')).toBeInTheDocument();
    const main = screen.getByRole('main', { name: 'marketplace.detail.main.label' });
    expect(main.firstElementChild?.firstElementChild).toHaveClass('h-full');
    expect(apiMock.getPackage).toHaveBeenCalledWith('codex', 'review-tools');
    expect(componentMocks.header).toHaveBeenLastCalledWith(expect.objectContaining({
      permissions: {
        canEdit: false,
        canDelete: false,
        canExport: true,
        canInstall: true,
        canManageRegistry: false,
      },
    }));
    expect(componentMocks.installDialog).toHaveBeenCalledWith(expect.objectContaining({ open: false }));
    expect(componentMocks.deleteDialog).not.toHaveBeenCalled();
    expect(componentMocks.exportDialog).toHaveBeenCalledWith(expect.objectContaining({
      open: false,
    }));
  });

  it('unmounts an open install dialog immediately when platform access is revoked', async () => {
    const user = userEvent.setup();
    const view = renderPage();

    await screen.findByText('basic-overview');
    await user.click(screen.getByRole('button', { name: 'marketplace-install-action' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('marketplace-install-dialog');

    authState.platformRole = null;
    view.rerender(
      <MemoryRouter initialEntries={['/marketplace/packages/codex/review-tools']}>
        <Routes>
          <Route
            path="/marketplace/packages/:targetClient/:packageId"
            element={<MarketplaceDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'marketplace-install-action' }),
    ).not.toBeInTheDocument();
  });

  it('loads only the overview initially and loads README after its tab opens', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('basic-overview')).toBeInTheDocument();
    expect(apiMock.getPackage).toHaveBeenCalledWith('codex', 'review-tools');
    expect(apiMock.getMarketplaceReadme).not.toHaveBeenCalled();
    expect(apiMock.listDocuments).not.toHaveBeenCalled();

    await user.click(screen.getByRole('tab', { name: 'marketplace.detail.readme.title' }));

    expect(await screen.findByText('marketplace.detail.readme.title:# Readme')).toBeInTheDocument();
    expect(apiMock.getMarketplaceReadme).toHaveBeenCalledWith('codex', 'review-tools');
  });

  it('lists documents when the tab opens and loads content only after selection', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('basic-overview');

    await user.click(screen.getByRole('tab', { name: 'marketplace.features.slashCommands' }));
    await waitFor(() => expect(apiMock.listDocuments).toHaveBeenCalledWith('codex', 'review-tools', 'commands'));
    expect(apiMock.loadDocument).not.toHaveBeenCalled();

    await user.click(await screen.findByRole('button', { name: 'Check' }));

    expect(await screen.findByText('Check:# Check')).toBeInTheDocument();
    expect(apiMock.loadDocument).toHaveBeenCalledWith('codex', 'review-tools', 'commands', 'commands/check.md');
  });

  it('shows a resource error and retries a failed README load', async () => {
    const user = userEvent.setup();
    apiMock.getMarketplaceReadme
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce({ revision: 'rev-1', path: 'README.md', content: '# Retried' });
    renderPage();
    await screen.findByText('basic-overview');

    await user.click(screen.getByRole('tab', { name: 'marketplace.detail.readme.title' }));

    expect(await screen.findByText('marketplace.common.resourceLoadError')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.retry' }));

    expect(await screen.findByText('marketplace.detail.readme.title:# Retried')).toBeInTheDocument();
    expect(apiMock.getMarketplaceReadme).toHaveBeenCalledTimes(2);
  });

  it('keeps the latest selected document when an older request finishes last', async () => {
    const user = userEvent.setup();
    let resolveFirst!: (value: unknown) => void;
    let resolveSecond!: (value: unknown) => void;
    apiMock.listDocuments.mockResolvedValueOnce([
      { id: 'first', title: 'First', path: 'commands/first.md', resourceType: 'commands' },
      { id: 'second', title: 'Second', path: 'commands/second.md', resourceType: 'commands' },
    ]);
    apiMock.loadDocument
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve; }));
    renderPage();
    await screen.findByText('basic-overview');
    await user.click(screen.getByRole('tab', { name: 'marketplace.features.slashCommands' }));
    await user.click(await screen.findByRole('button', { name: 'First' }));
    await user.click(screen.getByRole('button', { name: 'Second' }));

    resolveSecond({
      id: 'second',
      title: 'Second',
      path: 'commands/second.md',
      resourceType: 'commands',
      content: '# Second',
    });
    expect(await screen.findByText('Second:# Second')).toBeInTheDocument();
    resolveFirst({
      id: 'first',
      title: 'First',
      path: 'commands/first.md',
      resourceType: 'commands',
      content: '# First',
    });

    await waitFor(() => {
      expect(screen.getByText('Second:# Second')).toBeInTheDocument();
      expect(screen.queryByText('First:# First')).not.toBeInTheDocument();
    });
  });

  it('uses the editor empty states for empty MCP and document resources', async () => {
    const user = userEvent.setup();
    apiMock.getPackage.mockResolvedValueOnce({
      ...detail,
      targetClient: 'claude-code',
    });
    apiMock.listDocuments.mockResolvedValue([]);
    renderPage('claude-code');
    await screen.findByText('basic-overview');

    const emptyResources = [
      {
        tab: 'marketplace.features.mcp',
        title: 'marketplace.editor.featureSections.mcp.emptyTitle',
        description: 'marketplace.editor.featureSections.mcp.emptyDescription',
      },
      {
        tab: 'marketplace.features.subagents',
        title: 'marketplace.editor.featureSections.agents.emptyTitle',
        description: 'marketplace.editor.featureSections.agents.emptyDescription',
      },
      {
        tab: 'marketplace.features.slashCommands',
        title: 'marketplace.editor.featureSections.commands.emptyTitle',
        description: 'marketplace.editor.featureSections.commands.emptyDescription',
      },
      {
        tab: 'marketplace.features.outputStyle',
        title: 'marketplace.editor.featureSections.outputStyle.emptyTitle',
        description: 'marketplace.editor.featureSections.outputStyle.emptyDescription',
      },
    ];

    for (const resource of emptyResources) {
      await user.click(screen.getByRole('tab', { name: resource.tab }));
      expect(await screen.findByText(resource.title)).toBeInTheDocument();
      expect(screen.getByText(resource.description)).toBeInTheDocument();
    }

  });

  it('renders every MCP server in the single content column without a server selector', async () => {
    const user = userEvent.setup();
    apiMock.listMCPServers.mockResolvedValueOnce([
      {
        name: 'first',
        path: '.mcp.json',
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'first-fp',
        server: { command: 'first' },
      },
      {
        name: 'second',
        path: '.mcp.json',
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'second-fp',
        server: { command: 'second' },
      },
    ]);
    renderPage();
    await screen.findByText('basic-overview');
    await user.click(screen.getByRole('tab', { name: 'marketplace.features.mcp' }));

    expect(await screen.findByText('mcp-workflow:first,second')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'first' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'second' })).not.toBeInTheDocument();
  });

  it('retries the complete MCP tab load when the server inventory fails', async () => {
    const user = userEvent.setup();
    apiMock.listMCPServers
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce([{
        name: 'retry-server',
        path: '.mcp.json',
        server: { command: 'retry' },
        ownerFilePath: '.mcp.json',
        baseEntryFingerprint: 'retry-fp',
      }]);
    renderPage();
    await screen.findByText('basic-overview');
    await user.click(screen.getByRole('tab', { name: 'marketplace.features.mcp' }));

    expect(await screen.findByText('marketplace.common.resourceLoadError')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.retry' }));

    expect(await screen.findByText('mcp-workflow:retry-server')).toBeInTheDocument();
    expect(apiMock.listMCPServers).toHaveBeenCalledTimes(2);
  });
});
