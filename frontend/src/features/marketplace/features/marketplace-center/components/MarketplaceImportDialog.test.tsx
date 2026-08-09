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
};

const importResult: MarketplaceImportResult = {
  imported: [],
  skipped: [],
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
        provider: 'all',
        sourceKind: 'git',
        source: 'git@github.com:example/marketplace.git',
      });
      expect(mockImportCandidates).toHaveBeenCalledWith([candidate]);
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
        title: 'marketplace.import.result.summary',
        variant: 'success',
      }));
      expect(onImported).toHaveBeenCalledWith(importResult);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
