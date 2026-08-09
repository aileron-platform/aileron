import type {
  FileTreeContextMenuConfig,
  FileTreeNode,
} from '@/shared/components/file-workbench';
import type { MarketplaceTreeEntry } from '../../api/marketplaceApi';

export type MarketplaceFileResourceType = 'skills' | 'files';

export interface ResourceEntry extends MarketplaceTreeEntry {
  isDirectory: boolean;
}

const MANAGED_FILE_ROOTS = new Set([
  'commands',
  'agents',
  'output-styles',
  'policies',
  'skills',
  '.codex-plugin',
  '.claude-plugin',
  '.mcp.json',
  'mcp.json',
  'hooks',
  'AGENTS.md',
  'CLAUDE.md',
]);

export const isManagedFileRootPath = (path: string): boolean => {
  const normalized = path.replace(/^\/+/, '');
  const firstPart = normalized.split('/').filter(Boolean)[0] ?? normalized;
  return MANAGED_FILE_ROOTS.has(firstPart) || MANAGED_FILE_ROOTS.has(normalized);
};

export const toResourceEntries = (
  resourceType: MarketplaceFileResourceType,
  entries: MarketplaceTreeEntry[],
): ResourceEntry[] => {
  // The files tab mirrors the package detail view: every file in the package,
  // including managed dotfiles. The skills tab stays scoped to skills/.
  const filtered = resourceType === 'files'
    ? entries
    : entries.filter((entry) => entry.path === 'skills' || entry.path.startsWith('skills/'));

  return filtered.map((entry) => ({
    ...entry,
    isDirectory: entry.type === 'directory',
  }));
};

export const sortEntries = (entries: ResourceEntry[]): ResourceEntry[] => (
  [...entries].sort((left, right) => {
    if (left.isDirectory !== right.isDirectory) {
      return left.isDirectory ? -1 : 1;
    }
    return left.path.localeCompare(right.path);
  })
);

export const ensureScopedPath = (
  resourceType: MarketplaceFileResourceType,
  input: string,
): string => {
  const normalized = input.trim().replace(/^\/+/, '').replace(/\/+$/, '');
  if (!normalized) {
    return '';
  }
  if (resourceType === 'skills' && !normalized.startsWith('skills/')) {
    return `skills/${normalized}`;
  }
  return normalized;
};

export const buildChildPath = (
  resourceType: MarketplaceFileResourceType,
  parentPath: string,
  name: string,
): string => ensureScopedPath(resourceType, [parentPath, name].filter(Boolean).join('/'));

export const getContextParentPath = (node: FileTreeNode | null): string => {
  if (!node) {
    return '';
  }
  if (node.type === 'directory') {
    return node.path;
  }
  const parts = node.path.split('/').filter(Boolean);
  parts.pop();
  return parts.join('/');
};

export const renamePath = (path: string, nextName: string): string => {
  const parts = path.split('/').filter(Boolean);
  parts[parts.length - 1] = nextName;
  return parts.join('/');
};

export const toFileTreeNode = (
  entry: ResourceEntry,
  resourceType: MarketplaceFileResourceType,
): FileTreeNode => ({
  id: entry.path,
  path: entry.path,
  name: entry.name,
  type: entry.isDirectory ? 'directory' : 'file',
  children: entry.isDirectory ? [] : undefined,
  extension: entry.isDirectory ? undefined : entry.name.split('.').pop(),
  writable: resourceType === 'files' ? !isManagedFileRootPath(entry.path) : true,
});

export const marketplaceContextMenuFeatures = (
  resourceType: MarketplaceFileResourceType,
  node: FileTreeNode | null,
): NonNullable<FileTreeContextMenuConfig['features']> => {
  const isManaged = resourceType === 'files' && Boolean(node?.path) && isManagedFileRootPath(node.path);
  return {
    upload: !isManaged,
    createFile: !isManaged,
    createFolder: !isManaged,
    extractArchive: !isManaged,
    copy: !isManaged,
    copyPath: true,
    paste: resourceType === 'files' && !isManaged,
    rename: !isManaged,
    delete: !isManaged,
  };
};
