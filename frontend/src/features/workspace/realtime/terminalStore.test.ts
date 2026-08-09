import { describe, expect, it } from 'vitest';
import { createTerminalStore, TerminalTabMetadata } from './terminalStore';

const tab = (
  overrides: Partial<TerminalTabMetadata> = {},
): TerminalTabMetadata => ({
  tab_id: 'tab-1',
  session_id: 'session-1',
  working_directory: '/workspace',
  cols: 80,
  rows: 24,
  created_at: 100,
  last_active_at: 100,
  status: 'running',
  exit_code: null,
  ...overrides,
});

describe('terminalStore', () => {
  it('updates the shared working directory without storing a separate name', () => {
    const store = createTerminalStore();

    store.upsertTab(tab());
    store.upsertTab(tab({ working_directory: '/workspace/apps/frontend', cols: 120 }));

    const snapshot = store.getSnapshot();
    expect(snapshot.tabs).toHaveLength(1);
    expect(snapshot.tabs[0]).toMatchObject({
      tabId: 'tab-1',
      workingDirectory: '/workspace/apps/frontend',
      cols: 120,
    });
    expect(snapshot.tabs[0]).not.toHaveProperty('name');
  });

  it('applies tab lists as an authoritative synced snapshot', () => {
    const store = createTerminalStore();

    store.upsertTab(tab({ tab_id: 'stale', session_id: 'stale-session' }));
    store.applyTabList([
      tab({ tab_id: 'tab-b', session_id: 'session-b', created_at: 200 }),
      tab({ tab_id: 'tab-a', session_id: 'session-a', created_at: 100 }),
    ]);

    const snapshot = store.getSnapshot();
    expect(snapshot.isSynced).toBe(true);
    expect(snapshot.tabs.map((item) => item.tabId)).toEqual(['tab-a', 'tab-b']);
    expect(snapshot.tabs.some((item) => item.tabId === 'stale')).toBe(false);
  });

  it('keeps canonical order with tab id tie breaker', () => {
    const store = createTerminalStore();

    store.applyTabList([
      tab({ tab_id: 'tab-b', session_id: 'session-b', created_at: 100 }),
      tab({ tab_id: 'tab-a', session_id: 'session-a', created_at: 100 }),
    ]);

    expect(store.getSnapshot().tabs.map((item) => item.tabId)).toEqual([
      'tab-a',
      'tab-b',
    ]);
  });
});
