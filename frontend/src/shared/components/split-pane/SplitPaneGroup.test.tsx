import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SplitPaneGroup } from './SplitPaneGroup';

interface TestPane {
  id: string;
  label: string;
}

const panes: TestPane[] = [
  { id: 'pane-1', label: 'Pane One' },
  { id: 'pane-2', label: 'Pane Two' },
];

describe('SplitPaneGroup', () => {
  it('renders one pane per entry via renderPane, in horizontal direction by default sizing', () => {
    render(
      <SplitPaneGroup
        panes={panes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div data-testid={`content-${pane.id}`}>{pane.label}</div>}
      />,
    );

    expect(screen.getByTestId('content-pane-1')).toBeInTheDocument();
    expect(screen.getByTestId('content-pane-2')).toBeInTheDocument();
    expect(screen.getByTestId('split-pane-pane-1')).toHaveStyle({ width: '50%' });
    expect(screen.getByTestId('split-pane-pane-2')).toHaveStyle({ width: '50%' });
  });

  it('renders a vertical stack using height instead of width', () => {
    render(
      <SplitPaneGroup
        panes={panes}
        direction="vertical"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
      />,
    );

    expect(screen.getByTestId('split-pane-pane-1')).toHaveStyle({ height: '50%' });
    expect(screen.getByTestId('split-pane-pane-2')).toHaveStyle({ height: '50%' });
  });

  it('renders one resize divider between each pair of adjacent panes, none at the edges', () => {
    render(
      <SplitPaneGroup
        panes={panes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
      />,
    );

    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });

  it('renders 3 dividers for 4 panes (single-level, hard cap)', () => {
    const fourPanes: TestPane[] = [
      { id: 'p1', label: 'One' },
      { id: 'p2', label: 'Two' },
      { id: 'p3', label: 'Three' },
      { id: 'p4', label: 'Four' },
    ];
    render(
      <SplitPaneGroup
        panes={fourPanes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
      />,
    );

    expect(screen.getAllByRole('separator')).toHaveLength(3);
  });

  it('honors explicit sizes and reports resized ratios via onSizesChange when a divider is dragged', () => {
    const onSizesChange = vi.fn();
    render(
      <SplitPaneGroup
        panes={panes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
        sizes={[60, 40]}
        onSizesChange={onSizesChange}
      />,
    );

    expect(screen.getByTestId('split-pane-pane-1')).toHaveStyle({ width: '60%' });

    const divider = screen.getByRole('separator');
    vi.spyOn(divider.parentElement as HTMLElement, 'getBoundingClientRect').mockReturnValue({
      width: 1000, height: 500, top: 0, left: 0, right: 1000, bottom: 500, x: 0, y: 0, toJSON: () => ({}),
    });
    fireEvent.mouseDown(divider, { clientX: 600 });
    fireEvent.mouseMove(document, { clientX: 700 });
    fireEvent.mouseUp(document);

    expect(onSizesChange).toHaveBeenCalledWith([70, 30]);
  });

  it('clamps a dragged divider so neither pane shrinks below the minimum percentage', () => {
    const onSizesChange = vi.fn();
    render(
      <SplitPaneGroup
        panes={panes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
        sizes={[50, 50]}
        onSizesChange={onSizesChange}
      />,
    );

    const divider = screen.getByRole('separator');
    vi.spyOn(divider.parentElement as HTMLElement, 'getBoundingClientRect').mockReturnValue({
      width: 1000, height: 500, top: 0, left: 0, right: 1000, bottom: 500, x: 0, y: 0, toJSON: () => ({}),
    });
    fireEvent.mouseDown(divider, { clientX: 500 });
    fireEvent.mouseMove(document, { clientX: 990 });
    fireEvent.mouseUp(document);

    const [sizes] = onSizesChange.mock.calls[0];
    expect(sizes[0]).toBe(85);
    expect(sizes[1]).toBe(15);
  });

  it('falls back to an even split immediately when a controlled sizes array is the wrong length for the current panes, and reports the correction', async () => {
    const onSizesChange = vi.fn();
    const threePanes: TestPane[] = [
      { id: 'pane-1', label: 'Pane One' },
      { id: 'pane-2', label: 'Pane Two' },
      { id: 'pane-3', label: 'Pane Three' },
    ];

    render(
      <SplitPaneGroup
        panes={threePanes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
        sizes={[50, 50]}
        onSizesChange={onSizesChange}
      />,
    );

    expect(screen.getByTestId('split-pane-pane-1')).toHaveStyle({ width: `${100 / 3}%` });
    expect(screen.getByTestId('split-pane-pane-2')).toHaveStyle({ width: `${100 / 3}%` });
    expect(screen.getByTestId('split-pane-pane-3')).toHaveStyle({ width: `${100 / 3}%` });

    await waitFor(() => {
      expect(onSizesChange).toHaveBeenCalledWith([100 / 3, 100 / 3, 100 / 3]);
    });
  });

  it('recomputes an even split in uncontrolled mode too when the pane count grows', () => {
    const { rerender } = render(
      <SplitPaneGroup
        panes={panes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
      />,
    );

    const threePanes: TestPane[] = [...panes, { id: 'pane-3', label: 'Pane Three' }];
    rerender(
      <SplitPaneGroup
        panes={threePanes}
        direction="horizontal"
        getPaneKey={(pane) => pane.id}
        renderPane={(pane) => <div>{pane.label}</div>}
      />,
    );

    expect(screen.getByTestId('split-pane-pane-3')).toHaveStyle({ width: `${100 / 3}%` });
  });
});
