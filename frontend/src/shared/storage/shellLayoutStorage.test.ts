import { beforeEach, describe, expect, it } from 'vitest';
import { createShellLayoutStorage, type ShellLayoutStoragePreferences } from './shellLayoutStorage';

const defaults: ShellLayoutStoragePreferences = {
  navSidebarCollapsed: false,
  navSidebarWidth: 240,
  secondColumnCollapsed: false,
  secondColumnWidth: 320,
  companionCollapsed: false,
  companionWidth: 320,
  companionHeight: 240,
  companionPlacement: 'side',
};

const limits = {
  navSidebarWidth: { min: 120, max: 500 },
  secondColumnWidth: { min: 160, max: 600 },
  companionWidth: { min: 280, max: 600 },
  companionHeight: { min: 160, max: 520 },
};

describe('createShellLayoutStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns null when nothing has been saved', () => {
    const storage = createShellLayoutStorage({ featureKey: 'marketplace', limits });
    expect(storage.load('pkg-1')).toBeNull();
  });

  it('round-trips saved preferences for a given entity', () => {
    const storage = createShellLayoutStorage({ featureKey: 'marketplace', limits });
    const preferences: ShellLayoutStoragePreferences = {
      ...defaults,
      navSidebarWidth: 280,
      companionPlacement: 'bottom',
    };
    storage.save('pkg-1', preferences);
    expect(storage.load('pkg-1')).toEqual(preferences);
  });

  it('keeps separate entities and feature keys under separate storage keys', () => {
    const marketplaceStorage = createShellLayoutStorage({ featureKey: 'marketplace', limits });
    const knowledgeBaseStorage = createShellLayoutStorage({ featureKey: 'knowledge-base', limits });
    marketplaceStorage.save('pkg-1', { ...defaults, navSidebarWidth: 280 });
    marketplaceStorage.save('pkg-2', { ...defaults, navSidebarWidth: 300 });
    knowledgeBaseStorage.save('pkg-1', { ...defaults, navSidebarWidth: 320 });
    expect(marketplaceStorage.load('pkg-1')?.navSidebarWidth).toBe(280);
    expect(marketplaceStorage.load('pkg-2')?.navSidebarWidth).toBe(300);
    expect(knowledgeBaseStorage.load('pkg-1')?.navSidebarWidth).toBe(320);
  });

  it('clamps out-of-range widths and heights on load', () => {
    const storage = createShellLayoutStorage({ featureKey: 'marketplace', limits });
    storage.save('pkg-1', { ...defaults, navSidebarWidth: 9000, companionHeight: 1 });
    const loaded = storage.load('pkg-1');
    expect(loaded?.navSidebarWidth).toBe(500);
    expect(loaded?.companionHeight).toBe(160);
  });

  it('discards mismatched versions and malformed JSON', () => {
    const storage = createShellLayoutStorage({ featureKey: 'marketplace', limits });
    localStorage.setItem('shell_layout_marketplace_pkg-1', JSON.stringify({ version: '0', data: defaults }));
    expect(storage.load('pkg-1')).toBeNull();
    expect(localStorage.getItem('shell_layout_marketplace_pkg-1')).toBeNull();
    localStorage.setItem('shell_layout_marketplace_pkg-1', 'not json');
    expect(storage.load('pkg-1')).toBeNull();
  });

  it('clears a specific entity', () => {
    const storage = createShellLayoutStorage({ featureKey: 'marketplace', limits });
    storage.save('pkg-1', defaults);
    storage.clear('pkg-1');
    expect(storage.load('pkg-1')).toBeNull();
  });
});
