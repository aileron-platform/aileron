import type { PluginDisplayMode } from '../../components/plugin-list/PluginDisplayModeToggle';
import type { ClaudePluginScope, ClaudePluginSummary } from '../../api/agentSettingsApi';

export type ClaudeScopeFilter = 'all' | ClaudePluginScope;

export interface ClaudePluginFilterState {
  displayMode: PluginDisplayMode;
  searchQuery: string;
  marketplaceFilter: string;
  categoryFilter: string;
  scope: ClaudeScopeFilter;
}

export interface ClaudePluginPaginationState {
  totalPages: number;
  currentPage: number;
  startItem: number;
  endItem: number;
}

export const filterClaudePlugins = (
  plugins: ClaudePluginSummary[],
  filters: ClaudePluginFilterState,
): ClaudePluginSummary[] => {
  const normalizedQuery = filters.searchQuery.trim().toLowerCase();
  return plugins
    .filter((plugin) => filters.displayMode === 'all' || plugin.enabled)
    .filter((plugin) => filters.marketplaceFilter === 'all' || plugin.marketplace === filters.marketplaceFilter)
    .filter((plugin) => filters.categoryFilter === 'all' || plugin.category === filters.categoryFilter)
    .filter((plugin) => filters.scope === 'all' || plugin.installations.some((installation) => installation.scope === filters.scope))
    .filter((plugin) => {
      if (!normalizedQuery) {
        return true;
      }
      return [
        plugin.id,
        plugin.name,
        plugin.description,
        plugin.version,
        plugin.author,
        plugin.category,
        plugin.marketplace,
      ]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedQuery));
    });
};

export const getClaudeScopeInstallation = (plugin: ClaudePluginSummary, scope: ClaudePluginScope) => (
  plugin.installations.find((installation) => installation.scope === scope)
);

export const getNextClaudeScopeEnabled = (plugin: ClaudePluginSummary, scope: ClaudeScopeFilter): boolean => {
  if (scope === 'all') {
    return !plugin.enabled;
  }
  return getClaudeScopeInstallation(plugin, scope)?.enabled !== true;
};

export const getClaudePluginPagination = (
  totalItems: number,
  requestedPage: number,
  pageSize: number,
): ClaudePluginPaginationState => {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const currentPage = Math.min(Math.max(1, requestedPage), totalPages);
  return {
    totalPages,
    currentPage,
    startItem: totalItems > 0 ? (currentPage - 1) * pageSize + 1 : 0,
    endItem: totalItems > 0 ? Math.min(currentPage * pageSize, totalItems) : 0,
  };
};
