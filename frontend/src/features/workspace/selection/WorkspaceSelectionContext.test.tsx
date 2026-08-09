import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  WorkspaceSelectionProvider,
  useWorkspaceSelection,
} from './WorkspaceSelectionContext';

const SelectionProbe = () => {
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();

  return (
    <div>
      <div data-testid="selected-workspace">{selectedWorkspaceId ?? 'null'}</div>
      <button type="button" onClick={() => setSelectedWorkspaceId('ws-next')}>select</button>
      <button type="button" onClick={() => setSelectedWorkspaceId(null)}>clear</button>
    </div>
  );
};

describe('WorkspaceSelectionProvider', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('loads, persists, and clears the selected workspace identity', () => {
    localStorage.setItem('selectedWorkspaceId', 'ws-initial');

    render(
      <WorkspaceSelectionProvider>
        <SelectionProbe />
      </WorkspaceSelectionProvider>,
    );

    expect(screen.getByTestId('selected-workspace')).toHaveTextContent('ws-initial');

    fireEvent.click(screen.getByRole('button', { name: 'select' }));
    expect(screen.getByTestId('selected-workspace')).toHaveTextContent('ws-next');
    expect(localStorage.getItem('selectedWorkspaceId')).toBe('ws-next');

    fireEvent.click(screen.getByRole('button', { name: 'clear' }));
    expect(screen.getByTestId('selected-workspace')).toHaveTextContent('null');
    expect(localStorage.getItem('selectedWorkspaceId')).toBeNull();
  });
});
