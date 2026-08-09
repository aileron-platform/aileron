import type { FileTreeNode } from '@/shared/components/file-workbench';
import { ensureLeadingSlash } from './filePathModel';

export const getParentPath = (path: string): string => {
  if (!path || path === '/') {
    return '/';
  }
  const segments = path.split('/').filter(Boolean);
  segments.pop();
  if (segments.length === 0) {
    return '/';
  }
  return `/${segments.join('/')}`;
};

interface ResolveTargetDirectoryOptions {
  basePath?: string | null;
  flatNodes: FileTreeNode[];
}

export const resolveTargetDirectory = ({
  basePath,
  flatNodes,
}: ResolveTargetDirectoryOptions): string => {
  if (!basePath || basePath === '/' || basePath === '') {
    return '/';
  }
  const node = flatNodes.find((item) => item.path === basePath);
  if (node?.type === 'directory') {
    return node.path;
  }
  return getParentPath(basePath);
};

export const createPlaceholderNode = (
  path: string,
  type: 'file' | 'directory' = 'file',
): FileTreeNode => ({
  id: path,
  name: path.split('/').filter(Boolean).pop() ?? path,
  path,
  type,
});

interface GetRelatedPathsForDeleteOptions {
  paths: string[];
  flatNodes: FileTreeNode[];
}

export const getRelatedPathsForDelete = ({
  paths,
  flatNodes,
}: GetRelatedPathsForDeleteOptions): string[] => {
  const pathsToClose = new Set<string>();
  paths.forEach((item) => {
    const normalized = ensureLeadingSlash(item);
    pathsToClose.add(normalized);
    flatNodes.forEach((flatNode) => {
      if (flatNode.path.startsWith(`${normalized}/`)) {
        pathsToClose.add(flatNode.path);
      }
    });
  });
  return Array.from(pathsToClose);
};

export const getContextMenuTargetDirectory = (node?: FileTreeNode | null): string => (
  node?.type === 'directory' ? node.path : getParentPath(node?.path || '/')
);
