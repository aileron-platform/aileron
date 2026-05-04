import { describe, expect, it } from 'vitest';
import { createTerminalStore, TerminalTabMetadata } from './terminalStore';

const tab = (
  overrides: Partial<TerminalTabMetadata> = {},
): TerminalTabMetadata => ({
  tab_id: 'tab-1',
  session_id: 'session-1',
  name: 'Terminal 1',
  workspace_path: '/workspace',
  cols: 80,
  rows: 24,
  created_at: 100,
  last_active_at: 100,
  status: 'running',
  exit_code: null,
  ...overrides,
});

describe('terminalStore', () => {
  it('upserts tabs by tab id instead of appending duplicates', () => {
    const store = createTerminalStore();

    store.upsertTab(tab());
    store.upsertTab(tab({ name: 'Renamed terminal', cols: 120 }));

    const snapshot = store.getSnapshot();
    expect(snapshot.tabs).toHaveLength(1);
    expect(snapshot.tabs[0]).toMatchObject({
      tabId: 'tab-1',
      name: 'Renamed terminal',
      cols: 120,
    });
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

  it('tracks output sequence on history entries and tabs', () => {
    const store = createTerminalStore();
    store.upsertTab(tab());

    store.appendOutput('tab-1', 'hello', 7);

    const [entry] = store.getSnapshot().tabs[0].history;
    expect(entry).toMatchObject({ data: 'hello', seq: 7 });
    expect(store.getSnapshot().tabs[0].lastOutputSeq).toBe(7);
  });
});
