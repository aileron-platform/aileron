import React from 'react';

export type SplitPaneDirection = 'horizontal' | 'vertical';

export const SPLIT_PANE_MAX_COUNT = 4;
export const SPLIT_PANE_MIN_SIZE_PERCENT = 15;

export interface SplitPaneGroupProps<TPane> {
  panes: TPane[];
  direction: SplitPaneDirection;
  getPaneKey: (pane: TPane) => string;
  renderPane: (pane: TPane) => React.ReactNode;
  sizes?: number[];
  onSizesChange?: (sizes: number[]) => void;
}

const evenSizes = (count: number): number[] => {
  const each = 100 / count;
  return Array.from({ length: count }, () => each);
};

export function SplitPaneGroup<TPane>({
  panes,
  direction,
  getPaneKey,
  renderPane,
  sizes: controlledSizes,
  onSizesChange,
}: SplitPaneGroupProps<TPane>): React.ReactElement {
  const clampedPanes = panes.slice(0, SPLIT_PANE_MAX_COUNT);
  const [uncontrolledSizes, setUncontrolledSizes] = React.useState<number[]>(
    () => controlledSizes ?? evenSizes(clampedPanes.length),
  );
  const rawSizes = controlledSizes ?? uncontrolledSizes;
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const dragStateRef = React.useRef<{ dividerIndex: number; startPos: number; startSizes: number[] } | null>(null);
  const [isDragging, setIsDragging] = React.useState<number | null>(null);

  const setSizes = React.useCallback((next: number[]) => {
    if (onSizesChange) {
      onSizesChange(next);
    } else {
      setUncontrolledSizes(next);
    }
  }, [onSizesChange]);

  // Reconcile stale size arrays whenever the active pane count changes.
  const sizes = rawSizes.length === clampedPanes.length ? rawSizes : evenSizes(clampedPanes.length);

  React.useEffect(() => {
    if (rawSizes.length !== clampedPanes.length) {
      setSizes(evenSizes(clampedPanes.length));
    }
    // Only re-run when the pane count or the sizes array's own length changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clampedPanes.length, rawSizes.length]);

  const startResize = React.useCallback((event: React.MouseEvent, dividerIndex: number) => {
    event.preventDefault();
    const startPos = direction === 'horizontal' ? event.clientX : event.clientY;
    dragStateRef.current = { dividerIndex, startPos, startSizes: sizes };
    setIsDragging(dividerIndex);
  }, [direction, sizes]);

  React.useEffect(() => {
    if (isDragging === null) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = dragStateRef.current;
      const container = containerRef.current;

      if (!dragState || !container) {
        return;
      }

      const rect = container.getBoundingClientRect();
      const containerSize = direction === 'horizontal' ? rect.width : rect.height;
      const currentPos = direction === 'horizontal' ? event.clientX : event.clientY;
      const deltaPercent = ((currentPos - dragState.startPos) / containerSize) * 100;

      const leftIndex = dragState.dividerIndex;
      const rightIndex = dragState.dividerIndex + 1;
      const nextSizes = [...dragState.startSizes];
      const pairTotal = nextSizes[leftIndex] + nextSizes[rightIndex];
      const rawLeft = nextSizes[leftIndex] + deltaPercent;
      const clampedLeft = Math.max(
        SPLIT_PANE_MIN_SIZE_PERCENT,
        Math.min(pairTotal - SPLIT_PANE_MIN_SIZE_PERCENT, rawLeft),
      );
      nextSizes[leftIndex] = clampedLeft;
      nextSizes[rightIndex] = pairTotal - clampedLeft;

      setSizes(nextSizes);
    };

    const handleMouseUp = () => {
      setIsDragging(null);
      dragStateRef.current = null;
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, direction, setSizes]);

  const dimension = direction === 'horizontal' ? 'width' : 'height';

  return (
    <div
      ref={containerRef}
      className={direction === 'horizontal' ? 'flex h-full min-h-0 w-full' : 'flex h-full min-h-0 w-full flex-col'}
    >
      {clampedPanes.map((pane, index) => (
        <React.Fragment key={getPaneKey(pane)}>
          <div
            data-testid={`split-pane-${getPaneKey(pane)}`}
            className="min-h-0 min-w-0 overflow-hidden"
            style={{ [dimension]: `${sizes[index]}%` }}
          >
            {renderPane(pane)}
          </div>
          {index < clampedPanes.length - 1 && (
            <div
              role="separator"
              aria-orientation={direction === 'horizontal' ? 'vertical' : 'horizontal'}
              className={
                direction === 'horizontal'
                  ? 'w-1 shrink-0 cursor-col-resize bg-border transition-colors hover:bg-primary/30'
                  : 'h-1 shrink-0 cursor-row-resize bg-border transition-colors hover:bg-primary/30'
              }
              onMouseDown={(event) => startResize(event, index)}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
