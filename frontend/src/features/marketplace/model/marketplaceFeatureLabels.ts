import type { MarketplaceFeatureKey, MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';

export const getMarketplaceFeatureLabelKey = (
  provider: MarketplaceProvider,
  feature: MarketplaceFeatureKey,
): string => {
  if (feature === 'agentsMd') {
    if (provider === 'claude-code') return 'marketplace.features.claudeMd';
  }
  if (feature === 'agents') return 'marketplace.features.subagents';
  if (feature === 'commands') return 'marketplace.features.slashCommands';
  return `marketplace.features.${feature}`;
};
