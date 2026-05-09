import type { FileTreeNode } from '@/shared/components/file-workbench';
import { sortTreeNodes } from '@/shared/components/file-workbench';
import type { MarketplacePackageFile, MarketplaceProvider } from '@/shared/types/marketplace';

export type MarketplaceFileTreeScope = 'plugin' | 'extension';

export interface MarketplaceFileTreeOptions {
  rootPath?: string;
  scope?: MarketplaceFileTreeScope;
}

export interface MarketplacePackageFileTreeOptions {
  provider: MarketplaceProvider;
  packageRoot: string;
  displayName: string;
  packageFiles: MarketplacePackageFile[];
}

export const marketplaceJoinPath = (parentPath: string | null | undefined, name: string): string => (
  parentPath
    ? `${parentPath.replace(/\/$/, '')}/${name.replace(/^\//, '')}`
    : name.replace(/^\//, '')
);

const getMarketplacePackageScope = (provider: MarketplaceProvider): MarketplaceFileTreeScope => (
  provider === 'gemini' ? 'extension' : 'plugin'
);

const getFileExtension = (name: string): string | undefined => {
  const extension = name.split('.').pop();
  return extension && extension !== name ? extension : extension;
};

export const marketplacePackageFilesToFileTreeNodes = (
  files: MarketplacePackageFile[],
  options: MarketplaceFileTreeOptions = {},
): FileTreeNode[] => {
  const rootPath = options.rootPath?.replace(/\/$/, '');
  const scope = options.scope;
  const root: FileTreeNode | null = rootPath
    ? {
        id: rootPath,
        name: rootPath.split('/').filter(Boolean).at(-1) ?? rootPath,
        path: rootPath,
        type: 'directory',
        scope,
        children: [],
      }
    : null;
  const roots: FileTreeNode[] = root ? (root.children ?? []) : [];
  const directories = new Map<string, FileTreeNode>(root ? [[rootPath, root]] : []);
  const filePaths = new Set<string>();

  const ensureDirectory = (path: string, name: string, parentChildren: FileTreeNode[]) => {
    const existing = directories.get(path);
    if (existing) return existing;

    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: 'directory',
      scope,
      children: [],
    };
    directories.set(path, node);
    parentChildren.push(node);
    return node;
  };

  files.forEach(file => {
    const parts = file.path.split('/').filter(Boolean);
    if (parts.length === 0) return;

    let currentPath = rootPath ?? '';
    let parentChildren = roots;

    parts.slice(0, -1).forEach(part => {
      currentPath = marketplaceJoinPath(currentPath || null, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1);
    if (!fileName) return;

    const path = marketplaceJoinPath(currentPath || null, fileName);
    if (filePaths.has(path)) return;
    filePaths.add(path);

    parentChildren.push({
      id: path,
      name: fileName,
      path,
      type: 'file',
      extension: getFileExtension(fileName),
      scope,
      size: file.size,
      metadata: {
        content: file.content,
        binary: file.binary,
        mimeType: file.mimeType,
      },
    });
  });

  return sortTreeNodes(roots);
};

export const createMarketplacePackageFileTree = ({
  provider,
  packageRoot,
  displayName,
  packageFiles,
}: MarketplacePackageFileTreeOptions): FileTreeNode[] => {
  const rootPath = `/${packageRoot}`;
  const scope = getMarketplacePackageScope(provider);

  if (packageFiles.length > 0) {
    return [{
      id: rootPath,
      name: packageRoot.split('/').at(-1) ?? packageRoot,
      path: rootPath,
      type: 'directory',
      scope,
      children: marketplacePackageFilesToFileTreeNodes(packageFiles, { rootPath, scope }),
    }];
  }

  const packageName = packageRoot.split('/').at(-1) ?? packageRoot;
  const manifestPath = provider === 'gemini'
    ? `${rootPath}/gemini-extension.json`
    : `${rootPath}/${provider === 'codex' ? '.codex-plugin' : '.claude-plugin'}/plugin.json`;
  const manifestDirectory = provider === 'gemini' ? null : {
    id: manifestPath.split('/').slice(0, -1).join('/'),
    name: provider === 'codex' ? '.codex-plugin' : '.claude-plugin',
    path: manifestPath.split('/').slice(0, -1).join('/'),
    type: 'directory' as const,
    scope,
    children: [
      {
        id: manifestPath,
        name: 'plugin.json',
        path: manifestPath,
        type: 'file' as const,
        extension: 'json',
        scope,
        size: 128,
        metadata: {
          content: `{\n  "id": "${packageName}",\n  "name": "${displayName}",\n  "version": "0.1.0"\n}`,
        },
      },
    ],
  };
  const defaultScope = provider === 'gemini' ? 'extension' : 'plugin';

  return [
    {
      id: rootPath,
      name: packageName,
      path: rootPath,
      type: 'directory',
      scope,
      children: [
        ...(manifestDirectory ? [manifestDirectory] : [
          {
            id: manifestPath,
            name: 'gemini-extension.json',
            path: manifestPath,
            type: 'file' as const,
            extension: 'json',
            scope,
            size: 128,
            metadata: {
              content: `{\n  "name": "${packageName}",\n  "version": "0.1.0",\n  "contextFileName": "GEMINI.md"\n}`,
            },
          },
        ]),
        {
          id: `${rootPath}/README.md`,
          name: 'README.md',
          path: `${rootPath}/README.md`,
          type: 'file',
          extension: 'md',
          scope: defaultScope,
          size: 96,
          metadata: {
            content: `# ${displayName}\n\nPackage README for ${packageRoot}.`,
          },
        },
        {
          id: `${rootPath}/assets`,
          name: 'assets',
          path: `${rootPath}/assets`,
          type: 'directory',
          scope: defaultScope,
          children: [
            {
              id: `${rootPath}/assets/icon.svg`,
              name: 'icon.svg',
              path: `${rootPath}/assets/icon.svg`,
              type: 'file',
              extension: 'svg',
              scope: defaultScope,
              size: 96,
              metadata: {
                content: '<svg viewBox="0 0 24 24" role="img"><path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z" /></svg>',
              },
            },
            {
              id: `${rootPath}/assets/logo.png`,
              name: 'logo.png',
              path: `${rootPath}/assets/logo.png`,
              type: 'file',
              extension: 'png',
              scope: defaultScope,
              size: 68,
              metadata: {
                binary: true,
                mimeType: 'image/png',
                previewDataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
              },
            },
          ],
        },
        {
          id: `${rootPath}/scripts`,
          name: 'scripts',
          path: `${rootPath}/scripts`,
          type: 'directory',
          scope: defaultScope,
          children: [
            {
              id: `${rootPath}/scripts/install-check.sh`,
              name: 'install-check.sh',
              path: `${rootPath}/scripts/install-check.sh`,
              type: 'file',
              extension: 'sh',
              scope: defaultScope,
              size: 64,
              metadata: {
                content: '#!/usr/bin/env bash\nset -euo pipefail\n\necho "Checking package prerequisites"\n',
              },
            },
          ],
        },
        {
          id: `${rootPath}/LICENSE`,
          name: 'LICENSE',
          path: `${rootPath}/LICENSE`,
          type: 'file',
          extension: 'txt',
          scope: defaultScope,
          size: 32,
          metadata: {
            content: 'MIT License\n\nCopyright (c) 2026',
          },
        },
      ],
    },
  ];
};

export const marketplaceFileContentsFromTree = (nodes: FileTreeNode[]): Record<string, string> => {
  const contents: Record<string, string> = {};

  const walk = (items: FileTreeNode[]) => {
    items.forEach(node => {
      if (node.type === 'file' && typeof node.metadata?.content === 'string') {
        contents[node.path] = node.metadata.content;
      }
      if (node.children) {
        walk(node.children);
      }
    });
  };

  walk(nodes);
  return contents;
};

export const marketplacePackageFilesFromTree = (
  nodes: FileTreeNode[],
  packageRootPath: string,
  contents: Record<string, string>,
): MarketplacePackageFile[] => {
  const files: MarketplacePackageFile[] = [];
  const rootPrefix = `${packageRootPath.replace(/\/$/, '')}/`;

  const walk = (items: FileTreeNode[]) => {
    items.forEach(node => {
      if (node.type === 'file') {
        const relativePath = node.path.startsWith(rootPrefix)
          ? node.path.slice(rootPrefix.length)
          : node.path.replace(/^\//, '');
        const content = contents[node.path] ?? (typeof node.metadata?.content === 'string' ? node.metadata.content : '');
        files.push({
          path: relativePath,
          content,
          binary: Boolean(node.metadata?.binary),
          mimeType: typeof node.metadata?.mimeType === 'string' ? node.metadata.mimeType : undefined,
          size: typeof node.size === 'number' ? node.size : content.length,
        });
      }
      if (node.children) {
        walk(node.children);
      }
    });
  };

  walk(nodes);
  return files;
};

export const marketplaceFeaturePackageFilesFromTree = (
  nodes: FileTreeNode[],
  basePath: string,
  contents: Record<string, string>,
): MarketplacePackageFile[] => (
  marketplacePackageFilesFromTree(nodes, `/${basePath}`, contents)
    .map(file => ({
      ...file,
      path: file.path.startsWith(`${basePath}/`) ? file.path : `${basePath}/${file.path}`,
    }))
);

export const marketplaceFindFirstFilePath = (nodes: FileTreeNode[]): string | undefined => {
  for (const node of nodes) {
    if (node.type === 'file') return node.path;
    const childPath = node.children ? marketplaceFindFirstFilePath(node.children) : undefined;
    if (childPath) return childPath;
  }
  return undefined;
};

export const marketplaceRenameNode = (
  nodes: FileTreeNode[],
  oldPath: string,
  nextPath: string,
  nextName: string,
): FileTreeNode[] => (
  nodes.map(node => {
    if (node.path === oldPath || node.path.startsWith(`${oldPath}/`)) {
      const renamedPath = node.path.replace(oldPath, nextPath);
      return {
        ...node,
        id: renamedPath,
        path: renamedPath,
        name: node.path === oldPath ? nextName : node.name,
        children: node.children ? marketplaceRenameNode(node.children, oldPath, nextPath, nextName) : undefined,
      };
    }
    return {
      ...node,
      children: node.children ? marketplaceRenameNode(node.children, oldPath, nextPath, nextName) : undefined,
    };
  })
);

export const marketplaceRenameContentPaths = (
  contents: Record<string, string>,
  oldPath: string,
  nextPath: string,
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents).map(([path, content]) => [
    path === oldPath || path.startsWith(`${oldPath}/`) ? path.replace(oldPath, nextPath) : path,
    content,
  ]))
);

export const marketplaceDeleteContentPaths = (
  contents: Record<string, string>,
  paths: string[],
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents).filter(([path]) => (
    !paths.some(deletedPath => path === deletedPath || path.startsWith(`${deletedPath}/`))
  )))
);

export const marketplaceFileTreeAdapter = {
  toFileTreeNodes: marketplacePackageFilesToFileTreeNodes,
  createPackageFileTree: createMarketplacePackageFileTree,
  fromFileTreeNodes: marketplacePackageFilesFromTree,
  featurePackageFilesFromTree: marketplaceFeaturePackageFilesFromTree,
  fileContentsFromTree: marketplaceFileContentsFromTree,
  findFirstFilePath: marketplaceFindFirstFilePath,
  renameNode: marketplaceRenameNode,
  renameContentPaths: marketplaceRenameContentPaths,
  deleteContentPaths: marketplaceDeleteContentPaths,
};
