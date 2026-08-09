import type {
  MarketplaceFeatureKey,
  MarketplaceImportProvider,
  MarketplaceImportResult,
  MarketplaceListQuery,
  MarketplaceProvider,
} from '@/features/marketplace/model/marketplaceTypes';

export const PAGE_SIZE_OPTIONS = [6, 12, 24];
export const MARKETPLACE_FEATURES: MarketplaceFeatureKey[] = ['mcp', 'commands', 'hooks', 'agentsMd', 'agents', 'outputStyle', 'skills'];
export const IMPORT_SCAN_HIDDEN_VALIDATION_CODES = new Set(['marketplace.validation.metadata_conflict']);
export const IMPORT_PROVIDERS: MarketplaceImportProvider[] = ['all', 'claude-code', 'codex'];

export interface MarketplaceCenterQueryState {
  searchTerm: string;
  provider: MarketplaceProvider | 'all';
  category: string;
  activeFeatures: Set<MarketplaceFeatureKey>;
  page: number;
  pageSize: number;
}

export type MarketplaceImportedPackageRevealFilters = Pick<
  MarketplaceListQuery,
  'q' | 'provider' | 'category' | 'features' | 'page'
>;

export const buildMarketplaceListQuery = (
  state: MarketplaceCenterQueryState,
  overrides: Partial<MarketplaceListQuery> = {},
): MarketplaceListQuery => ({
  q: overrides.q ?? state.searchTerm,
  provider: overrides.provider ?? state.provider,
  category: overrides.category ?? state.category,
  features: overrides.features ?? Array.from(state.activeFeatures),
  sort: 'updatedAt',
  direction: 'desc',
  page: overrides.page ?? state.page,
  pageSize: overrides.pageSize ?? state.pageSize,
});

export const toggleMarketplaceFeature = (
  current: Set<MarketplaceFeatureKey>,
  feature: MarketplaceFeatureKey,
) => {
  const next = new Set(current);
  if (next.has(feature)) {
    next.delete(feature);
  } else {
    next.add(feature);
  }
  return next;
};

export const resolveImportedPackageRevealFilters = (
  importResult: MarketplaceImportResult,
): MarketplaceImportedPackageRevealFilters | null => {
  if (importResult.imported.length === 0) {
    return null;
  }
  const importedProviders = new Set(importResult.imported.map(item => item.provider));
  return {
    q: '',
    provider: importedProviders.size === 1 ? importResult.imported[0].provider : 'all',
    category: 'all',
    features: [],
    page: 1,
  };
};

const normalizeMarketplaceMessageKey = (value: string) => {
  const importValidationPrefix = 'marketplace.import.validation.';
  if (!value.startsWith(importValidationPrefix)) {
    return value;
  }
  const suffix = value.slice(importValidationPrefix.length);
  return `${importValidationPrefix}${suffix.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase())}`;
};

export const translateMarketplaceMessage = (
  t: (key: string, params?: Record<string, unknown>) => string,
  value: string,
  params?: Record<string, unknown>,
) => {
  if (value.startsWith('marketplace.')) {
    return t(normalizeMarketplaceMessageKey(value), params);
  }
  return t('marketplace.errors.unknown');
};
