import { describe, expect, it } from 'vitest';
import type { CodexPluginSummary } from '../../api/agentSettingsApi';
import {
  getCodexLayerState,
  getCodexPluginPagination,
  getNextCodexLayerEnabled,
  isCodexLayerOverridden,
  filterCodexPlugins,
} from './codexPluginsPageModel';

const plugins: CodexPluginSummary[] = [
  {
    id: 'alpha@local',
    name: 'alpha',
    displayName: 'Alpha Plugin',
    shortDescription: 'Alpha review helper',
    version: '1.0.0',
    authorName: 'Team',
    category: 'Review',
    capabilities: [],
    brandColor: null,
    homepage: null,
    marketplace: 'local',
    listed: true,
    installed: true,
    effectiveEnabled: true,
    scopes: [
      { scope: 'user', configured: true, enabled: true },
      { scope: 'project', configured: false, enabled: null },
    ],
    resourceCounts: { skills: 1, mcpServers: 0, apps: 0, hooks: 0 },
  },
  {
    id: 'gamma@local',
    name: 'gamma',
    displayName: 'Gamma Plugin',
    shortDescription: 'Gamma override helper',
    version: '1.0.0',
    authorName: 'Team',
    category: 'Review',
    capabilities: [],
    brandColor: null,
    homepage: null,
    marketplace: 'local',
    listed: true,
    installed: true,
    effectiveEnabled: false,
    scopes: [
      { scope: 'user', configured: true, enabled: true },
      { scope: 'project', configured: true, enabled: false },
    ],
    resourceCounts: { skills: 0, mcpServers: 0, apps: 0, hooks: 0 },
  },
];

describe('codexPluginsPageModel', () => {
  it('filters enabled Codex plugins by search, marketplace, category, and configured layer', () => {
    expect(filterCodexPlugins(plugins, {
      displayMode: 'enabled',
      searchQuery: 'alpha',
      marketplaceFilter: 'local',
      categoryFilter: 'Review',
      layer: 'user',
    })).toEqual([plugins[0]]);

    expect(filterCodexPlugins(plugins, {
      displayMode: 'enabled',
      searchQuery: 'gamma',
      marketplaceFilter: 'local',
      categoryFilter: 'Review',
      layer: 'user',
    })).toEqual([]);
  });

  it('resolves selected layer state and next toggle value', () => {
    expect(getCodexLayerState(plugins[1], 'project')).toEqual({ scope: 'project', configured: true, enabled: false });
    expect(getNextCodexLayerEnabled(plugins[1], 'project')).toBe(true);
    expect(getNextCodexLayerEnabled(plugins[1], 'user')).toBe(false);
    expect(getNextCodexLayerEnabled(plugins[1], 'all')).toBe(true);
  });

  it('detects user layer overrides from project effective state', () => {
    expect(isCodexLayerOverridden(plugins[1], 'user')).toBe(true);
    expect(isCodexLayerOverridden(plugins[1], 'project')).toBe(false);
    expect(isCodexLayerOverridden(plugins[0], 'user')).toBe(false);
  });

  it('computes clamped pagination windows', () => {
    expect(getCodexPluginPagination(13, 3, 6)).toEqual({
      totalPages: 3,
      currentPage: 3,
      startItem: 13,
      endItem: 13,
    });

    expect(getCodexPluginPagination(0, 5, 6)).toEqual({
      totalPages: 1,
      currentPage: 1,
      startItem: 0,
      endItem: 0,
    });
  });
});
