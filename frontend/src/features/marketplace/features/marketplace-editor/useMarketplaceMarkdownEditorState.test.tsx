import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useMarketplaceMarkdownEditorState } from './useMarketplaceMarkdownEditorState';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

vi.mock('../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(),
}));

const items: MarketplaceEditorResourceItem[] = [
  {
    id: 'alpha',
    title: 'Alpha',
    description: 'Alpha agent',
    path: 'agents/alpha.md',
    content: '# Alpha',
    badge: 'md',
  },
  {
    id: 'beta',
    title: 'Beta',
    description: 'Beta agent',
    path: 'agents/beta.md',
    content: '# Beta',
    badge: 'md',
  },
];

interface HarnessProps {
  commitVersion: number;
  discardVersion: number;
}

const Harness: React.FC<HarnessProps> = ({ commitVersion, discardVersion }) => {
  const state = useMarketplaceMarkdownEditorState({
    format: 'markdown',
    items,
    commitVersion,
    discardVersion,
    t: (key: string) => key,
    onDirty: vi.fn(),
  });

  return (
    <div>
      <button type="button" onClick={() => state.handleSelectItem('beta')}>
        select-beta
      </button>
      <button type="button" onClick={() => state.handleContentChange('# Updated beta')}>
        edit
      </button>
      <button type="button" onClick={() => state.handleContentChange('# Temporary beta')}>
        temp
      </button>
      <div data-testid="selected-content">{state.selectedContent}</div>
      <div data-testid="selected-id">{state.selectedItem?.id ?? ''}</div>
    </div>
  );
};

describe('useMarketplaceMarkdownEditorState', () => {
  it('retains committed content and restores it on discard', () => {
    const { rerender } = render(<Harness commitVersion={0} discardVersion={0} />);

    fireEvent.click(screen.getByText('select-beta'));
    fireEvent.click(screen.getByText('edit'));
    expect(screen.getByTestId('selected-content')).toHaveTextContent('# Updated beta');

    rerender(<Harness commitVersion={1} discardVersion={0} />);
    fireEvent.click(screen.getByText('temp'));
    expect(screen.getByTestId('selected-content')).toHaveTextContent('# Temporary beta');

    rerender(<Harness commitVersion={1} discardVersion={1} />);
    expect(screen.getByTestId('selected-content')).toHaveTextContent('# Updated beta');
    expect(screen.getByTestId('selected-id')).toHaveTextContent('beta');
  });
});
