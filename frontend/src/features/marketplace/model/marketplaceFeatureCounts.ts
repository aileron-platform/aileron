interface MarketplaceFeatureCountableItem {
  id?: string;
  path?: string | null;
}

const getPathPrefix = (resourceDirectory: string): string => `${resourceDirectory.trim().replace(/^\/+|\/+$/g, '')}/`;

const normalizePath = (value: string): string => value.trim().replace(/^\/+|\/+$/g, '');

const getTopLevelDirectorySegment = (path: string, resourceDirectory: string): string | null => {
  const normalizedPath = normalizePath(path);
  const prefix = getPathPrefix(resourceDirectory);
  if (!normalizedPath.startsWith(prefix)) {
    const [firstSegment, ...restSegments] = normalizedPath.split('/');
    return restSegments.length > 0 ? firstSegment : null;
  }
  const remainder = normalizedPath.slice(prefix.length);
  if (!remainder) return null;
  const [segment] = remainder.split('/');
  return segment || null;
};

export const getMarketplaceFeatureItemCount = (
  items: readonly MarketplaceFeatureCountableItem[],
  resourceDirectory: string,
): number => {
  const keys = new Set<string>();
  for (const item of items) {
    const path = item.path ?? '';
    const groupedKey = getTopLevelDirectorySegment(path, resourceDirectory) || item.id;
    if (!groupedKey) continue;
    keys.add(groupedKey);
  }

  return keys.size || items.length;
};

export const getMarketplaceFeatureCountByDirectory = {
  agents: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'agents'),
  commands: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'commands'),
  hooks: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'hooks'),
  mcp: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'mcp'),
  outputStyles: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'output-styles'),
  policies: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'policies'),
  skills: (items: readonly MarketplaceFeatureCountableItem[]) => getMarketplaceFeatureItemCount(items, 'skills'),
} as const;
