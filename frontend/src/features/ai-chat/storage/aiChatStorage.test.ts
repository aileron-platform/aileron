// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getLastThreadId,
  getShowInitMessages,
  getThreadListSortMode,
  isUnread,
  setLastReadAt,
  setLastThreadId,
  setShowInitMessages,
  setThreadListSortMode,
  subscribeLocalState,
} from './aiChatStorage';

beforeEach(() => {
  localStorage.clear();
});

describe('ai chat local state', () => {
  it('stores and reads last thread per user+workspace', () => {
    setLastThreadId('u1', 'w1', 't1');

    expect(getLastThreadId('u1', 'w1')).toBe('t1');
    expect(getLastThreadId('u1', 'w2')).toBeNull();
    expect(localStorage.getItem('aichat.lastThread.u1.w1')).toBe('t1');
  });

  it('notifies same-tab subscribers on write', () => {
    const onChange = vi.fn();
    const unsubscribe = subscribeLocalState(onChange);

    setLastThreadId('u1', 'w1', 't1');

    expect(onChange).toHaveBeenCalledTimes(1);
    unsubscribe();
    setLastThreadId('u1', 'w1', 't2');
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('notifies subscribers for cross-tab ai chat storage events', () => {
    const onChange = vi.fn();
    const unsubscribe = subscribeLocalState(onChange);

    window.dispatchEvent(new StorageEvent('storage', { key: 'aichat.lastThread.u1.w1' }));
    window.dispatchEvent(new StorageEvent('storage', { key: 'other.key' }));

    expect(onChange).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it('stores thread list sort mode per user+workspace', () => {
    setThreadListSortMode('u1', 'w1', 'title');

    expect(getThreadListSortMode('u1', 'w1')).toBe('title');
    expect(getThreadListSortMode('u1', 'w2')).toBe('activity');
    expect(localStorage.getItem('aichat.threadListSort.u1.w1')).toBe('title');

    localStorage.setItem('aichat.threadListSort.u1.w1', 'invalid');
    expect(getThreadListSortMode('u1', 'w1')).toBe('activity');
  });

  it('stores the show-init-messages preference, defaulting to hidden', () => {
    expect(getShowInitMessages()).toBe(false);

    setShowInitMessages(true);
    expect(getShowInitMessages()).toBe(true);
    expect(localStorage.getItem('aichat.showInitMessages')).toBe('true');

    setShowInitMessages(false);
    expect(getShowInitMessages()).toBe(false);
  });

  it('notifies same-tab subscribers when the show-init-messages preference changes', () => {
    const onChange = vi.fn();
    const unsubscribe = subscribeLocalState(onChange);

    setShowInitMessages(true);

    expect(onChange).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it('isUnread compares updatedAt with lastRead and ignores running threads', () => {
    const base = { id: 't1', updatedAt: '2026-07-08T10:00:00Z', status: 'complete' } as const;

    expect(isUnread(base, 'u1', 'w1')).toBe(true);
    setLastReadAt('u1', 'w1', 't1', '2026-07-08T11:00:00Z');
    expect(isUnread(base, 'u1', 'w1')).toBe(false);
    expect(isUnread({ ...base, status: 'working' }, 'u1', 'w1')).toBe(false);
    expect(isUnread({ ...base, status: 'draft' }, 'u1', 'w1')).toBe(false);
  });
});
