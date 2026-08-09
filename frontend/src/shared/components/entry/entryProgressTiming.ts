export const ENTRY_PROGRESS_DELAY_MS = 500;
export const ENTRY_PROGRESS_MIN_VISIBLE_MS = 500;

export type EntryProgressTimingState =
  | { phase: 'hidden'; token: number; visibleAt: null }
  | { phase: 'waiting'; token: number; visibleAt: null }
  | { phase: 'visible'; token: number; visibleAt: number };

export type EntryProgressTimingEvent =
  | { type: 'delay-elapsed'; token: number; now: number }
  | { type: 'resolved'; token: number; now: number }
  | { type: 'minimum-visible-elapsed'; token: number }
  | { type: 'identity-changed' };

export const createEntryProgressTiming = (
  isPending: boolean,
  token = 0,
): EntryProgressTimingState => isPending
  ? { phase: 'waiting', token: token + 1, visibleAt: null }
  : { phase: 'hidden', token, visibleAt: null };

export const transitionEntryProgressTiming = (
  state: EntryProgressTimingState,
  event: EntryProgressTimingEvent,
): EntryProgressTimingState => {
  if (event.type === 'identity-changed') {
    return {
      phase: 'waiting',
      token: state.token + 1,
      visibleAt: null,
    };
  }

  if (event.token !== state.token) {
    return state;
  }

  if (event.type === 'delay-elapsed') {
    if (state.phase !== 'waiting') {
      return state;
    }
    return {
      phase: 'visible',
      token: state.token,
      visibleAt: event.now,
    };
  }

  if (event.type === 'resolved') {
    if (state.phase === 'hidden') {
      return state;
    }
    if (state.phase === 'waiting') {
      return {
        phase: 'hidden',
        token: state.token + 1,
        visibleAt: null,
      };
    }
    if (event.now - state.visibleAt >= ENTRY_PROGRESS_MIN_VISIBLE_MS) {
      return {
        phase: 'hidden',
        token: state.token + 1,
        visibleAt: null,
      };
    }
    return state;
  }

  if (state.phase !== 'visible') {
    return state;
  }

  return {
    phase: 'hidden',
    token: state.token + 1,
    visibleAt: null,
  };
};
