import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
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

const mockInstallPackage = vi.fn();
const mockDeletePackage = vi.fn();
const mockExportPackage = vi.fn();
const mockGetRegistrySettings = vi.fn();
const mockGetInstallPreflight = vi.fn();
const mockInitializeRegistry = vi.fn();
const mockListPackages = vi.fn();
const mockScanImportSource = vi.fn();
const mockImportCandidates = vi.fn();
const mockToast = vi.fn();

vi.mock('../../api/marketplaceApi', () => ({
  getRegistrySettings: (...args: unknown[]) => mockGetRegistrySettings(...args),
  getInstallPreflight: (...args: unknown[]) => mockGetInstallPreflight(...args),
  initializeRegistry: (...args: unknown[]) => mockInitializeRegistry(...args),
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

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

const renderCenter = () => render(
  <MemoryRouter>
    <MarketplaceCenterView />
  </MemoryRouter>,
);

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
    mockListPackages.mockReset();
    mockInstallPackage.mockReset();
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

  it('shows action API errors in the center action dialog', async () => {
    const user = userEvent.setup();
    mockExportPackage.mockRejectedValue(new Error('你沒有權限執行此 Marketplace 操作'));
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.export' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.export.actions.export' }));

    expect(await screen.findByText('你沒有權限執行此 Marketplace 操作')).toBeInTheDocument();
  });

  it('scans HTTPS repository URLs using the default branch', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.clear(screen.getByLabelText('marketplace.import.fields.source'));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'https://github.com/example/marketplace.git');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    await waitFor(() => {
      expect(mockScanImportSource).toHaveBeenCalledWith(expect.objectContaining({
        source: 'https://github.com/example/marketplace.git',
      }));
    });
    expect(mockScanImportSource).toHaveBeenCalledWith(expect.not.objectContaining({
      ref: expect.any(String),
    }));
  });

  it('does not render branch selection in the import flow', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getAllByRole('combobox')).toHaveLength(2);
    expect(within(dialog).getByRole('button', { name: 'marketplace.import.actions.scan' })).toBeInTheDocument();
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

  it('scans import candidates without selecting them by default and imports selected candidates', async () => {
    const user = userEvent.setup();
    renderCenter();

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    expect(screen.getByText('Existing Package')).toBeInTheDocument();
    expect(screen.getByText('marketplace.import.variantStatuses.new-family')).toBeInTheDocument();
    expect(screen.getByText('marketplace.import.variantStatuses.duplicate-variant')).toBeInTheDocument();
    expect(screen.getByText('marketplace.import.candidates.duplicate')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.validation.metadata_conflict')).not.toBeInTheDocument();
    expect(screen.getByText('marketplace.import.validation.duplicate')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.import.actions.import' })).toBeDisabled();
    const candidateCheckboxes = screen.getAllByRole('checkbox').slice(-2);
    expect(candidateCheckboxes).toHaveLength(2);
    expect(candidateCheckboxes.every(checkbox => !(checkbox as HTMLInputElement).checked)).toBe(true);

    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    expect(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.clearSelection' }));
    expect(screen.getByRole('button', { name: 'marketplace.import.actions.import' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

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
    const user = userEvent.setup();
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
    await user.click(screen.getByRole('button', { name: 'marketplace.providers.codex' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.features.mcp' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));
    await user.click(await screen.findByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
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

    await screen.findByText('Figma Context');
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
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
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
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
        variantStatus: 'new-family',
        variants: [],
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
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'marketplace.import.result.summary',
        description: 'marketplace.import.result.failedDetailsDescription',
        variant: 'destructive',
      }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
