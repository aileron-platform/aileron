import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceImportDialog } from './MarketplaceImportDialog';
import type { MarketplaceImportCandidate, MarketplaceImportResult } from '@/features/marketplace/model/marketplaceTypes';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const mockScanImportSource = vi.fn();
const mockImportCandidates = vi.fn();
const mockToast = vi.fn();

vi.mock('../../../api/marketplaceApi', () => ({
  importCandidates: (...args: unknown[]) => mockImportCandidates(...args),
  scanImportSource: (...args: unknown[]) => mockScanImportSource(...args),
  uploadImportSource: vi.fn(),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToast }),
}));

const candidate: MarketplaceImportCandidate = {
  id: 'claude-code:review-assistant',
  targetClient: 'claude-code',
  packageFormat: 'claude-native',
  packageId: 'review-assistant',
  version: '1.0.0',
  displayName: 'Review Assistant',
  sourcePath: 'plugins/review-assistant',
  duplicate: false,
  variantStatus: 'new-family',
  variants: [],
  validationSeverity: 'none',
  validationResults: [],
};

const securityCandidate: MarketplaceImportCandidate = {
  ...candidate,
  id: 'codex:security-audit',
  targetClient: 'codex',
  packageFormat: 'codex-native',
  packageId: 'security-audit',
  displayName: 'Security Audit',
  sourcePath: 'plugins/security-audit',
};

const importResult: MarketplaceImportResult = {
  imported: [],
  failed: [],
  warnings: [],
};

describe('MarketplaceImportDialog', () => {
  beforeEach(() => {
    mockScanImportSource.mockReset();
    mockImportCandidates.mockReset();
    mockToast.mockReset();
    mockScanImportSource.mockResolvedValue([candidate]);
    mockImportCandidates.mockResolvedValue(importResult);
  });

  it('scans a Git source and imports selected candidates', async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();
    const onOpenChange = vi.fn();

    render(
      <MarketplaceImportDialog
        open
        onOpenChange={onOpenChange}
        onImported={onImported}
      />,
    );

    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'git@github.com:example/marketplace.git');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    expect(await screen.findByText('Review Assistant')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectAll' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockScanImportSource).toHaveBeenCalledWith({
        targetClient: 'all',
        sourceKind: 'git',
        source: 'git@github.com:example/marketplace.git',
      });
      expect(mockImportCandidates).toHaveBeenCalledWith(
        {
          targetClient: 'all',
          sourceKind: 'git',
          source: 'git@github.com:example/marketplace.git',
        },
        [
        expect.objectContaining({
          import: {
            version: '1.0.0',
            overwrite: false,
          },
        }),
        ],
      );
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'marketplace.import.result.summary',
        variant: 'success',
      }));
      expect(onImported).toHaveBeenCalledWith(importResult);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it('filters scanned candidates by keyword and selects only visible results', async () => {
    const user = userEvent.setup();
    mockScanImportSource.mockResolvedValue([candidate, securityCandidate]);

    render(
      <MarketplaceImportDialog
        open
        onOpenChange={vi.fn()}
        onImported={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'https://github.com/example/plugins');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));

    await user.type(
      await screen.findByLabelText('marketplace.import.candidates.searchLabel'),
      'security codex',
    );

    expect(screen.queryByText('Review Assistant')).not.toBeInTheDocument();
    expect(screen.getByText('Security Audit')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.selectFiltered' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.import' }));

    await waitFor(() => {
      expect(mockImportCandidates).toHaveBeenCalledWith(
        expect.objectContaining({ sourceKind: 'git' }),
        [expect.objectContaining({ id: 'codex:security-audit' })],
      );
    });
  });

  it('shows a localized empty state when no scanned candidates match the keyword', async () => {
    const user = userEvent.setup();

    render(
      <MarketplaceImportDialog
        open
        onOpenChange={vi.fn()}
        onImported={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText('marketplace.import.fields.source'), 'https://github.com/example/plugins');
    await user.click(screen.getByRole('button', { name: 'marketplace.import.actions.scan' }));
    await user.type(
      await screen.findByLabelText('marketplace.import.candidates.searchLabel'),
      'not-found',
    );

    expect(screen.getByText('marketplace.import.candidates.noMatches')).toBeInTheDocument();
  });
});
