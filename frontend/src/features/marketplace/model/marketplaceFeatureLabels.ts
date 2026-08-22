import type {
  MarketplaceFeatureKey,
  MarketplacePackageSummary,
  MarketplaceTargetClient,
} from '@/features/marketplace/model/marketplaceTypes';

const MARKETPLACE_FEATURE_ORDER: MarketplaceFeatureKey[] = [
  'agentsMd',
  'hooks',
  'mcp',
  'agents',
  'commands',
  'outputStyle',
  'skills',
];

export const getMarketplacePackageFeatures = (
  item: MarketplacePackageSummary,
): MarketplaceFeatureKey[] => {
  const haystack = [...item.indexedResourceNames, ...item.tags]
    .join(' ')
    .toLowerCase();
  return MARKETPLACE_FEATURE_ORDER.filter(feature => {
    switch (feature) {
      case 'agentsMd':
        return haystack.includes('agentsmd')
          || haystack.includes('agents.md')
          || haystack.includes('claude.md');
      case 'hooks':
        return haystack.includes('hook');
      case 'mcp':
        return haystack.includes('mcp');
      case 'agents':
        return haystack.includes('agent') || haystack.includes('subagent');
      case 'commands':
        return haystack.includes('command') || haystack.includes('slash');
      case 'outputStyle':
        return haystack.includes('outputstyle')
          || haystack.includes('output-style')
          || haystack.includes('output style');
      case 'skills':
        return haystack.includes('skill');
    }
  });
};

export const getMarketplaceFeatureLabelKey = (
  targetClient: MarketplaceTargetClient,
  feature: MarketplaceFeatureKey,
): string => {
  if (feature === 'agentsMd') {
    if (targetClient === 'claude-code') return 'marketplace.features.claudeMd';
  }
  if (feature === 'agents') return 'marketplace.features.subagents';
  if (feature === 'commands') return 'marketplace.features.slashCommands';
  return `marketplace.features.${feature}`;
};
