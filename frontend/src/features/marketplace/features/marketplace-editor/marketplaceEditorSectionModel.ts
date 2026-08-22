import type {
  MarketplaceAuthoringCapability,
  MarketplaceAuthoringFeature,
  MarketplacePackageFormat,
  MarketplaceTargetClient,
} from '@/features/marketplace/model/marketplaceTypes';
import { visibleMarketplaceEditorTabs, type MarketplaceEditorTab } from './marketplaceEditorTabsModel';

export const resolveMarketplaceEditorSection = (
  capabilities: Record<MarketplaceAuthoringFeature, MarketplaceAuthoringCapability> | null,
  raw: string | undefined,
): MarketplaceEditorTab => {
  if (!capabilities) return 'basic';
  const tabs = visibleMarketplaceEditorTabs(capabilities);
  const match = tabs.find((tab) => tab === raw);
  return match ?? 'basic';
};

export const buildMarketplaceEditorPath = (args: {
  targetClient: MarketplaceTargetClient;
  packageId: string;
  packageFormat: MarketplacePackageFormat;
  section: MarketplaceEditorTab;
}): string => {
  return `/marketplace/packages/${args.targetClient}/${args.packageId}/edit/${args.section}?packageFormat=${encodeURIComponent(args.packageFormat)}`;
};
