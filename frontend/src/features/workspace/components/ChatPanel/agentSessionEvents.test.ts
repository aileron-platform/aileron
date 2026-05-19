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

  it('dispatches task failure code with error message', () => {
    const dispatcher = new AgentSessionEventDispatcher();
    const onTaskFailed = vi.fn();

    dispatcher.subscribe({ onTaskFailed });

    dispatcher.dispatch({
      type: 'task:failed',
      session_id: 'session-1',
      task_id: 'task-1',
      timestamp: '2026-05-01T00:00:00.000Z',
      data: {
        session_id: 'session-1',
        task_id: 'task-1',
        status: 'failed',
        error_message: 'workspace.chat.errors.authenticationFailed',
        error_code: 'AUTHENTICATION_FAILED',
      },
    });

    expect(onTaskFailed).toHaveBeenCalledWith(
      'session-1',
      'task-1',
      'workspace.chat.errors.authenticationFailed',
      'AUTHENTICATION_FAILED',
    );
  });

  it('dispatches task status notice events', () => {
    const dispatcher = new AgentSessionEventDispatcher();
    const onTaskStatusNotice = vi.fn();

    dispatcher.subscribe({ onTaskStatusNotice });

    dispatcher.dispatch({
      type: 'task:status_notice',
      session_id: 'session-1',
      task_id: 'task-1',
      timestamp: '2026-05-18T00:00:00.000Z',
      data: {
        session_id: 'session-1',
        task_id: 'task-1',
        message_key: 'workspace.chat.status.codexReconnecting',
        severity: 'warning',
        params: {
          attempt: 2,
          max_attempts: 5,
        },
      },
    });

    expect(onTaskStatusNotice).toHaveBeenCalledWith(
      'session-1',
      'task-1',
      expect.objectContaining({
        message_key: 'workspace.chat.status.codexReconnecting',
        severity: 'warning',
        params: {
          attempt: 2,
          max_attempts: 5,
        },
      }),
    );
  });
});
