import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarketplacePackageHeader } from './MarketplacePackageHeader';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplacePackageHeader', () => {
  it('renders create status and dispatches actions', () => {
    const onDiscard = vi.fn();
    const onSave = vi.fn();
    const onBack = vi.fn();

    render(
      <MarketplacePackageHeader
        mode="create"
        isDirty
        saveStatus="success"
        onDiscard={onDiscard}
        onSave={onSave}
        onBack={onBack}
      />,
    );

    expect(screen.getByText('marketplace.editor.createTitle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.dirty')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.saveStatus.success')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /marketplace.editor.actions.discard/ }));
    fireEvent.click(screen.getByRole('button', { name: /marketplace.editor.actions.save/ }));
    fireEvent.click(screen.getByRole('button', { name: /marketplace.common.actions.back/ }));

    expect(onDiscard).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('hides discard when the draft is clean and renders conflict status', () => {
    render(
      <MarketplacePackageHeader
        mode="edit"
        isDirty={false}
        saveStatus="conflict"
        onDiscard={vi.fn()}
        onSave={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText('marketplace.editor.editTitle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.saveStatus.revisionConflict')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /marketplace.editor.actions.discard/ })).not.toBeInTheDocument();
  });
});
