import type { MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import { providerEditorTabs, type MarketplaceEditorTab } from './marketplaceEditorTabsModel';

export const resolveMarketplaceEditorSection = (
  provider: MarketplaceProvider,
  raw: string | undefined,
): MarketplaceEditorTab => {
  const tabs = providerEditorTabs[provider];
  const match = tabs.find((tab) => tab === raw);
  return match ?? 'basic';
};

export const buildMarketplaceEditorPath = (args: {
  provider: MarketplaceProvider;
  packageId: string;
  section: MarketplaceEditorTab;
}): string => {
  return `/marketplace/packages/${args.provider}/${args.packageId}/edit/${args.section}`;
};
