import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarketplaceInfoGridRow } from './MarketplaceInfoGridRow';

describe('MarketplaceInfoGridRow', () => {
  it('renders label and value in the shared detail grid layout', () => {
    render(<MarketplaceInfoGridRow label="marketplace.detail.basicInfo.packageId" value="sample-package" />);

    expect(screen.getByText('marketplace.detail.basicInfo.packageId')).toBeInTheDocument();
    expect(screen.getByText('sample-package')).toBeInTheDocument();
  });

  it('supports monospace values for package identifiers and paths', () => {
    render(<MarketplaceInfoGridRow label="marketplace.export.fields.root" value="codex/plugins/sample" monospace />);

    expect(screen.getByText('codex/plugins/sample')).toHaveClass('font-mono');
  });
});
