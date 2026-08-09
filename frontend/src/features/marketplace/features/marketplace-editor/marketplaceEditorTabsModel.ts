import type { MarketplaceProvider } from '@/features/marketplace/model/marketplaceTypes';
import type { FileTreeNode } from '@/shared/components/file-workbench';

export const marketplaceEditorTabs = ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'skills', 'files'] as const;
export type MarketplaceEditorTab = typeof marketplaceEditorTabs[number];

export const providerEditorTabs: Record<MarketplaceProvider, MarketplaceEditorTab[]> = {
  'claude-code': ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'skills', 'files'],
  codex: ['basic', 'agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'skills', 'files'],
};

export const getMarketplaceEditorTabLabelKey = (
  provider: MarketplaceProvider,
  tab: MarketplaceEditorTab,
): string => {
  if (provider === 'claude-code' && tab === 'agentsMd') {
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

export const getMarketplacePackageRoot = (provider: MarketplaceProvider, packageId: string): string => (
  `${provider}/plugins/${packageId}`
);
