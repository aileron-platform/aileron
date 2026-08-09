import { beforeEach, describe, expect, it } from 'vitest';

import {
  loadMarketplaceCenterFilters,
  loadMarketplaceCenterViewMode,
  resolveMarketplaceInstallWorkspaceId,
  saveMarketplaceCenterFilters,
  saveMarketplaceCenterViewMode,
  saveMarketplaceInstallWorkspaceId,
} from './marketplaceStorage';
import type { MarketplaceWorkspaceOption } from './marketplaceStorage';

describe('marketplaceStorage', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('sanitizes persisted center filters and restores valid view mode', () => {
    window.localStorage.setItem('marketplace.center.filters.v1:local-user', JSON.stringify({
      provider: 'unknown-provider',
      category: '',
      features: ['mcp', 'unknown-feature', 'skills'],
    }));
    window.localStorage.setItem('marketplace.center.viewMode.v1:local-user', 'list');

    expect(loadMarketplaceCenterFilters('local-user')).toEqual({
      provider: 'all',
      category: 'all',
      features: ['mcp', 'skills'],
    });
    expect(loadMarketplaceCenterViewMode('local-user')).toBe('list');

    saveMarketplaceCenterFilters('local-user', {
      provider: 'codex',
      category: 'productivity',
      features: ['hooks'],
    });
    saveMarketplaceCenterViewMode('local-user', 'grid');

    expect(loadMarketplaceCenterFilters('local-user')).toEqual({
      provider: 'codex',
      category: 'productivity',
      features: ['hooks'],
    });
    expect(loadMarketplaceCenterViewMode('local-user')).toBe('grid');

    window.localStorage.setItem('marketplace.center.filters.v1:local-user', JSON.stringify({
      provider: 'gemini',
      category: 'productivity',
      features: ['hooks'],
    }));
    expect(loadMarketplaceCenterFilters('local-user').provider).toBe('all');
  });

  it('resolves install workspace by current workspace, remembered workspace, then fallback', () => {
    const options: MarketplaceWorkspaceOption[] = [
      { id: 'ws-1', label: 'Workspace One', agenticTools: ['codex'] },
      { id: 'ws-2', label: 'Workspace Two', agenticTools: ['codex'] },
    ];

    saveMarketplaceInstallWorkspaceId('local-user', 'ws-2');
    expect(resolveMarketplaceInstallWorkspaceId(options, 'current-workspace', 'local-user')).toBe('ws-2');

    window.localStorage.setItem('selectedWorkspaceId', 'ws-1');
    expect(resolveMarketplaceInstallWorkspaceId(options, 'current-workspace', 'local-user')).toBe('ws-1');

    window.localStorage.clear();
    expect(resolveMarketplaceInstallWorkspaceId([], 'current-workspace', 'local-user')).toBe('current-workspace');
  });
});
