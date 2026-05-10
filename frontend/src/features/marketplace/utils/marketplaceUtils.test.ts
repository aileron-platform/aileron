import { beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { downloadBlob } from './downloadBlob';
import { getMarketplaceDetailFeatureItems } from '../components/MarketplaceDetailContentPanels';
import { getMarketplaceFeatureLabelKey } from './featureLabels';
import { getMarketplaceFeatureItemCount } from './marketplaceFeatureCounts';
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

  it('counts feature items by top-level folder when grouped', () => {
    expect(
      getMarketplaceFeatureItemCount([
        { id: 'review-main', path: 'skills/review/README.md' },
        { id: 'review-config', path: 'skills/review/config.toml' },
        { id: 'auth', path: 'skills/auth/SKILL.md' },
      ], 'skills'),
    ).toBe(2);
  });

  it('groups by first path segment when resource prefix is omitted', () => {
    expect(
      getMarketplaceFeatureItemCount([
        { id: 'review-main', path: 'review/README.md' },
        { id: 'review-config', path: 'review/config.toml' },
        { id: 'auth', path: 'auth/SKILL.md' },
      ], 'skills'),
    ).toBe(2);
  });

  it('falls back to item identifiers when path is not under the expected folder', () => {
    expect(
      getMarketplaceFeatureItemCount([
        { id: 'discord', path: '.mcp.json' },
        { id: 'playwright', path: '.mcp.json' },
      ], 'mcp'),
    ).toBe(2);
  });

  it('computes detail skills count by top-level folder instead of flat item length', () => {
    const detail = {
      provider: 'codex',
      packageFiles: [],
      featureContent: {
        hooks: [],
        mcpServers: [],
        agents: [],
        commands: [],
        outputStyles: [],
        skills: [
          { id: 'review-main', name: 'Review Main', path: 'skills/review/README.md' },
          { id: 'review-config', name: 'Review Config', path: 'skills/review/config.toml' },
          { id: 'auth', name: 'Auth', path: 'skills/auth/SKILL.md' },
        ],
      },
    } as const;

    const items = getMarketplaceDetailFeatureItems(detail as any, key => key);

    expect(items.find(item => item.id === 'skills')?.count).toBe(2);
  });

  it('uses shared feature count helpers for feature tab counts and does not hardcode .length in detail panel source', () => {
    const detailPanelPath = path.resolve(__dirname, '../components/MarketplaceDetailContentPanels.tsx');
    const editorPath = path.resolve(__dirname, '../features/marketplace-editor/MarketplaceEditorView.tsx');
    const detailPanelSource = fs.readFileSync(detailPanelPath, 'utf8');
    const editorSource = fs.readFileSync(editorPath, 'utf8');

    expect(detailPanelSource).toContain('getMarketplaceFeatureItemCount(detail.featureContent.hooks, \'hooks\')');
    expect(detailPanelSource).toContain('getMarketplaceFeatureItemCount(detail.featureContent.skills, \'skills\')');
    expect(editorSource).toContain('getMarketplaceFeatureCountByDirectory');

    const detailFeatureItemsMatch = /export const getMarketplaceDetailFeatureItems[\s\S]*?return items\.filter\(/.exec(detailPanelSource);
    const detailFeatureItemsBlock = detailFeatureItemsMatch?.[0] ?? '';
    const detailManualCountLines = detailFeatureItemsBlock
      .split('\n')
      .filter(line => /count:\s*.*\.length/.test(line) && !line.includes('detail.packageFiles.length'));
    const editorManualCountLines = editorSource
      .split('\n')
      .filter(line => /count[s]?:/.test(line) && line.includes('.length'));

    expect(detailManualCountLines).toEqual([]);
    expect(editorManualCountLines).toEqual([]);
  });
});
