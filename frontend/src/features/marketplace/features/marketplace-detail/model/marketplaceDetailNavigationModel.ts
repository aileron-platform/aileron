import {
  Bot,
  Command,
  FileArchive,
  FileText,
  Network,
  Sparkles,
  Wand2,
  Zap,
  type LucideIcon,
} from 'lucide-react';

import { getMarketplaceFeatureLabelKey } from '@/features/marketplace/model/marketplaceFeatureLabels';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

export type MarketplaceDetailFeatureTab =
  | 'readme'
  | 'agents-md'
  | 'hooks'
  | 'mcp'
  | 'agent'
  | 'commands'
  | 'output-style'
  | 'skills'
  | 'files';

export interface MarketplaceDetailFeatureItem {
  id: MarketplaceDetailFeatureTab;
  name: string;
  icon: LucideIcon;
  count: number;
}

export const getMarketplaceDetailFeatureItems = (
  detail: MarketplacePackageDetail,
  t: (key: string, params?: Record<string, unknown>) => string,
): MarketplaceDetailFeatureItem[] => {
  const items: MarketplaceDetailFeatureItem[] = [
    { id: 'readme', name: t('marketplace.detail.readme.title'), icon: FileText, count: 0 },
    { id: 'agents-md', name: t(getMarketplaceFeatureLabelKey(detail.targetClient, 'agentsMd')), icon: FileText, count: 0 },
    { id: 'hooks', name: t('marketplace.features.hooks'), icon: Zap, count: 0 },
    { id: 'mcp', name: t('marketplace.features.mcp'), icon: Network, count: 0 },
    { id: 'agent', name: t('marketplace.features.subagents'), icon: Bot, count: 0 },
    { id: 'commands', name: t('marketplace.features.slashCommands'), icon: Command, count: 0 },
    { id: 'output-style', name: t('marketplace.features.outputStyle'), icon: Wand2, count: 0 },
    { id: 'skills', name: t('marketplace.features.skills'), icon: Sparkles, count: 0 },
    { id: 'files', name: t('marketplace.detail.tabs.files'), icon: FileArchive, count: 0 },
  ];

  return items.filter(item => {
    if (item.id === 'output-style') return detail.targetClient === 'claude-code';
    return true;
  });
};
