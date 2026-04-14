import { describe, expect, it } from 'vitest';

import { workspaceReducer } from './workspaceState.reducer';
import { initialState } from './workspaceState.constants';

describe('workspaceReducer preview state', () => {
  it('updates markdown and raw preview content atomically for session results', () => {
    const nextState = workspaceReducer(initialState, {
      type: 'SET_PREVIEW_SESSION_RESULT',
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

    expect(nextState.preview).toEqual({
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
