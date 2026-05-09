import React from 'react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';
import { MarketplaceSectionSidebarShell } from './MarketplaceSectionSidebarShell';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceSectionSidebarShell', () => {
  it('preserves header, actions, search, and body rendering through the shared shell', async () => {
    const user = userEvent.setup();
    const onSearchChange = vi.fn();
    const onSearchClear = vi.fn();

    render(
      <MarketplaceSectionSidebarShell
        title="marketplace.detail.viewer.files"
        actions={<button type="button">marketplace.detail.viewer.collapseSidebar</button>}
        searchValue=""
        onSearchChange={onSearchChange}
        onSearchClear={onSearchClear}
        searchPlaceholder="marketplace.editor.fileManager.search.placeholder"
        body={<div>marketplace.editor.fileManager.tree.body</div>}
      />,
    );

    expect(screen.getByText('marketplace.detail.viewer.files')).toBeInTheDocument();
    expect(screen.getByText('marketplace.detail.viewer.collapseSidebar')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.fileManager.tree.body')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('marketplace.editor.fileManager.search.placeholder'), 'abc');

    expect(onSearchChange).toHaveBeenCalled();
  });

  it('does not render search when no change handler is provided', () => {
    render(
      <MarketplaceSectionSidebarShell
        title="marketplace.detail.viewer.files"
        searchPlaceholder="marketplace.editor.fileManager.search.placeholder"
        body={<div>marketplace.editor.fileManager.tree.body</div>}
      />,
    );

    expect(screen.queryByPlaceholderText('marketplace.editor.fileManager.search.placeholder')).not.toBeInTheDocument();
  });
});
