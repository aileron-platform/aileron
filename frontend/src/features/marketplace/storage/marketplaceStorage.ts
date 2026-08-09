import type { MarketplaceFeatureKey, MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import type { AgenticTool } from '@/shared/types/agenticTool';
import { readSelectedWorkspaceId } from '@/features/workspace/public';

export type MarketplaceCenterViewMode = 'grid' | 'list';

export interface MarketplaceCenterFilterState {
  provider: MarketplaceProvider | 'all';
  category: string;
  features: MarketplaceFeatureKey[];
}

export interface MarketplaceWorkspaceOption {
  id: string;
  label: string;
  agenticTools: AgenticTool[];
}

export const MARKETPLACE_STORAGE_USER_SCOPE = 'local-user';
export const MARKETPLACE_CURRENT_WORKSPACE_OPTION_ID = 'current-workspace';

const MARKETPLACE_CENTER_FILTERS_KEY = 'marketplace.center.filters.v1';
const MARKETPLACE_CENTER_VIEW_MODE_KEY = 'marketplace.center.viewMode.v1';
const MARKETPLACE_INSTALL_WORKSPACE_KEY = 'marketplace.install.lastWorkspace.v1';

const marketplaceProviders = new Set<MarketplaceProvider | 'all'>(['all', 'claude-code', 'codex']);
const marketplaceFeatures = new Set<MarketplaceFeatureKey>(['mcp', 'commands', 'hooks', 'agentsMd', 'agents', 'outputStyle', 'skills']);

const getStorage = (): Storage | null => (
  typeof window === 'undefined' ? null : window.localStorage
);

const getScopedKey = (key: string, userScope?: string | null): string => (
  `${key}:${userScope || MARKETPLACE_STORAGE_USER_SCOPE}`
);

const readJson = <T>(key: string): T | null => {
  const storage = getStorage();
  if (!storage) return null;

  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) as T : null;
  } catch {
    storage.removeItem(key);
    return null;
  }
};

const writeJson = (key: string, value: unknown): void => {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota or privacy-mode errors; the current UI state still works in memory.
  }
};

export const loadMarketplaceCenterFilters = (userScope?: string | null): MarketplaceCenterFilterState => {
  const value = readJson<Partial<MarketplaceCenterFilterState>>(getScopedKey(MARKETPLACE_CENTER_FILTERS_KEY, userScope));
  return {
    provider: value?.provider && marketplaceProviders.has(value.provider) ? value.provider : 'all',
    category: typeof value?.category === 'string' && value.category ? value.category : 'all',
    features: Array.isArray(value?.features)
      ? value.features.filter((feature): feature is MarketplaceFeatureKey => marketplaceFeatures.has(feature as MarketplaceFeatureKey))
      : [],
  };
};

export const saveMarketplaceCenterFilters = (
  userScope: string | null | undefined,
  value: MarketplaceCenterFilterState,
): void => {
  writeJson(getScopedKey(MARKETPLACE_CENTER_FILTERS_KEY, userScope), {
    provider: value.provider,
    category: value.category,
    features: value.features,
  });
};

export const loadMarketplaceCenterViewMode = (userScope?: string | null): MarketplaceCenterViewMode => {
  const storage = getStorage();
  const value = storage?.getItem(getScopedKey(MARKETPLACE_CENTER_VIEW_MODE_KEY, userScope));
  return value === 'list' ? 'list' : 'grid';
};

export const saveMarketplaceCenterViewMode = (
  userScope: string | null | undefined,
  value: MarketplaceCenterViewMode,
): void => {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.setItem(getScopedKey(MARKETPLACE_CENTER_VIEW_MODE_KEY, userScope), value);
  } catch {
    // Ignore storage quota or privacy-mode errors; the current UI state still works in memory.
  }
};

export const loadMarketplaceInstallWorkspaceId = (userScope?: string | null): string | null => {
  const storage = getStorage();
  return storage?.getItem(getScopedKey(MARKETPLACE_INSTALL_WORKSPACE_KEY, userScope)) || null;
};

export const saveMarketplaceInstallWorkspaceId = (
  userScope: string | null | undefined,
  workspaceId: string,
): void => {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.setItem(getScopedKey(MARKETPLACE_INSTALL_WORKSPACE_KEY, userScope), workspaceId);
  } catch {
    // Ignore storage quota or privacy-mode errors; the current UI state still works in memory.
  }
};

export const resolveMarketplaceInstallWorkspaceId = (
  options: MarketplaceWorkspaceOption[],
  fallbackWorkspaceId: string,
  userScope?: string | null,
): string => {
  const currentWorkspaceId = readSelectedWorkspaceId();
  if (currentWorkspaceId && options.some(option => option.id === currentWorkspaceId)) {
    return currentWorkspaceId;
  }

  const rememberedWorkspaceId = loadMarketplaceInstallWorkspaceId(userScope);
  if (rememberedWorkspaceId && options.some(option => option.id === rememberedWorkspaceId)) {
    return rememberedWorkspaceId;
  }

  return options[0]?.id ?? currentWorkspaceId ?? rememberedWorkspaceId ?? fallbackWorkspaceId;
};
