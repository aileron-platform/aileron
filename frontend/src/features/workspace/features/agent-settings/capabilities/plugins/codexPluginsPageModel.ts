import type { PluginDisplayMode } from '../../components/plugin-list/PluginDisplayModeToggle';
import type { CodexPluginSummary } from '../../api/agentSettingsApi';

export type CodexLayer = 'user' | 'project';
export type CodexLayerFilter = 'all' | CodexLayer;

export interface CodexPluginFilterState {
  displayMode: PluginDisplayMode;
  searchQuery: string;
  marketplaceFilter: string;
  categoryFilter: string;
  layer: CodexLayerFilter;
}

export interface CodexPluginPaginationState {
  totalPages: number;
  currentPage: number;
  startItem: number;
  endItem: number;
}

export const filterCodexPlugins = (
  plugins: CodexPluginSummary[],
  filters: CodexPluginFilterState,
): CodexPluginSummary[] => {
  const normalizedQuery = filters.searchQuery.trim().toLowerCase();
  return plugins
    .filter((plugin) => filters.displayMode === 'all' || plugin.effectiveEnabled)
    .filter((plugin) => filters.marketplaceFilter === 'all' || plugin.marketplace === filters.marketplaceFilter)
    .filter((plugin) => filters.categoryFilter === 'all' || plugin.category === filters.categoryFilter)
    .filter((plugin) => filters.layer === 'all' || getCodexLayerState(plugin, filters.layer)?.configured)
    .filter((plugin) => {
      if (!normalizedQuery) {
        return true;
      }
      return [
        plugin.id,
        plugin.name,
        plugin.displayName,
        plugin.shortDescription,
        plugin.version,
        plugin.authorName,
        plugin.category,
        plugin.marketplace,
      ]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedQuery));
    });
};

export const getCodexLayerState = (plugin: CodexPluginSummary, layer: CodexLayer) => (
  plugin.scopes.find((item) => item.scope === layer)
);

export const getNextCodexLayerEnabled = (plugin: CodexPluginSummary, layer: CodexLayerFilter): boolean => {
  if (layer === 'all') {
    return !plugin.effectiveEnabled;
  }
  const state = getCodexLayerState(plugin, layer);
  return state?.configured ? state.enabled !== true : true;
};

export const isCodexLayerOverridden = (plugin: CodexPluginSummary, layer: CodexLayerFilter): boolean => {
  if (layer !== 'user') {
    return false;
  }
  const user = getCodexLayerState(plugin, 'user');
  const project = getCodexLayerState(plugin, 'project');
  return Boolean(user?.configured && project?.configured && user.enabled !== plugin.effectiveEnabled);
};

export const getCodexPluginPagination = (
  totalItems: number,
  requestedPage: number,
  pageSize: number,
): CodexPluginPaginationState => {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const currentPage = Math.min(Math.max(1, requestedPage), totalPages);
  return {
    totalPages,
    currentPage,
    startItem: totalItems > 0 ? (currentPage - 1) * pageSize + 1 : 0,
    endItem: totalItems > 0 ? Math.min(currentPage * pageSize, totalItems) : 0,
  };
};
