import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EntryFrame } from './EntryFrame';
import type { PlatformIdentityEntryProjection } from './workspaceEntryTypes';
import {
  ENTRY_PROGRESS_DELAY_MS,
  ENTRY_PROGRESS_MIN_VISIBLE_MS,
} from './entryProgressTiming';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const projection: PlatformIdentityEntryProjection = {
  stages: [{ id: 'identity', status: 'active' }],
  activeStage: 'identity',
  titleKey: 'common.entry.title',
  descriptionKey: 'common.entry.descriptions.identity',
  reasonCode: null,
  actions: [],
};

describe('EntryFrame', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps navigation geometry and delays the panel until the entry is slow', () => {
    vi.useFakeTimers();
    const { rerender } = render(
      <EntryFrame
        isPending
        transitionKey="identity-1"
        projection={projection}
        navigationSlot={<header data-testid="global-navigation" />}
        onAction={vi.fn()}
      >
        <div data-testid="workspace-content" />
      </EntryFrame>,
    );

    expect(screen.getByTestId('global-navigation')).toBeInTheDocument();
    expect(screen.getByRole('main')).toHaveClass('absolute', 'inset-0');
    expect(screen.queryByRole('heading', { name: 'common.entry.title' })).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(ENTRY_PROGRESS_DELAY_MS);
    });
    expect(screen.getByRole('heading', { name: 'common.entry.title' })).toBeInTheDocument();

    rerender(
      <EntryFrame
        isPending={false}
        transitionKey="identity-1"
        projection={projection}
        navigationSlot={<header data-testid="global-navigation" />}
        onAction={vi.fn()}
      >
        <div data-testid="workspace-content" />
      </EntryFrame>,
    );

    expect(screen.queryByTestId('workspace-content')).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(ENTRY_PROGRESS_MIN_VISIBLE_MS);
    });
    expect(screen.getByTestId('workspace-content')).toBeInTheDocument();
  });

  it('skips the panel for the ready fast path', () => {
    render(
      <EntryFrame
        isPending={false}
        transitionKey="ready-1"
        projection={projection}
        navigationSlot={<header data-testid="global-navigation" />}
        onAction={vi.fn()}
      >
        <div data-testid="workspace-content" />
      </EntryFrame>,
    );

    expect(screen.getByTestId('workspace-content')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'common.entry.title' })).not.toBeInTheDocument();
  });
});
