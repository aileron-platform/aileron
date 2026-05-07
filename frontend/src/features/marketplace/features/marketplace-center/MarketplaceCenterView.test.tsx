import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceCenterView } from './MarketplaceCenterView';
import type { MarketplaceListResult, MarketplacePackageSummary } from '@/shared/types/marketplace';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
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
  registryPath: 'codex/plugins/figma-context',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
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

const mockInstallPackage = vi.fn();
const mockDeletePackage = vi.fn();
const mockExportPackage = vi.fn();
const mockGetRegistrySettings = vi.fn();
const mockGetInstallPreflight = vi.fn();
const mockInitializeRegistry = vi.fn();
const mockListImportBranches = vi.fn();
const mockListPackages = vi.fn();
const mockScanImportSource = vi.fn();
const mockImportCandidates = vi.fn();

vi.mock('../../api/marketplaceApi', () => ({
  getRegistrySettings: (...args: unknown[]) => mockGetRegistrySettings(...args),
  getInstallPreflight: (...args: unknown[]) => mockGetInstallPreflight(...args),
  initializeRegistry: (...args: unknown[]) => mockInitializeRegistry(...args),
  listImportBranches: (...args: unknown[]) => mockListImportBranches(...args),
  listPackages: (...args: unknown[]) => mockListPackages(...args),
  scanImportSource: (...args: unknown[]) => mockScanImportSource(...args),
  importCandidates: (...args: unknown[]) => mockImportCandidates(...args),
  installPackage: (...args: unknown[]) => mockInstallPackage(...args),
  exportPackage: (...args: unknown[]) => mockExportPackage(...args),
  deletePackage: (...args: unknown[]) => mockDeletePackage(...args),
}));

vi.mock('@/features/workspace/services/workspaceRuntimeApi', () => ({
  fetchWorkspaceList: vi.fn(async () => ({
    items: [
      { id: 'ws-1', name: 'Workspace One' },
      { id: 'ws-2', name: 'Workspace Two' },
    ],
  })),
}));

const renderCenter = () => render(
  <MemoryRouter>
    <MarketplaceCenterView />
  </MemoryRouter>,
);

const chooseImportBranch = async (user: ReturnType<typeof userEvent.setup>, branch = 'main') => {
  await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.loadBranches' }));
  await waitFor(() => expect(mockListImportBranches).toHaveBeenCalled());
  const branchSelect = screen.getAllByRole('combobox').at(-1);
  expect(branchSelect).toBeTruthy();
  await user.click(branchSelect!);
  await user.click(await screen.findByRole('option', { name: branch }));
};

describe('MarketplaceCenterView', () => {
  beforeEach(() => {
    if (!HTMLElement.prototype.hasPointerCapture) {
      HTMLElement.prototype.hasPointerCapture = () => false;
    }
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = vi.fn();
    }
    window.localStorage.clear();
    mockGetRegistrySettings.mockReset();
    mockGetInstallPreflight.mockReset();
    mockInitializeRegistry.mockReset();
    mockListImportBranches.mockReset();
    mockListPackages.mockReset();
    mockInstallPackage.mockReset();
    mockDeletePackage.mockReset();
    mockExportPackage.mockReset();
    mockScanImportSource.mockReset();
    mockImportCandidates.mockReset();
    mockGetRegistrySettings.mockResolvedValue({
      displayName: 'Local Marketplace Registry',
      rootPath: '~/.ai-developer-hub/marketplace',
      status: 'ready',
      maintainerName: 'Current user',
      maintainerEmail: 'current.user@example.local',
    });
    mockGetInstallPreflight.mockResolvedValue({
      provider: 'codex',
      available: true,
      version: '1.2.3',
      capabilities: {
        supportsUserScope: true,
        supportsMarketplaceAdd: true,
        supportsExtensionInstall: false,
      },
    });
    mockInitializeRegistry.mockResolvedValue({});
    mockListImportBranches.mockResolvedValue({ branches: ['main', 'develop'] });
    mockListPackages.mockResolvedValue(mockListResult);
    mockInstallPackage.mockResolvedValue({
      status: 'success',
      provider: 'codex',
      packageId: 'figma-context',
      workspaceId: 'ws-1',
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
        validationSeverity: 'none',
        validationResults: [],
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

    expect(await screen.findByText('marketplace.center.list.empty.title')).toBeInTheDocument();

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
    const installButtons = screen.getAllByRole('button', { name: 'marketplace.install.actions.install' });
    await user.click(installButtons[installButtons.length - 1]);

    await waitFor(() => {
      expect(mockInstallPackage).toHaveBeenCalledWith(expect.objectContaining({
        workspaceId: 'ws-1',
      }));
    });
  });

  it('shows install failures from the center action dialog', async () => {
    const user = userEvent.setup();
    mockInstallPackage.mockResolvedValue({
      status: 'cliUnavailable',
      provider: 'codex',
      packageId: 'figma-context',
      workspaceId: 'ws-1',
      errorCode: 'marketplace.install.cliUnavailable',
      stderr: 'codex missing',
    });
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.install' }));
    const installButtons = screen.getAllByRole('button', { name: 'marketplace.install.actions.install' });
    await user.click(installButtons[installButtons.length - 1]);

    expect(await screen.findByText('marketplace.install.result.cliUnavailable')).toBeInTheDocument();
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

  it('allows HTTPS repository URLs to load branches', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.clear(screen.getByLabelText('marketplace.import.fields.source'));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'https://github.com/example/marketplace.git');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.loadBranches' }));

    await waitFor(() => {
      expect(mockListImportBranches).toHaveBeenCalledWith(expect.objectContaining({
        source: 'https://github.com/example/marketplace.git',
      }));
    });
  });

  it('shows a backend branch lookup error when loading repository branches fails', async () => {
    const user = userEvent.setup();
    mockListImportBranches.mockRejectedValueOnce(new Error('marketplace.import.validation.branchListFailed'));
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.clear(screen.getByLabelText('marketplace.import.fields.source'));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@untrusted.example:team/marketplace.git');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.loadBranches' }));

    expect(await screen.findByText('marketplace.import.validation.branchListFailed')).toBeInTheDocument();
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

    expect(await screen.findByText('marketplace.delete.result.failed')).toBeInTheDocument();
  });

  it('scans import candidates, keeps duplicates unselected, and imports selected candidates', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await chooseImportBranch(user);
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    expect(screen.getByText('Existing Package')).toBeInTheDocument();
    expect(screen.getByText('marketplace.import.candidates.duplicate')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    expect(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.clearSelection' }));
    expect(screen.getByRole('button', { name: 'marketplace.import.actions.import' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockScanImportSource).toHaveBeenCalledWith(expect.objectContaining({
        provider: 'claude-code',
        sourceKind: 'git',
        ref: 'main',
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
    expect(screen.getByText('marketplace.import.result.summary')).toBeInTheDocument();
  });

  it('imports a duplicate candidate as a new package id', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await chooseImportBranch(user);
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Existing Package')).toBeInTheDocument();
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[checkboxes.length - 1]);
    const duplicateActionSelects = screen.getAllByRole('combobox');
    await user.click(duplicateActionSelects[duplicateActionSelects.length - 1]);
    await user.click(screen.getByRole('option', { name: 'marketplace.import.duplicateActions.importAsNew' }));
    await user.clear(screen.getByLabelText('marketplace.import.fields.newPackageId'));
    await user.type(screen.getByLabelText('marketplace.import.fields.newPackageId'), 'existing-package-team');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockImportCandidates).toHaveBeenCalledWith(expect.arrayContaining([
        expect.objectContaining({
          packageId: 'existing-package',
          duplicate: true,
          duplicateAction: 'import-as-new',
          newPackageId: 'existing-package-team',
        }),
      ]));
    });
  });

  it('shows an import error when importing selected candidates fails', async () => {
    const user = userEvent.setup();
    mockImportCandidates.mockRejectedValue(new Error('marketplace.import.validation.cloneFailed'));
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await chooseImportBranch(user);
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    expect(await screen.findByText('marketplace.import.validation.cloneFailed')).toBeInTheDocument();
  });

  it('shows failed candidate details from an import result', async () => {
    const user = userEvent.setup();
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
        validationSeverity: 'none',
        validationResults: [],
        errorCode: 'marketplace.validation.required_manifest_missing',
      }],
      warnings: [],
    });
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await chooseImportBranch(user);
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    expect(await screen.findByText('marketplace.import.result.failedDetails')).toBeInTheDocument();
    expect(screen.getByText(/marketplace.validation.required_manifest_missing/)).toBeInTheDocument();
  });
});
