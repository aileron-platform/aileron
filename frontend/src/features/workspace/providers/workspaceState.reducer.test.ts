import { describe, expect, it } from 'vitest';

import { workspaceReducer } from './workspaceState.reducer';
import { initialState } from './workspaceState.constants';

describe('workspaceReducer canvas state', () => {
  it('updates markdown and raw canvas content atomically for session results', () => {
    const nextState = workspaceReducer(initialState, {
      type: 'SET_CANVAS_SESSION_RESULT',
      payload: {
        markdownContent: '# Final answer',
        rawContent: {
          usage: {
            input_tokens: 10,
            output_tokens: 5,
            total_tokens: 15,
          },
        },
      },
    });

    expect(nextState.canvas).toEqual({
      subView: 'session-result',
      markdownContent: '# Final answer',
      rawContent: {
        usage: {
          input_tokens: 10,
          output_tokens: 5,
          total_tokens: 15,
        },
      },
    });
  });
});
