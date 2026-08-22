import type {
  MarketplaceAuthoringCapability,
  MarketplaceAuthoringFeature,
  MarketplaceTargetClient,
} from '@/features/marketplace/model/marketplaceTypes';
import type { FileTreeNode } from '@/shared/components/file-workbench';

export const marketplaceEditorTabs = ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'skills', 'files'] as const;
export type MarketplaceEditorTab = typeof marketplaceEditorTabs[number];

export const visibleMarketplaceEditorTabs = (
  capabilities: Record<MarketplaceAuthoringFeature, MarketplaceAuthoringCapability>,
): MarketplaceEditorTab[] => marketplaceEditorTabs.filter(
  tab => capabilities[tab] !== 'unsupported',
);

export const getMarketplaceEditorTabLabelKey = (
  targetClient: MarketplaceTargetClient,
  tab: MarketplaceEditorTab,
): string => {
  if (targetClient === 'claude-code' && tab === 'agentsMd') {
    return 'marketplace.editor.tabs.claudeMd';
  }
  if (tab === 'agents') {
    return 'marketplace.editor.tabs.subagents';
  }
  if (tab === 'commands') {
    return 'marketplace.editor.tabs.slashCommand';
  }
  return `marketplace.editor.tabs.${tab}`;
};

export const countMarketplaceFileNodes = (nodes: FileTreeNode[]): number => (
  nodes.reduce((count, node) => (
    count + (node.type === 'file' ? 1 : 0) + (node.children ? countMarketplaceFileNodes(node.children) : 0)
  ), 0)
);

export const getMarketplacePackageRoot = (targetClient: MarketplaceTargetClient, packageId: string): string => (
  `${targetClient}/plugins/${packageId}`
);
