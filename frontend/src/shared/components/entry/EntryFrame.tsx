import React from 'react';
import { EntryProgressPanel } from './EntryProgressPanel';
import {
  ENTRY_PROGRESS_DELAY_MS,
  ENTRY_PROGRESS_MIN_VISIBLE_MS,
  createEntryProgressTiming,
  transitionEntryProgressTiming,
  type EntryProgressTimingState,
} from './entryProgressTiming';
import type {
  PlatformIdentityEntryProjection,
  WorkspaceEntryActionId,
  WorkspaceEntryProjection,
} from './workspaceEntryTypes';

type EntryProjection = WorkspaceEntryProjection | PlatformIdentityEntryProjection;

interface EntryFrameProps {
  isPending: boolean;
  transitionKey: string;
  projection: EntryProjection;
  navigationSlot?: React.ReactNode;
  onAction: (action: WorkspaceEntryActionId) => void;
  disableMutationActions?: boolean;
  auxiliaryActions?: React.ReactNode;
  keepFrame?: boolean;
  children: React.ReactNode;
}

const useEntryProgressTiming = (
  isPending: boolean,
  transitionKey: string,
): EntryProgressTimingState => {
  const [timing, setTiming] = React.useState<EntryProgressTimingState>(() => (
    createEntryProgressTiming(isPending)
  ));
  const previousTransitionKeyRef = React.useRef(transitionKey);

  React.useEffect(() => {
    if (previousTransitionKeyRef.current === transitionKey) {
      return;
    }
    previousTransitionKeyRef.current = transitionKey;
    setTiming(current => createEntryProgressTiming(isPending, current.token));
  }, [isPending, transitionKey]);

  React.useEffect(() => {
    let timeoutId: number | undefined;

    if (isPending && timing.phase === 'waiting') {
      timeoutId = window.setTimeout(() => {
        setTiming(current => transitionEntryProgressTiming(current, {
          type: 'delay-elapsed',
          token: timing.token,
          now: Date.now(),
        }));
      }, ENTRY_PROGRESS_DELAY_MS);
    }

    if (!isPending) {
      const now = Date.now();
      const next = transitionEntryProgressTiming(timing, {
        type: 'resolved',
        token: timing.token,
        now,
      });
      if (next !== timing) {
        setTiming(next);
      } else if (timing.phase === 'visible' && timing.visibleAt !== null) {
        const remaining = Math.max(
          0,
          ENTRY_PROGRESS_MIN_VISIBLE_MS - (now - timing.visibleAt),
        );
        timeoutId = window.setTimeout(() => {
          setTiming(current => transitionEntryProgressTiming(current, {
            type: 'minimum-visible-elapsed',
            token: timing.token,
          }));
        }, remaining);
      }
    }

    return () => {
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [isPending, timing]);

  return timing;
};

export const EntryFrame: React.FC<EntryFrameProps> = ({
  isPending,
  transitionKey,
  projection,
  navigationSlot,
  onAction,
  disableMutationActions = false,
  auxiliaryActions,
  keepFrame = false,
  children,
}) => {
  const timing = useEntryProgressTiming(isPending, transitionKey);

  if (!isPending && timing.phase === 'hidden' && !keepFrame) {
    return (
      <div className="animate-in fade-in duration-150" data-testid="entry-content">
        {children}
      </div>
    );
  }

  return (
    <div
      className="relative flex min-h-screen w-full flex-col bg-background"
      data-testid="entry-frame"
    >
      <div className="relative z-10 shrink-0">{navigationSlot}</div>
      <main className="absolute inset-0 z-0 flex items-center justify-center overflow-hidden bg-muted/50 bg-[image:radial-gradient(60rem_36rem_at_50%_-8%,hsl(var(--primary)/0.12),transparent_70%)] px-6 py-10">
        {timing.phase === 'visible' ? (
          <EntryProgressPanel
            projection={projection}
            onAction={onAction}
            disableMutationActions={disableMutationActions}
            auxiliaryActions={auxiliaryActions}
          />
        ) : keepFrame && !isPending ? (
          <div className="relative w-full min-h-0">{children}</div>
        ) : null}
      </main>
    </div>
  );
};
