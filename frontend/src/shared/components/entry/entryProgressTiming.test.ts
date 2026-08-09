import { describe, expect, it } from 'vitest';
import {
  ENTRY_PROGRESS_DELAY_MS,
  ENTRY_PROGRESS_MIN_VISIBLE_MS,
  createEntryProgressTiming,
  transitionEntryProgressTiming,
} from './entryProgressTiming';

describe('entry progress timing', () => {
  it('delays the progress panel for the fast path', () => {
    const initial = createEntryProgressTiming(true, 100);

    expect(initial).toEqual({
      phase: 'waiting',
      token: 101,
      visibleAt: null,
    });

    expect(transitionEntryProgressTiming(initial, {
      type: 'delay-elapsed',
      token: initial.token,
      now: 100 + ENTRY_PROGRESS_DELAY_MS,
    })).toEqual({
      phase: 'visible',
      token: initial.token,
      visibleAt: 100 + ENTRY_PROGRESS_DELAY_MS,
    });
  });

  it('keeps a visible panel until the minimum duration completes', () => {
    const visible = {
      phase: 'visible' as const,
      token: 1,
      visibleAt: 1_000,
    };

    const resolvedEarly = transitionEntryProgressTiming(visible, {
      type: 'resolved',
      token: visible.token,
      now: 1_000 + ENTRY_PROGRESS_MIN_VISIBLE_MS - 1,
    });
    expect(resolvedEarly).toEqual(visible);

    expect(transitionEntryProgressTiming(resolvedEarly, {
      type: 'minimum-visible-elapsed',
      token: visible.token,
    })).toEqual({
      phase: 'hidden',
      token: visible.token + 1,
      visibleAt: null,
    });
  });

  it('ignores stale timer callbacks from an older entry identity', () => {
    const initial = createEntryProgressTiming(true, 0);
    const switched = transitionEntryProgressTiming(initial, {
      type: 'identity-changed',
    });

    expect(switched.token).toBe(initial.token + 1);
    expect(transitionEntryProgressTiming(switched, {
      type: 'delay-elapsed',
      token: initial.token,
      now: ENTRY_PROGRESS_DELAY_MS,
    })).toEqual(switched);
  });

  it('does not create a progress panel for an already-ready fast path', () => {
    expect(createEntryProgressTiming(false, 0)).toEqual({
      phase: 'hidden',
      token: 0,
      visibleAt: null,
    });
  });
});
