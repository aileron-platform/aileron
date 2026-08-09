import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithoutRouter } from '@/__tests__/utils/render';
import { MarketplaceCenterPage } from './MarketplaceCenterPage';
import type { MarketplaceListResult, MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';

const mockNavigate = vi.fn();
const authState = vi.hoisted(() => ({ platformRole: 'admin' as 'admin' | 'member' | null }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/features/auth/public', () => ({
  useAuth: () => authState,
}));

const mockPackage: MarketplacePackageSummary = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'figma-context',
  displayName: 'Figma Context',
  version: '0.1.0',
  description: 'Figma context plugin.',
  category: 'coding',
  tags: ['mcp'],
  sourceType: 'created',
  indexedResourceNames: ['mcp'],
  validationSeverity: 'none',
  lifecycleStatus: 'ready',
  registryPath: 'codex/plugins/figma-context',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [{
    provider: 'codex',
    packageId: 'figma-context',
    displayName: 'Figma Context',
    registryPath: 'codex/plugins/figma-context',
    revision: 'rev-1',
  }],
};

const mockListResult: MarketplaceListResult = {
  items: [mockPackage],
  total: 1,
  page: 1,
  pageSize: 12,
  totalPages: 1,
  categories: ['coding'],
  sourceTypes: ['created'],
  validationSeverities: ['none'],
};

const mockInstallPlugin = vi.fn();
const mockDeletePackage = vi.fn();
const mockExportPackage = vi.fn();
const mockGetRegistrySettings = vi.fn();
const mockInitializeRegistry = vi.fn();
const mockListPackages = vi.fn();
const mockCreatePackage = vi.fn();
const mockScanImportSource = vi.fn();
const mockImportCandidates = vi.fn();
const mockToast = vi.fn();

vi.mock('../../api/marketplaceApi', () => ({
  createPackage: (...args: unknown[]) => mockCreatePackage(...args),
  getRegistrySettings: (...args: unknown[]) => mockGetRegistrySettings(...args),
  preflightMarketplaceUserCopy: vi.fn(),
  createMarketplaceUserCopy: vi.fn(),
  listPackages: (...args: unknown[]) => mockListPackages(...args),
  scanImportSource: (...args: unknown[]) => mockScanImportSource(...args),
  importCandidates: (...args: unknown[]) => mockImportCandidates(...args),
  installMarketplacePlugin: (...args: unknown[]) => mockInstallPlugin(...args),
  exportPackage: (...args: unknown[]) => mockExportPackage(...args),
  deletePackage: (...args: unknown[]) => mockDeletePackage(...args),
}));

vi.mock('@/shared/version-control', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/version-control')>()),
  useMarketplaceVersionControlSession: () => ({
    remote: {
      useInitializeRepositoryMutation: () => ({
        mutateAsync: (...args: unknown[]) => mockInitializeRegistry(...args),
      }),
    },
  }),
}));

vi.mock('@/features/workspace/public', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/workspace/public')>()),
  fetchWorkspaceList: vi.fn(async () => ({
    items: [
      {
        id: 'ws-1',
        name: 'Workspace One',
        accessRole: 'manager',
        agenticTools: ['codex'],
      },
      {
        id: 'ws-2',
        name: 'Workspace Two',
        accessRole: 'manager',
        agenticTools: ['claude-code'],
      },
    ],
  })),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

const renderCenter = () => renderWithoutRouter(
  <MemoryRouter>
    <MarketplaceCenterPage />
  </MemoryRouter>,
);

const renderCenterStrict = () => renderWithoutRouter(
  <StrictMode>
    <MemoryRouter>
      <MarketplaceCenterPage />
    </MemoryRouter>
  </StrictMode>,
);

const openImportDialog = async () => {
  await screen.findByText('Figma Context');
  fireEvent.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
  return within(await screen.findByRole('dialog'));
};

const scanGitImport = async (source = 'git@github.com:example/marketplace.git') => {
  const dialog = await openImportDialog();
  fireEvent.change(dialog.getByLabelText('marketplace.import.fields.source'), {
    target: { value: source },
  });
  const user = userEvent.setup();
  await user.click(dialog.getByRole('button', { name: 'marketplace.import.actions.scan' }));
  return dialog;
};

describe('MarketplaceCenterPage', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
    window.localStorage.clear();
    authState.platformRole = 'admin';
    mockGetRegistrySettings.mockReset();
    mockInitializeRegistry.mockReset();
    mockListPackages.mockReset();
    mockCreatePackage.mockReset();
    mockNavigate.mockReset();
    mockInstallPlugin.mockReset();
    mockDeletePackage.mockReset();
    mockExportPackage.mockReset();
    mockScanImportSource.mockReset();
    mockImportCandidates.mockReset();
    mockToast.mockReset();
    mockGetRegistrySettings.mockResolvedValue({
      displayName: 'Local Marketplace Registry',
      rootPath: '~/.ai-developer-hub/marketplace',
      status: 'ready',
      maintainerName: 'Current user',
      maintainerEmail: 'current.user@example.local',
    });
    mockInitializeRegistry.mockResolvedValue({});
    mockListPackages.mockResolvedValue(mockListResult);
    mockInstallPlugin.mockResolvedValue({
      status: 'installed',
      provider: 'codex',
      packageId: 'figma-context',
      marketplaceId: 'team-tools',
      workspaceId: 'ws-1',
      operationId: 'a'.repeat(32),
      stage: 'completed',
      exitCode: 0,
      cliMessage: 'Installed',
      stdout: null,
      stderr: null,
      truncated: false,
    });
    mockDeletePackage.mockResolvedValue({ deleted: true });
    mockExportPackage.mockResolvedValue({ archiveName: 'pkg.zip' });
    mockScanImportSource.mockResolvedValue([
      {
        id: 'claude-code:review-assistant',
        provider: 'claude-code',
        packageId: 'review-assistant',
        displayName: 'Review Assistant',
        sourcePath: 'plugins/review-assistant',
        duplicate: false,
        duplicateAction: 'skip',
        variantStatus: 'new-family',
        variants: [],
        validationSeverity: 'warning',
        validationResults: [{
          severity: 'warning',
          code: 'marketplace.validation.metadata_conflict',
          messageKey: 'marketplace.validation.metadata_conflict',
        }],
      },
      {
        id: 'claude-code:existing-package',
        provider: 'claude-code',
        packageId: 'existing-package',
        displayName: 'Existing Package',
        sourcePath: 'plugins/existing-package',
        duplicate: true,
        duplicateAction: 'skip',
        newPackageId: 'existing-package-copy',
        variantStatus: 'duplicate-variant',
        variants: [{
          provider: 'claude-code',
          packageId: 'existing-package',
          displayName: 'Existing Package',
        }],
        validationSeverity: 'warning',
        validationResults: [{
          severity: 'warning',
          code: 'marketplace.import.duplicate',
          messageKey: 'marketplace.import.validation.duplicate',
        }],
      },
    ]);
    mockImportCandidates.mockResolvedValue({ imported: [], skipped: [], failed: [], warnings: [] });
  });

  it('single-flights identical initial requests under StrictMode', async () => {
    renderCenterStrict();

    expect(await screen.findByText('Figma Context')).toBeInTheDocument();
    expect(mockGetRegistrySettings).toHaveBeenCalledTimes(1);
    expect(mockListPackages).toHaveBeenCalledTimes(1);
    expect(mockListPackages).toHaveBeenCalledWith({
      q: '',
      provider: 'all',
      category: 'all',
      features: [],
      sort: 'updatedAt',
      direction: 'desc',
      page: 1,
      pageSize: 12,
    });
  });

  it('does not share in-flight package data across page instances', async () => {
    let resolveFirst!: (result: MarketplaceListResult) => void;
    mockListPackages
      .mockImplementationOnce(() => new Promise(resolve => {
        resolveFirst = resolve;
      }))
      .mockResolvedValueOnce({
        ...mockListResult,
        items: [{
          ...mockPackage,
          packageId: 'second-instance',
          displayName: 'Second Instance',
        }],
      });

    const first = renderCenter();
    await waitFor(() => {
      expect(mockListPackages).toHaveBeenCalledTimes(1);
    });
    first.unmount();

    renderCenter();
    expect(await screen.findByText('Second Instance')).toBeInTheDocument();
    expect(mockListPackages).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveFirst(mockListResult);
    });
    expect(screen.getByText('Second Instance')).toBeInTheDocument();
  });

  it('resets the page and applies a filter in one package request', async () => {
    const user = userEvent.setup();
    mockListPackages.mockResolvedValue({
      ...mockListResult,
      totalPages: 2,
    });
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', {
      name: 'marketplace.center.pagination.next',
    }));
    await waitFor(() => {
      expect(mockListPackages).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 }),
      );
    });
    mockListPackages.mockClear();

    await user.click(screen.getByRole('button', {
      name: 'marketplace.providers.codex',
    }));

    await waitFor(() => {
      expect(mockListPackages).toHaveBeenCalledTimes(1);
      expect(mockListPackages).toHaveBeenCalledWith(
        expect.objectContaining({
          provider: 'codex',
          page: 1,
        }),
      );
    });
  });

  it('ignores an older package response that completes after the latest query', async () => {
    let resolveInitial!: (result: MarketplaceListResult) => void;
    let resolveFiltered!: (result: MarketplaceListResult) => void;
    mockListPackages
      .mockImplementationOnce(() => new Promise(resolve => {
        resolveInitial = resolve;
      }))
      .mockImplementationOnce(() => new Promise(resolve => {
        resolveFiltered = resolve;
      }));
    renderCenter();

    await waitFor(() => {
      expect(mockListPackages).toHaveBeenCalledTimes(1);
    });
    fireEvent.click(screen.getByRole('button', {
      name: 'marketplace.providers.codex',
    }));
    await waitFor(() => {
      expect(mockListPackages).toHaveBeenCalledTimes(2);
    });

    const filteredPackage = {
      ...mockPackage,
      packageId: 'latest-package',
      displayName: 'Latest Package',
    };
    await act(async () => {
      resolveFiltered({
        ...mockListResult,
        items: [filteredPackage],
      });
    });
    expect(await screen.findByText('Latest Package')).toBeInTheDocument();

    await act(async () => {
      resolveInitial(mockListResult);
    });
    expect(screen.getByText('Latest Package')).toBeInTheDocument();
    expect(screen.queryByText('Figma Context')).not.toBeInTheDocument();
  });

  it('issues a fresh package request when the user refreshes', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    mockListPackages.mockClear();
    await user.click(screen.getByRole('button', {
      name: 'marketplace.center.actions.refresh',
    }));

    await waitFor(() => {
      expect(mockListPackages).toHaveBeenCalledTimes(1);
    });
  });

  it('renders Marketplace breadcrumbs in the center header', async () => {
    renderCenter();

    expect(await screen.findByText('marketplace.center.header.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.breadcrumbs.root')).toBeInTheDocument();
  });

  it('keeps member browse and install access without canonical management surfaces', async () => {
    authState.platformRole = 'member';

    renderCenter();

    await screen.findByText('Figma Context');
    expect(mockListPackages).toHaveBeenCalled();
    expect(mockGetRegistrySettings).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('button', { name: 'marketplace.center.actions.import' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'marketplace.center.actions.create' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'marketplace.center.actions.settings' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'marketplace.center.card.actions.install' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'marketplace.center.card.actions.export' }),
    ).toBeEnabled();
    expect(mockInitializeRegistry).not.toHaveBeenCalled();
    expect(mockCreatePackage).not.toHaveBeenCalled();
    expect(mockScanImportSource).not.toHaveBeenCalled();
    expect(mockImportCandidates).not.toHaveBeenCalled();
    expect(mockInstallPlugin).not.toHaveBeenCalled();
    expect(mockDeletePackage).not.toHaveBeenCalled();
  });

  it('creates a provider-native package from the header dialog and navigates to the editor', async () => {
    const user = userEvent.setup();
    const createdPackage: MarketplacePackageSummary = {
      provider: 'codex',
      packageType: 'plugin',
      packageId: 'review-helper',
      displayName: 'Review Helper',
      version: '0.1.0',
      description: 'Helps review changes',
      category: 'coding',
      tags: [],
      sourceType: 'created',
      indexedResourceNames: [],
      validationSeverity: 'none',
      lifecycleStatus: 'ready',
      registryPath: 'codex/plugins/review-helper',
      revision: 'rev-created',
      updatedAt: '2026-06-27T00:00:00.000Z',
      variants: [{
        provider: 'codex',
        packageId: 'review-helper',
        displayName: 'Review Helper',
        registryPath: 'codex/plugins/review-helper',
        revision: 'rev-created',
      }],
    };
    mockCreatePackage.mockResolvedValueOnce(createdPackage);

    renderCenter();

    await user.click(await screen.findByRole('button', { name: 'marketplace.center.actions.create' }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'marketplace.createPackage.fields.provider' }));
    await user.click(screen.getByRole('option', { name: 'marketplace.providers.codex' }));
    await user.type(screen.getByLabelText('marketplace.createPackage.fields.packageId'), 'review-helper');
    await user.type(screen.getByLabelText('marketplace.createPackage.fields.displayName'), 'Review Helper');
    await user.type(screen.getByLabelText('marketplace.createPackage.fields.description'), 'Helps review changes');
    await user.click(screen.getByRole('button', { name: 'marketplace.createPackage.actions.create' }));

    await waitFor(() => expect(mockCreatePackage).toHaveBeenCalledWith({
      provider: 'codex',
      packageId: 'review-helper',
      displayName: 'Review Helper',
      description: 'Helps review changes',
    }));
    expect(mockNavigate).toHaveBeenCalledWith('/marketplace/packages/codex/review-helper/edit/basic');
  });

  it('keeps the create dialog open with the entered values when package creation fails', async () => {
    const user = userEvent.setup();
    mockCreatePackage.mockRejectedValueOnce(new Error('Package already exists'));

    renderCenter();

    await user.click(await screen.findByRole('button', { name: 'marketplace.center.actions.create' }));
    await user.type(screen.getByLabelText('marketplace.createPackage.fields.packageId'), 'review-helper');
    await user.type(screen.getByLabelText('marketplace.createPackage.fields.displayName'), 'Review Helper');
    await user.type(screen.getByLabelText('marketplace.createPackage.fields.description'), 'Helps review changes');
    await user.click(screen.getByRole('button', { name: 'marketplace.createPackage.actions.create' }));

    expect(await screen.findByText('marketplace.createPackage.errors.generic')).toBeInTheDocument();
    expect(screen.getByLabelText('marketplace.createPackage.fields.packageId')).toHaveValue('review-helper');
    expect(screen.getByLabelText('marketplace.createPackage.fields.displayName')).toHaveValue('Review Helper');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows first-run onboarding and initializes the local registry before browsing', async () => {
    const user = userEvent.setup();
    mockGetRegistrySettings
      .mockResolvedValueOnce({
        displayName: 'Local Marketplace Registry',
        rootPath: '~/.ai-developer-hub/marketplace',
        status: 'uninitialized',
      })
      .mockResolvedValueOnce({
        displayName: 'Local Marketplace Registry',
        rootPath: '~/.ai-developer-hub/marketplace',
        status: 'ready',
        maintainerName: 'Current user',
        maintainerEmail: 'current.user@example.local',
      });
    renderCenter();

    expect(await screen.findByText('marketplace.onboarding.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.onboarding.rootPath')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /marketplace\.onboarding\.actions\.initialize/ }));

    await waitFor(() => {
      expect(mockInitializeRegistry).toHaveBeenCalled();
    });
    expect(await screen.findByText('Figma Context')).toBeInTheDocument();
  });

  it('retries package loading after a localized list error', async () => {
    const user = userEvent.setup();
    mockListPackages
      .mockRejectedValueOnce(new Error('marketplace.list.failed'))
      .mockResolvedValueOnce(mockListResult);
    renderCenter();

    expect(await screen.findByText('marketplace.center.list.error.title')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.center.list.error.retry' }));

    expect(await screen.findByText('Figma Context')).toBeInTheDocument();
  });

  it('renders filters sidebar and package list with the shared resizable sidebar', async () => {
    renderCenter();

    expect(await screen.findByText('Figma Context')).toBeInTheDocument();
    expect(screen.getByText('marketplace.center.filters.searchLabel')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'shared.shell.collapseSidebar' })).not.toBeInTheDocument();
    expect(screen.getByRole('separator')).toBeInTheDocument();
    expect(screen.queryByRole('separator', { name: 'Resize column' })).not.toBeInTheDocument();
  });

  it('renders the empty state and resets active filters', async () => {
    const user = userEvent.setup();
    mockListPackages.mockResolvedValue({
      ...mockListResult,
      items: [],
      total: 0,
      totalPages: 1,
      categories: ['coding'],
    });
    renderCenter();

    const emptyTitle = await screen.findByText('marketplace.center.list.empty.title');
    expect(emptyTitle).toBeInTheDocument();
    expect(emptyTitle.parentElement?.querySelector('svg')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.center.list.empty.reset' }));

    await waitFor(() => {
      expect(mockListPackages).toHaveBeenLastCalledWith(expect.objectContaining({
        provider: 'all',
        category: 'all',
        features: [],
        page: 1,
      }));
    });
  });

  it('persists last-used filters and view mode in localStorage', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.providers.codex' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.features.mcp' }));
    await user.click(screen.getByRole('button', { name: 'coding' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.viewModes.list' }));

    await waitFor(() => {
      expect(window.localStorage.getItem('marketplace.center.filters.v1:local-user')).toContain('"provider":"codex"');
      expect(window.localStorage.getItem('marketplace.center.filters.v1:local-user')).toContain('"category":"coding"');
      expect(window.localStorage.getItem('marketplace.center.filters.v1:local-user')).toContain('"mcp"');
      expect(window.localStorage.getItem('marketplace.center.viewMode.v1:local-user')).toBe('list');
    });
  });

  it('prefers current workspace context before remembered install workspace', async () => {
    const user = userEvent.setup();
    window.localStorage.setItem('selectedWorkspaceId', 'ws-1');
    window.localStorage.setItem('marketplace.install.lastWorkspace.v1:local-user', 'ws-2');
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.install' }));
    await screen.findByText('marketplace.install.plugin.publishReady');
    const installButtons = screen.getAllByRole('button', { name: 'marketplace.install.actions.install' });
    await user.click(installButtons[installButtons.length - 1]);

    await waitFor(() => {
      expect(mockInstallPlugin).toHaveBeenCalledWith(expect.objectContaining({
        workspaceId: 'ws-1',
      }));
    });
  });

  it('shows install failures from the center action dialog', async () => {
    const user = userEvent.setup();
    mockInstallPlugin.mockResolvedValue({
      status: 'failed',
      provider: 'codex',
      packageId: 'figma-context',
      marketplaceId: 'team-tools',
      workspaceId: 'ws-1',
      operationId: 'b'.repeat(32),
      stage: 'plugin-install',
      exitCode: 1,
      cliMessage: 'Codex CLI rejected the plugin',
      stdout: null,
      stderr: 'codex missing',
      truncated: false,
    });
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.install' }));
    await screen.findByText('marketplace.install.plugin.publishReady');
    const installButtons = screen.getAllByRole('button', { name: 'marketplace.install.actions.install' });
    await user.click(installButtons[installButtons.length - 1]);

    expect(await screen.findAllByText('Codex CLI rejected the plugin'))
      .toHaveLength(2);
    expect(screen.getByText('codex missing')).toBeInTheDocument();
  });

  it('exports packages from the center action dialog', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.export' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.export.actions.export' }));

    await waitFor(() => {
      expect(mockExportPackage).toHaveBeenCalledWith({
        provider: 'codex',
        packageId: 'figma-context',
        revision: 'rev-1',
      });
    });
    expect(screen.getByText('marketplace.export.result.ready')).toBeInTheDocument();
  });

  it('localizes action API errors without exposing backend messages', async () => {
    const user = userEvent.setup();
    const backendMessage = '\u4f60\u6c92\u6709\u6b0a\u9650\u57f7\u884c\u6b64 Marketplace \u64cd\u4f5c';
    mockExportPackage.mockRejectedValue(new Error(backendMessage));
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.export' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.export.actions.export' }));

    expect(
      await screen.findByText('marketplace.export.result.failed'),
    ).toBeInTheDocument();
    expect(screen.queryByText(backendMessage)).not.toBeInTheDocument();
  });

  it('scans HTTPS repository URLs using the default branch', async () => {
    renderCenter();

    const dialog = await scanGitImport('https://github.com/example/marketplace.git');
    expect(await dialog.findByText('Review Assistant')).toBeInTheDocument();
    expect(mockScanImportSource).toHaveBeenCalledWith(expect.objectContaining({
      source: 'https://github.com/example/marketplace.git',
    }));
    expect(mockScanImportSource).toHaveBeenCalledWith(expect.not.objectContaining({
      ref: expect.any(String),
    }));
  });

  it('does not render branch selection in the import flow', async () => {
    renderCenter();

    const dialog = await openImportDialog();
    expect(dialog.getAllByRole('combobox')).toHaveLength(2);
    expect(dialog.getByRole('button', { name: 'marketplace.import.actions.scan' })).toBeInTheDocument();
  });

  it('requires typing the package id before deleting a package from the list row', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.viewModes.list' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.delete' }));

    const deleteButtons = screen.getAllByRole('button', { name: 'marketplace.delete.actions.delete' });
    const confirmDelete = deleteButtons[deleteButtons.length - 1];
    expect(confirmDelete).toBeDisabled();

    await user.type(screen.getByLabelText('marketplace.delete.fields.confirm'), mockPackage.packageId);
    expect(confirmDelete).toBeEnabled();
    await user.click(confirmDelete);

    await waitFor(() => {
      expect(mockDeletePackage).toHaveBeenCalledWith(expect.objectContaining({
        provider: 'codex',
        packageId: 'figma-context',
        revision: 'rev-1',
      }));
    });
  });

  it('unmounts an open delete dialog immediately when Admin is downgraded to Member', async () => {
    const user = userEvent.setup();
    const view = renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.viewModes.list' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.delete' }));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();

    authState.platformRole = 'member';
    view.rerender(
      <MemoryRouter>
        <MarketplaceCenterPage />
      </MemoryRouter>,
    );

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'marketplace.center.card.actions.delete' }),
    ).not.toBeInTheDocument();
    expect(mockDeletePackage).not.toHaveBeenCalled();
  });

  it('keeps delete dialog open when center delete hits a revision conflict', async () => {
    const user = userEvent.setup();
    mockDeletePackage.mockResolvedValue({
      deleted: false,
      errorCode: 'marketplace.package.revision_conflict',
    });
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.viewModes.list' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.delete' }));
    await user.type(screen.getByLabelText('marketplace.delete.fields.confirm'), mockPackage.packageId);
    const deleteButtons = screen.getAllByRole('button', { name: 'marketplace.delete.actions.delete' });
    await user.click(deleteButtons[deleteButtons.length - 1]);

    expect(
      await screen.findByText(
        'marketplace.install.errors.packageRevisionConflict',
      ),
    ).toBeInTheDocument();
  });

  it('scans import candidates without selecting them by default and imports selected candidates', async () => {
    renderCenter();

    const dialog = await scanGitImport();
    expect(await dialog.findByText('Review Assistant')).toBeInTheDocument();
    expect(dialog.getByText('Existing Package')).toBeInTheDocument();
    expect(dialog.queryByText('marketplace.import.variantStatuses.new-family')).not.toBeInTheDocument();
    expect(dialog.queryByText('marketplace.import.variantStatuses.duplicate-variant')).not.toBeInTheDocument();
    expect(dialog.getByText('marketplace.import.candidates.duplicate')).toBeInTheDocument();
    expect(dialog.queryByText('marketplace.validation.metadata_conflict')).not.toBeInTheDocument();
    expect(dialog.getByText('marketplace.import.validation.duplicate')).toBeInTheDocument();
    expect(dialog.getByRole('button', { name: 'marketplace.import.actions.import' })).toBeDisabled();
    const candidateCheckboxes = dialog.getAllByRole('checkbox');
    expect(candidateCheckboxes).toHaveLength(2);
    expect(candidateCheckboxes.every(checkbox => !(checkbox as HTMLInputElement).checked)).toBe(true);

    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    expect(dialog.getByRole('button', { name: 'marketplace.import.actions.selectAll' })).toBeDisabled();
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.clearSelection' }));
    expect(dialog.getByRole('button', { name: 'marketplace.import.actions.import' })).toBeDisabled();
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockScanImportSource).toHaveBeenCalledWith(expect.objectContaining({
        provider: 'all',
        sourceKind: 'git',
      }));
      expect(mockScanImportSource).toHaveBeenCalledWith(expect.not.objectContaining({
        ref: expect.any(String),
      }));
      expect(mockImportCandidates).toHaveBeenCalledWith([
        expect.objectContaining({
          packageId: 'review-assistant',
          duplicate: false,
        }),
        expect.objectContaining({
          packageId: 'existing-package',
          duplicate: true,
        }),
      ]);
    });
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'marketplace.import.result.summary',
        variant: 'success',
      }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('reveals imported packages by clearing filters and switching to the imported provider', async () => {
    mockImportCandidates.mockResolvedValue({
      imported: [{
        ...mockPackage,
        provider: 'claude-code',
        packageId: 'review-assistant',
        displayName: 'Review Assistant',
      }],
      skipped: [],
      failed: [],
      warnings: [],
    });
    renderCenter();

    await screen.findByText('Figma Context');
    fireEvent.click(screen.getByRole('button', { name: 'marketplace.providers.codex' }));
    fireEvent.click(screen.getByRole('button', { name: 'marketplace.features.mcp' }));
    const dialog = await scanGitImport();
    expect(await dialog.findByText('Review Assistant')).toBeInTheDocument();
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    mockListPackages.mockClear();
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockListPackages).toHaveBeenCalledTimes(1);
      expect(mockListPackages).toHaveBeenCalledWith(expect.objectContaining({
        q: '',
        provider: 'claude-code',
        category: 'all',
        features: [],
        page: 1,
      }));
    });
  });

  it('imports a duplicate candidate as a new package id', async () => {
    const user = userEvent.setup();
    renderCenter();

    const dialog = await scanGitImport();
    expect(await dialog.findByText('Existing Package')).toBeInTheDocument();
    const checkboxes = dialog.getAllByRole('checkbox');
    fireEvent.click(checkboxes[checkboxes.length - 1]);
    const duplicateActionSelects = dialog.getAllByRole('combobox');
    await user.click(duplicateActionSelects[duplicateActionSelects.length - 1]);
    await user.click(screen.getByRole('option', { name: 'marketplace.import.duplicateActions.importAsNew' }));
    fireEvent.change(dialog.getByLabelText('marketplace.import.fields.newPackageId'), {
      target: { value: 'existing-package-team' },
    });
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockImportCandidates).toHaveBeenCalledWith(expect.arrayContaining([
        expect.objectContaining({
          packageId: 'existing-package',
          duplicate: true,
          duplicateAction: 'import-as-new',
          newPackageId: 'existing-package-team',
        }),
      ]));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('shows an import error when importing selected candidates fails', async () => {
    mockImportCandidates.mockRejectedValue(new Error('marketplace.import.validation.cloneFailed'));
    renderCenter();

    const dialog = await scanGitImport();
    expect(await dialog.findByText('Review Assistant')).toBeInTheDocument();
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.import' }));

    expect(await dialog.findByText('marketplace.import.validation.cloneFailed')).toBeInTheDocument();
  });

  it('shows failed candidate details from an import result', async () => {
    mockImportCandidates.mockResolvedValue({
      imported: [],
      skipped: [],
      failed: [{
        id: 'claude-code:review-assistant',
        provider: 'claude-code',
        packageId: 'review-assistant',
        displayName: 'Review Assistant',
        sourcePath: 'plugins/review-assistant',
        duplicate: false,
        duplicateAction: 'skip',
        variantStatus: 'new-family',
        variants: [],
        validationSeverity: 'none',
        validationResults: [],
        errorCode: 'marketplace.validation.required_manifest_missing',
      }],
      warnings: [],
    });
    renderCenter();

    const dialog = await scanGitImport();
    expect(await dialog.findByText('Review Assistant')).toBeInTheDocument();
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    fireEvent.click(dialog.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'marketplace.import.result.summary',
        description: 'marketplace.import.result.failedDetailsDescription',
        variant: 'destructive',
      }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('shows draft badge and can filter drafts', async () => {
    const user = userEvent.setup();
    mockListPackages.mockResolvedValueOnce({
      ...mockListResult,
      items: [
        {
          ...mockPackage,
          packageId: 'draft-package',
          displayName: 'Draft Package',
          lifecycleStatus: 'draft',
        },
        {
          ...mockPackage,
          packageId: 'ready-package',
          displayName: 'Ready Package',
          lifecycleStatus: 'ready',
          revision: 'rev-ready',
        },
      ],
      total: 2,
    });

    renderCenter();

    expect(await screen.findByText('Draft Package')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.lifecycle.draft' }));

    expect(screen.getByText('Draft Package')).toBeInTheDocument();
    expect(screen.queryByText('Ready Package')).not.toBeInTheDocument();
  });
});
