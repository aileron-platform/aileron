import { describe, expect, it, vi } from 'vitest';
import {
  WORKSPACE_CHAT_INSERT_DRAFT_EVENT,
  WORKSPACE_CHAT_SEND_DRAFT_EVENT,
  dispatchInsertDraftEvent,
  dispatchSendDraftEvent,
} from './chatEvents';

describe('chatEvents Canvas review draft events', () => {
  it('dispatches insert and send draft events with structured content', () => {
    const insertListener = vi.fn();
    const sendListener = vi.fn();
    window.addEventListener(WORKSPACE_CHAT_INSERT_DRAFT_EVENT, insertListener);
    window.addEventListener(WORKSPACE_CHAT_SEND_DRAFT_EVENT, sendListener);

    dispatchInsertDraftEvent({ content: 'Canvas review request', mode: 'replace' });
    dispatchSendDraftEvent({ content: 'Canvas review request', mode: 'append' });

    expect(insertListener).toHaveBeenCalledWith(expect.objectContaining({
      detail: { content: 'Canvas review request', mode: 'replace' },
    }));
    expect(sendListener).toHaveBeenCalledWith(expect.objectContaining({
      detail: { content: 'Canvas review request', mode: 'append' },
    }));

    window.removeEventListener(WORKSPACE_CHAT_INSERT_DRAFT_EVENT, insertListener);
    window.removeEventListener(WORKSPACE_CHAT_SEND_DRAFT_EVENT, sendListener);
  });
});
