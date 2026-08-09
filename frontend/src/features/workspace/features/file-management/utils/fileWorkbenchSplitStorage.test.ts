import { beforeEach, describe, expect, it } from 'vitest';
import { fileWorkbenchSplitStorage, type FileWorkbenchSplitStorageEntry } from './fileWorkbenchSplitStorage';

const entry: FileWorkbenchSplitStorageEntry = {
  direction: 'horizontal',
  panes: [
    { tabIds: ['/a.ts'], activeTabId: '/a.ts' },
    { tabIds: ['/b.ts'], activeTabId: '/b.ts' },
  ],
  sizes: [60, 40],
};

describe('fileWorkbenchSplitStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns null when nothing has been saved', () => {
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('round-trips a saved split-view state', () => {
    fileWorkbenchSplitStorage.save('ws-1', entry);
    expect(fileWorkbenchSplitStorage.load('ws-1')).toEqual(entry);
  });

  it('discards malformed data without throwing', () => {
    localStorage.setItem('file_workbench_split_ws-1', 'not json');
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('discards an entry with more than 4 panes (defensive against corrupted/hand-edited storage)', () => {
    localStorage.setItem('file_workbench_split_ws-1', JSON.stringify({
      version: '1',
      data: { ...entry, panes: [...entry.panes, ...entry.panes, ...entry.panes] },
    }));
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('discards an entry with a non-string tab ID', () => {
    localStorage.setItem('file_workbench_split_ws-1', JSON.stringify({
      version: '1',
      data: {
        ...entry,
        panes: [{ ...entry.panes[0], tabIds: ['/a.ts', 42] }, entry.panes[1]],
      },
    }));
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('discards an entry with an invalid active tab ID', () => {
    localStorage.setItem('file_workbench_split_ws-1', JSON.stringify({
      version: '1',
      data: {
        ...entry,
        panes: [{ ...entry.panes[0], activeTabId: 42 }, entry.panes[1]],
      },
    }));
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('discards an entry with a non-finite pane size', () => {
    localStorage.setItem('file_workbench_split_ws-1', JSON.stringify({
      version: '1',
      data: { ...entry, sizes: [60, null] },
    }));
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('discards an entry when pane and size counts differ', () => {
    localStorage.setItem('file_workbench_split_ws-1', JSON.stringify({
      version: '1',
      data: { ...entry, sizes: [100] },
    }));
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });

  it('clears a specific workspace entry', () => {
    fileWorkbenchSplitStorage.save('ws-1', entry);
    fileWorkbenchSplitStorage.clear('ws-1');
    expect(fileWorkbenchSplitStorage.load('ws-1')).toBeNull();
  });
});
