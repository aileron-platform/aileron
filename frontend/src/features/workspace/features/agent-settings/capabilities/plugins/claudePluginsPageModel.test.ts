import { describe, expect, it } from 'vitest';
import type { ClaudePluginSummary } from '../../api/agentSettingsApi';
import {
  filterClaudePlugins,
  getClaudePluginPagination,
  getClaudeScopeInstallation,
  getNextClaudeScopeEnabled,
} from './claudePluginsPageModel';

const plugins: ClaudePluginSummary[] = [
  {
    id: 'review@official',
    name: 'Review Plugin',
    marketplace: 'official',
    version: '1.0.0',
    description: 'Review helper',
    author: 'Team',
    category: 'Review',
    homepage: null,
    enabled: true,
    installations: [{ scope: 'user', enabled: true, version: '1.0.0', installedAt: null, lastUpdated: null }],
    errors: [],
    resourceCounts: {
      commands: 1,
      agents: 0,
      hooks: 0,
      mcpServers: 0,
      skills: 1,
      outputStyles: 0,
    },
  },
  {
    id: 'mixed@official',
    name: 'Mixed Plugin',
    marketplace: 'official',
    version: '1.0.0',
    description: 'Mixed scope helper',
    author: 'Team',
    category: 'Ops',
    homepage: null,
    enabled: false,
    installations: [
      { scope: 'user', enabled: true, version: '1.0.0', installedAt: null, lastUpdated: null },
      { scope: 'local', enabled: false, version: '1.0.0', installedAt: null, lastUpdated: null },
    ],
    errors: [],
    resourceCounts: {
      commands: 0,
      agents: 0,
      hooks: 0,
      mcpServers: 0,
      skills: 0,
      outputStyles: 0,
    },
  },
];

describe('claudePluginsPageModel', () => {
  it('filters Claude plugins by display mode, search, marketplace, category, and scope', () => {
    expect(filterClaudePlugins(plugins, {
      displayMode: 'enabled',
      searchQuery: 'review',
      marketplaceFilter: 'official',
      categoryFilter: 'Review',
      scope: 'user',
    })).toEqual([plugins[0]]);

    expect(filterClaudePlugins(plugins, {
      displayMode: 'enabled',
      searchQuery: 'mixed',
      marketplaceFilter: 'official',
      categoryFilter: 'Ops',
      scope: 'user',
    })).toEqual([]);
  });

  it('resolves installation state and next toggle value for selected scopes', () => {
    expect(getClaudeScopeInstallation(plugins[1], 'local')).toEqual({
      scope: 'local',
      enabled: false,
      version: '1.0.0',
      installedAt: null,
      lastUpdated: null,
    });
    expect(getNextClaudeScopeEnabled(plugins[1], 'user')).toBe(false);
    expect(getNextClaudeScopeEnabled(plugins[1], 'local')).toBe(true);
    expect(getNextClaudeScopeEnabled(plugins[1], 'all')).toBe(true);
  });

  it('computes clamped pagination windows', () => {
    expect(getClaudePluginPagination(13, 3, 6)).toEqual({
      totalPages: 3,
      currentPage: 3,
      startItem: 13,
      endItem: 13,
    });

    expect(getClaudePluginPagination(0, 5, 6)).toEqual({
      totalPages: 1,
      currentPage: 1,
      startItem: 0,
      endItem: 0,
    });
  });
});
