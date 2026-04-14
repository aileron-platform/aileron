import type { TemplateFileNode } from '@/shared/types/templates';

export interface TemplateFileEntry {
  path: string;
  content?: string;
}

interface DirectoryNode {
  name: string;
  path: string;
  children: Map<string, DirectoryNode | TemplateFileNode>;
}

const createDirectoryNode = (name: string, path: string): DirectoryNode => ({
  name,
  path,
  children: new Map(),
});

export const flattenFileTree = (nodes: TemplateFileNode[]): TemplateFileEntry[] => {
  const results: TemplateFileEntry[] = [];

  const traverse = (node: TemplateFileNode, currentPath: string) => {
    const nextPath = currentPath ? `${currentPath}/${node.name}` : node.name;
    if (node.type === 'file') {
      results.push({ path: nextPath, content: node.content });
    }
    if (node.type === 'directory' && node.children) {
      node.children.forEach(child => traverse(child, nextPath));
    }
  };

  nodes.forEach(node => traverse(node, ''));
  return results;
};

const buildTreeFromDirectory = (dir: DirectoryNode): TemplateFileNode[] => {
  const children: TemplateFileNode[] = [];
  dir.children.forEach(value => {
    if ('type' in value) {
      children.push(value as TemplateFileNode);
    } else {
      const directory = value as DirectoryNode;
      children.push({
        id: directory.path,
        name: directory.name,
        path: directory.path,
        type: 'directory',
        children: buildTreeFromDirectory(directory),
      });
    }
  });
  return children;
};

export const buildFileTreeFromEntries = (entries: TemplateFileEntry[]): TemplateFileNode[] => {
  const root = createDirectoryNode('', '');
  const sorted = [...entries].sort((a, b) => a.path.localeCompare(b.path));

  sorted.forEach(entry => {
    const trimmedPath = entry.path.replace(/^\/+/, '');
    if (!trimmedPath) {
      return;
    }
    const segments = trimmedPath.split('/');
    let current = root;

    segments.forEach((segment, index) => {
      const currentPath = segments.slice(0, index + 1).join('/');
      const isFile = index === segments.length - 1;

      if (isFile) {
        current.children.set(segment, {
          id: currentPath,
          name: segment,
          path: currentPath,
          type: 'file',
          content: entry.content ?? '',
        });
      } else {
        const existing = current.children.get(segment);
        if (existing && 'type' in existing) {
          // 如果原本是檔案，轉成目錄
          const directory = createDirectoryNode(segment, currentPath);
          current.children.set(segment, directory);
          current = directory;
        } else if (existing) {
          current = existing as DirectoryNode;
        } else {
          const directory = createDirectoryNode(segment, currentPath);
          current.children.set(segment, directory);
          current = directory;
        }
      }
    });
  });

  return buildTreeFromDirectory(root);
};
