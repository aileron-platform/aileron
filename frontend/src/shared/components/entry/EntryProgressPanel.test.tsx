import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EntryProgressPanel } from './EntryProgressPanel';
import type { WorkspaceEntryProjection } from './workspaceEntryTypes';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const projection: WorkspaceEntryProjection = {
  stages: [
    { id: 'identity', status: 'complete' },
    { id: 'workspace', status: 'complete' },
    { id: 'execution', status: 'uncertain' },
  ],
  activeStage: 'execution',
  titleKey: 'common.entry.title',
  descriptionKey: 'common.entry.descriptions.execution',
  reasonCode: 'WORKSPACE_AVAILABILITY_UNCERTAIN',
  actions: [
    { id: 'refresh', emphasis: 'primary' },
    { id: 'return', emphasis: 'secondary' },
  ],
};

describe('EntryProgressPanel', () => {
  it('renders the fixed stage order, current stage and safe reason code', () => {
    render(<EntryProgressPanel projection={projection} onAction={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'common.entry.title' })).toBeInTheDocument();
    expect(screen.getByRole('list')).toHaveAttribute('aria-label', 'common.entry.stages.label');
    expect(screen.getByRole('listitem', { name: 'common.entry.stages.identity' })).toHaveAttribute(
      'data-status',
      'complete',
    );
    expect(screen.getByRole('listitem', { name: 'common.entry.stages.execution' })).toHaveAttribute(
      'aria-current',
      'step',
    );
    expect(screen.getByRole('listitem', { name: 'common.entry.stages.execution' })
      .querySelector('svg')).toHaveClass('motion-reduce:animate-none');
    expect(screen.getByText('WORKSPACE_AVAILABILITY_UNCERTAIN')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.entry.actions.refresh' })).toBeInTheDocument();
  });

  it('dispatches actions through the adapter and exposes the copy action', async () => {
    const onAction = vi.fn();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<EntryProgressPanel projection={projection} onAction={onAction} />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'common.entry.actions.refresh' }));
      fireEvent.click(screen.getByRole('button', { name: 'common.entry.copyReasonCode' }));
      await Promise.resolve();
    });

    expect(onAction).toHaveBeenCalledWith('refresh');
    expect(writeText).toHaveBeenCalledWith('WORKSPACE_AVAILABILITY_UNCERTAIN');
  });

  it('does not render a reason-code surface when no stable code exists', () => {
    render(
      <EntryProgressPanel
        projection={{ ...projection, reasonCode: null }}
        onAction={vi.fn()}
      />,
    );

    expect(screen.queryByText('common.entry.reasonCode')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.copyReasonCode' })).not.toBeInTheDocument();
  });
});
