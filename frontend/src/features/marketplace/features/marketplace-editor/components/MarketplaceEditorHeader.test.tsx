import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceEditorHeader } from './MarketplaceEditorHeader';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceEditorHeader', () => {
  it('shows only back action in editor header', () => {
    const onBack = vi.fn();

    render(
      <MemoryRouter>
        <MarketplaceEditorHeader
          breadcrumbs={[
            { label: 'marketplace.breadcrumbs.root', to: '/marketplace' },
            { label: 'marketplace.center.header.title', to: '/marketplace/packages' },
          ]}
          onBack={onBack}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('marketplace.breadcrumbs.root')).toBeInTheDocument();
    expect(screen.getByText('marketplace.center.header.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.editTitle')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /marketplace\.common\.actions\.back/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /discard/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /marketplace\.common\.actions\.back/i }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
