import { beforeEach, describe, expect, it, vi } from 'vitest';
import { downloadBlob } from './downloadBlob';
import { getMarketplaceFeatureLabelKey } from './featureLabels';
import {
  loadMarketplaceCenterFilters,
  loadMarketplaceCenterViewMode,
  resolveMarketplaceInstallWorkspaceId,
  saveMarketplaceCenterFilters,
  saveMarketplaceCenterViewMode,
  saveMarketplaceInstallWorkspaceId,
} from './marketplaceLocalStorage';

describe('marketplace utils', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('maps provider-specific feature labels', () => {
    expect(getMarketplaceFeatureLabelKey('claude-code', 'agentsMd')).toBe('marketplace.features.claudeMd');
    expect(getMarketplaceFeatureLabelKey('gemini', 'agentsMd')).toBe('marketplace.features.geminiMd');
    expect(getMarketplaceFeatureLabelKey('codex', 'agents')).toBe('marketplace.features.subagents');
    expect(getMarketplaceFeatureLabelKey('codex', 'commands')).toBe('marketplace.features.slashCommands');
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
      provider: 'gemini',
      category: 'productivity',
      features: ['hooks'],
    });
    saveMarketplaceCenterViewMode('local-user', 'grid');

    expect(loadMarketplaceCenterFilters('local-user')).toEqual({
      provider: 'gemini',
      category: 'productivity',
      features: ['hooks'],
    });
    expect(loadMarketplaceCenterViewMode('local-user')).toBe('grid');
  });

  it('resolves install workspace by current workspace, remembered workspace, then fallback', () => {
    const options = [
      { id: 'ws-1', label: 'Workspace One' },
      { id: 'ws-2', label: 'Workspace Two' },
    ];

    saveMarketplaceInstallWorkspaceId('local-user', 'ws-2');
    expect(resolveMarketplaceInstallWorkspaceId(options, 'current-workspace', 'local-user')).toBe('ws-2');

    window.localStorage.setItem('selectedWorkspaceId', 'ws-1');
    expect(resolveMarketplaceInstallWorkspaceId(options, 'current-workspace', 'local-user')).toBe('ws-1');

    window.localStorage.clear();
    expect(resolveMarketplaceInstallWorkspaceId([], 'current-workspace', 'local-user')).toBe('current-workspace');
  });

  it('downloads blobs through a temporary anchor and revokes object URLs', () => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:marketplace-download');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const anchor = document.createElement('a');
    const click = vi.spyOn(anchor, 'click').mockImplementation(() => undefined);
    const remove = vi.spyOn(anchor, 'remove').mockImplementation(() => undefined);
    const appendChild = vi.spyOn(document.body, 'appendChild');
    const createElement = vi.spyOn(document, 'createElement');

    createElement.mockReturnValue(anchor);

    downloadBlob(new Blob(['content'], { type: 'text/plain' }), 'package.zip');

    expect(createObjectURL).toHaveBeenCalled();
    expect(appendChild).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:marketplace-download');

    createElement.mockRestore();
    appendChild.mockRestore();
    click.mockRestore();
    remove.mockRestore();
    createObjectURL.mockRestore();
    revokeObjectURL.mockRestore();
  });
});
