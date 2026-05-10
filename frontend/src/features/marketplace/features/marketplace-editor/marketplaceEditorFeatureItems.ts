import type { MarketplaceFeatureContentItem, MarketplacePackageDetail, MarketplacePackageFile } from '@/shared/types/marketplace';

import { type MarketplaceEditorResourceItem, type MarketplaceMarkdownEditorTab } from './marketplaceEditorResourceItems';
import { stringifyMarketplaceJson } from './marketplaceEditorRequiredDraft';

export type MarketplaceEditorFeatureTab = 'skills' | 'agents' | 'commands' | 'mcp' | 'hooks' | 'outputStyle' | 'policies' | 'files';

export type MarketplaceEditorFeatureItems = Record<MarketplaceEditorFeatureTab, MarketplaceEditorResourceItem[]>;

export const emptyMarketplaceFeatureItems = (): MarketplaceEditorFeatureItems => ({
  skills: [],
  agents: [],
  commands: [],
  mcp: [],
  hooks: [],
  outputStyle: [],
  policies: [],
  files: [],
});

const marketplaceFeatureItemFromDetail = (
  item: MarketplaceFeatureContentItem,
  fallbackPath: string,
): MarketplaceEditorResourceItem => {
  const path = item.path ?? fallbackPath;
  const extension = path.split('.').pop() || 'txt';
  return {
    id: item.id || path || item.name,
    title: item.name,
    description: item.description ?? '',
    path,
    content: item.content ?? stringifyMarketplaceJson(item.data ?? {}),
    badge: extension,
  };
};

export const marketplacePackageFileFromResourceItem = (item: MarketplaceEditorResourceItem): MarketplacePackageFile => {
  const extension = item.path.split('.').pop()?.toLowerCase() ?? '';
  const mimeType = extension === 'json'
    ? 'application/json'
    : extension === 'toml'
      ? 'application/toml'
      : 'text/markdown';

  return {
    path: item.path,
    content: item.content,
    binary: false,
    mimeType,
    size: item.content.length,
  };
};

export const marketplaceApplyResourceItemsToPackageFiles = (
  files: MarketplacePackageFile[],
  items: MarketplaceEditorResourceItem[],
  managedPrefixes: string[],
): MarketplacePackageFile[] => {
  const itemPaths = new Set(items.map(item => item.path));
  const nextFiles = files.filter(file => (
    !itemPaths.has(file.path) &&
    !managedPrefixes.some(prefix => file.path === prefix.slice(0, -1) || file.path.startsWith(prefix))
  ));

  return [
    ...nextFiles,
    ...items.map(marketplacePackageFileFromResourceItem),
  ].sort((first, second) => first.path.localeCompare(second.path));
};

export const marketplaceMarkdownManagedPrefixes: Record<MarketplaceMarkdownEditorTab, string[]> = {
  agents: ['agents/'],
  commands: ['commands/'],
  outputStyle: ['output-styles/'],
  policies: ['policies/'],
};

export const marketplaceApplyPackageFiles = (
  files: MarketplacePackageFile[],
  packageFiles: MarketplacePackageFile[],
  managedPrefixes: string[],
): MarketplacePackageFile[] => {
  const packageFilePaths = new Set(packageFiles.map(file => file.path));
  const nextFiles = files.filter(file => (
    !packageFilePaths.has(file.path) &&
    !managedPrefixes.some(prefix => file.path === prefix.slice(0, -1) || file.path.startsWith(prefix))
  ));

  return [
    ...nextFiles,
    ...packageFiles,
  ].sort((first, second) => first.path.localeCompare(second.path));
};

export const marketplaceTextPackageFile = (path: string, content: string, mimeType = 'text/markdown'): MarketplacePackageFile => ({
  path,
  content,
  binary: false,
  mimeType,
  size: content.length,
});

export const marketplaceFeatureItemsFromDetail = (detail: MarketplacePackageDetail | null): MarketplaceEditorFeatureItems | null => {
  if (!detail) return null;
  const content = detail.featureContent;
  return {
    ...emptyMarketplaceFeatureItems(),
    skills: content.skills.map(item => marketplaceFeatureItemFromDetail(item, `skills/${item.id}/SKILL.md`)),
    agents: content.agents.map(item => marketplaceFeatureItemFromDetail(item, `agents/${item.id}.md`)),
    commands: content.commands.map(item => marketplaceFeatureItemFromDetail(item, `commands/${item.id}.md`)),
    outputStyle: content.outputStyles.map(item => marketplaceFeatureItemFromDetail(item, `output-styles/${item.id}.md`)),
    mcp: content.mcpServers.map(item => marketplaceFeatureItemFromDetail(item, `mcp/${item.id}.json`)),
    hooks: content.hooks.map(item => marketplaceFeatureItemFromDetail(item, `hooks/${item.id}.json`)),
    policies: (content.policies ?? []).map(item => marketplaceFeatureItemFromDetail(item, `policies/${item.id}.toml`)),
  };
};
