import { describe, expect, it, vi } from 'vitest';

import { AgentSessionEventDispatcher } from './agentSessionEvents';

describe('AgentSessionEventDispatcher', () => {
  it('dispatches queue processing failure events', () => {
    const dispatcher = new AgentSessionEventDispatcher();
    const onQueueProcessingFailed = vi.fn();

    dispatcher.subscribe({ onQueueProcessingFailed });

    dispatcher.dispatch({
      type: 'queue:processing_failed',
      session_id: 'session-1',
      timestamp: '2026-04-29T00:00:00.000Z',
      data: {
        message_id: 'message-1',
        queue_position: 1,
        error_message: 'dispatch failed',
        error_type: 'RuntimeError',
        content_preview: 'hello',
      },
    });

    expect(onQueueProcessingFailed).toHaveBeenCalledWith(
      'session-1',
      expect.objectContaining({
        message_id: 'message-1',
        queue_position: 1,
        error_message: 'dispatch failed',
      }),
    );
  });
});
