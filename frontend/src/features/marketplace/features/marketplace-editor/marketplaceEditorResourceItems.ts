export interface MarketplaceEditorResourceItem {
  id: string;
  name?: string;
  titleKey?: string;
  descriptionKey?: string;
  path: string;
  content: string;
  title?: string;
  description?: string;
  badge?: string;
  code?: string;
  data?: Record<string, unknown>;
  meta?: Array<{ labelKey: string; value: string }>;
  ownerFilePath?: string;
  baseEntryFingerprint?: string;
}

export type MarketplaceResourceFormat = 'markdown' | 'toml';

export type MarketplaceMarkdownEditorTab = 'agents' | 'commands' | 'outputStyle';

export const marketplaceEditorItemTitle = (item: MarketplaceEditorResourceItem, t: (key: string) => string): string => (
  item.title ?? item.name ?? (item.titleKey ? t(item.titleKey) : item.id)
);

export const marketplaceEditorItemDescription = (item: MarketplaceEditorResourceItem, t: (key: string) => string): string => (
  item.description ?? (item.descriptionKey ? t(item.descriptionKey) : '')
);

export const getMarketplaceItemFileName = (item: MarketplaceEditorResourceItem): string => (
  item.path.split('/').pop() || item.id
);
