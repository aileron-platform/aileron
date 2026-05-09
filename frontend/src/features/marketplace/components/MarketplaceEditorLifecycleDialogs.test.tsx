import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceEditorLeaveDialog } from './MarketplaceEditorLifecycleDialogs';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceEditorLifecycleDialogs', () => {
  it('renders the unsaved changes dialog actions', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onSave = vi.fn();
    const onDiscard = vi.fn();

    render(
      <MarketplaceEditorLeaveDialog
        open
        onOpenChange={onOpenChange}
        onSave={onSave}
        onDiscard={onDiscard}
      />,
    );

    expect(screen.getByText('marketplace.editor.unsaved.title')).toBeInTheDocument();

    await user.click(screen.getByText('marketplace.editor.actions.discard'));
    expect(onDiscard).toHaveBeenCalled();

    await user.click(screen.getByText('marketplace.editor.actions.save'));
    expect(onSave).toHaveBeenCalled();
  });
});
