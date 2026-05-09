import type {
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileDownloadOptions,
  FileOperationRequest,
  FileOperationResponse,
  FileTreeDataAdapter,
  FileTreeNode,
  FileUploadOptions,
  FileUploadResult,
} from '@/shared/components/file-workbench';
import type { MarketplacePackageFile, MarketplaceProvider } from '@/shared/types/marketplace';
import {
  createMarketplacePackageFileTree,
  marketplaceJoinPath,
} from './marketplaceFileTreeAdapter';

export interface MarketplaceFileWorkbenchAdapterContext {
  provider: MarketplaceProvider;
  packageId: string;
  packageRoot: string;
  displayName: string;
  getPackageFiles: () => MarketplacePackageFile[];
  onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
  readOnly?: boolean;
}

export interface MarketplaceFileWorkbenchAdapter extends FileTreeDataAdapter {
  read: (path: string) => Promise<string>;
  write: (path: string, content: string) => Promise<void>;
  rename: (oldPath: string, newPath: string) => Promise<FileOperationResponse>;
  isReadOnly: (node: FileTreeNode) => boolean;
}

const notSupported = (key: string): never => {
  throw new Error(key);
};

const normalizePath = (path: string) => path.replace(/^\/+/, '').replace(/\/+$/, '');

const toRelativePackagePath = (path: string, packageRoot: string): string => {
  const normalizedPath = normalizePath(path);
  const normalizedRoot = normalizePath(packageRoot);
  return normalizedPath === normalizedRoot
    ? ''
    : normalizedPath.startsWith(`${normalizedRoot}/`)
      ? normalizedPath.slice(normalizedRoot.length + 1)
      : normalizedPath;
};

const getParentPath = (path: string): string | null => {
  const parts = path.split('/').filter(Boolean);
  if (parts.length <= 1) return null;
  return parts.slice(0, -1).join('/');
};

const getFileName = (path: string): string => path.split('/').filter(Boolean).at(-1) ?? path;

const createResponse = (): FileOperationResponse => ({ success: true });

const toPackageFile = (path: string, content = ''): MarketplacePackageFile => ({
  path,
  content,
  binary: false,
  mimeType: 'text/plain',
  size: content.length,
});

const readFileText = (file: File): Promise<string> => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
  reader.onerror = () => reject(new Error('marketplace.fileTree.error.upload'));
  reader.readAsText(file);
});

export const createMarketplaceFileWorkbenchAdapter = (
  context: MarketplaceFileWorkbenchAdapterContext,
): MarketplaceFileWorkbenchAdapter => {
  const getFiles = () => context.getPackageFiles();
  const setFiles = (files: MarketplacePackageFile[]) => context.onPackageFilesChange(files);
  const packageRootPath = `/${context.packageRoot}`;

  const getRelativePath = (path: string) => toRelativePackagePath(path, context.packageRoot);

  const adapter: MarketplaceFileWorkbenchAdapter = {
    async getTree() {
      return createMarketplacePackageFileTree({
        provider: context.provider,
        packageRoot: context.packageRoot,
        displayName: context.displayName,
        packageFiles: getFiles(),
      });
    },

    async getChildren(path) {
      const tree = await adapter.getTree();
      const find = (nodes: FileTreeNode[]): FileTreeNode | null => {
        for (const node of nodes) {
          if (node.path === path) return node;
          const child = node.children ? find(node.children) : null;
          if (child) return child;
        }
        return null;
      };
      return find(tree)?.children ?? [];
    },

    async getContent(path) {
      const relativePath = getRelativePath(path);
      const file = getFiles().find(item => item.path === relativePath);
      if (!file) {
        throw new Error('marketplace.fileTree.error.read');
      }
      if (file.binary) {
        throw new Error('marketplace.fileTree.error.binaryRead');
      }
      return file.content;
    },

    async create(request: FileOperationRequest) {
      if (context.readOnly) {
        throw new Error('marketplace.fileTree.error.readOnly');
      }
      if (request.isDirectory) {
        return createResponse();
      }

      const relativePath = getRelativePath(request.path);
      const files = getFiles();
      if (!relativePath || files.some(file => file.path === relativePath)) {
        throw new Error('marketplace.fileTree.error.create');
      }

      setFiles([...files, toPackageFile(relativePath, request.content ?? '')]);
      return createResponse();
    },

    async update(path, content) {
      await adapter.write(path, content);
      return createResponse();
    },

    async delete(path) {
      if (context.readOnly) {
        throw new Error('marketplace.fileTree.error.readOnly');
      }
      const relativePath = getRelativePath(path);
      const files = getFiles();
      const nextFiles = files.filter(file => file.path !== relativePath && !file.path.startsWith(`${relativePath}/`));
      if (nextFiles.length === files.length) {
        throw new Error('marketplace.fileTree.error.delete');
      }
      setFiles(nextFiles);
      return createResponse();
    },

    async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
      if (context.readOnly) {
        throw new Error('marketplace.fileTree.error.readOnly');
      }

      const deleted: string[] = [];
      const failed: Array<{ path: string; error: string }> = [];
      let files = getFiles();

      request.paths.forEach(path => {
        const relativePath = getRelativePath(path);
        const nextFiles = files.filter(file => file.path !== relativePath && !file.path.startsWith(`${relativePath}/`));
        if (nextFiles.length === files.length) {
          failed.push({ path, error: 'marketplace.fileTree.error.delete' });
        } else {
          deleted.push(path);
          files = nextFiles;
        }
      });

      setFiles(files);
      return {
        success: failed.length === 0,
        deleted,
        failed,
        total: request.paths.length,
        successCount: deleted.length,
        failedCount: failed.length,
      };
    },

    async move(sourcePath, targetPath) {
      return adapter.rename(sourcePath, targetPath);
    },

    async upload(options: FileUploadOptions): Promise<FileUploadResult[]> {
      if (context.readOnly) {
        throw new Error('marketplace.fileTree.error.readOnly');
      }

      const uploaded = await Promise.all(options.files.map(async file => {
        const targetPath = marketplaceJoinPath(options.targetPath || packageRootPath, file.name);
        const relativePath = getRelativePath(targetPath);
        const content = await readFileText(file);
        return { file, relativePath, content, targetPath };
      }));

      const filesByPath = new Map(getFiles().map(file => [file.path, file]));
      uploaded.forEach(({ file, relativePath, content }) => {
        filesByPath.set(relativePath, {
          path: relativePath,
          content,
          binary: false,
          mimeType: file.type || 'text/plain',
          size: file.size,
        });
      });
      setFiles(Array.from(filesByPath.values()));

      return uploaded.map(({ file, targetPath }) => ({
        fileName: file.name,
        path: targetPath,
        success: true,
      }));
    },

    async download(_options: FileDownloadOptions): Promise<void> {
      notSupported('marketplace.fileTree.error.download');
    },

    async read(path) {
      return adapter.getContent(path);
    },

    async write(path, content) {
      if (context.readOnly) {
        throw new Error('marketplace.fileTree.error.readOnly');
      }
      const relativePath = getRelativePath(path);
      const files = getFiles();
      let didUpdate = false;
      const nextFiles = files.map(file => {
        if (file.path !== relativePath) return file;
        didUpdate = true;
        return {
          ...file,
          content,
          binary: false,
          size: content.length,
        };
      });
      if (!didUpdate) {
        throw new Error('marketplace.fileTree.error.write');
      }
      setFiles(nextFiles);
    },

    async rename(oldPath, newPath) {
      if (context.readOnly) {
        throw new Error('marketplace.fileTree.error.readOnly');
      }
      const oldRelativePath = getRelativePath(oldPath);
      const newRelativePath = getRelativePath(newPath);
      if (!oldRelativePath || !newRelativePath || getParentPath(oldRelativePath) !== getParentPath(newRelativePath)) {
        throw new Error('marketplace.fileTree.error.rename');
      }

      let didRename = false;
      const nextFiles = getFiles().map(file => {
        if (file.path !== oldRelativePath && !file.path.startsWith(`${oldRelativePath}/`)) {
          return file;
        }
        didRename = true;
        return {
          ...file,
          path: file.path.replace(oldRelativePath, newRelativePath),
        };
      });

      if (!didRename || getFileName(newRelativePath).length === 0) {
        throw new Error('marketplace.fileTree.error.rename');
      }

      setFiles(nextFiles);
      return createResponse();
    },

    isReadOnly(node) {
      return Boolean(context.readOnly || node.writable === false);
    },
  };

  return adapter;
};
