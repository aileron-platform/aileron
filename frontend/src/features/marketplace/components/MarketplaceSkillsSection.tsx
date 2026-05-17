import React from 'react';
import { unzip } from 'fflate';
import { FolderPlus, Plus, RefreshCw, Upload, Wand2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  flattenTree,
  sortTreeNodes,
  useFileTreeContextMenu,
  useFileTreeState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import {
  FileViewerWorkbench,
  useManagedDocumentWorkbenchTabs,
  type SkillsFileTreePersistenceAdapter,
} from '@/shared/components/file-workbench/viewer-entry';
import type { MarketplacePackageFile } from '@/shared/types/marketplace';
import { getMimeType, isTextFile } from '@/shared/utils/fileTypeUtils';
import { MarketplaceSectionSidebarShell } from './MarketplaceSectionSidebarShell';
import { type MarketplaceEditorResourceItem } from '../features/marketplace-editor/marketplaceEditorResourceItems';
import {
  marketplaceJoinPath,
  marketplaceFileContentsFromTree,
  marketplaceFeaturePackageFilesFromTree,
  marketplaceRenameNode,
} from '../adapters/marketplaceFileTreeAdapter';
import { getMarketplaceItemFileName } from '../features/marketplace-editor/marketplaceEditorResourceItems';

type MarketplaceFileDialogState =
  | { type: 'create-file' | 'create-folder'; parentPath: string | null }
  | { type: 'rename' | 'delete' | 'batch-delete'; node: FileTreeNode }
  | null;

interface ZipFileEntry {
  path: string;
  content: string;
  size: number;
  binary?: boolean;
  mimeType?: string;
}

const isZipFileName = (name: string): boolean => name.toLowerCase().endsWith('.zip');

const getArchiveDirectoryName = (name: string): string => {
  const fileName = name.split('/').filter(Boolean).at(-1) ?? name;
  return fileName.replace(/\.zip$/i, '') || fileName;
};

const normalizeZipEntryPaths = (entries: ZipFileEntry[], archiveName: string): ZipFileEntry[] => {
  const hasRootLevelFile = entries.some(entry => entry.path.split('/').filter(Boolean).length === 1);
  if (!hasRootLevelFile) {
    return entries;
  }

  const archiveDirectory = getArchiveDirectoryName(archiveName);
  return entries.map(entry => ({
    ...entry,
    path: marketplaceJoinPath(archiveDirectory, entry.path),
  }));
};

const uint8ArrayToBase64 = (bytes: Uint8Array): string => {
  let binary = '';
  bytes.forEach(byte => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
};

const arrayBufferToBase64 = (buffer: ArrayBuffer): string => uint8ArrayToBase64(new Uint8Array(buffer));

const base64ToUint8Array = (content: string): Uint8Array => {
  const binary = atob(content);
  return new Uint8Array(Array.from(binary, character => character.charCodeAt(0)));
};

const isIgnoredZipEntry = (zipPath: string): boolean => {
  const parts = zipPath.split('/').filter(Boolean);
  const fileName = parts.at(-1) ?? '';
  return zipPath.endsWith('/')
    || parts[0] === '__MACOSX'
    || fileName.startsWith('._')
    || fileName === '.DS_Store';
};

const readFileText = (file: File): Promise<string> => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = (event) => resolve(typeof event.target?.result === 'string' ? event.target.result : '');
  reader.onerror = () => reject(new Error('marketplace.fileTree.error.upload'));
  reader.readAsText(file);
});

const readFileBase64 = (file: File): Promise<string> => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = (event) => {
    if (!(event.target?.result instanceof ArrayBuffer)) {
      reject(new Error('marketplace.fileTree.error.upload'));
      return;
    }
    resolve(arrayBufferToBase64(event.target.result));
  };
  reader.onerror = () => reject(new Error('marketplace.fileTree.error.upload'));
  reader.readAsArrayBuffer(file);
});

const insertNodeIntoTree = (
  nodes: FileTreeNode[],
  parentPath: string | null,
  node: FileTreeNode,
): FileTreeNode[] => {
  if (!parentPath) return sortTreeNodes([...nodes, node]);
  return nodes.map(n => {
    if (n.path === parentPath) return { ...n, children: sortTreeNodes([...(n.children ?? []), node]) };
    if (n.children) return { ...n, children: insertNodeIntoTree(n.children, parentPath, node) };
    return n;
  });
};

const addFilesToTree = (
  existingNodes: FileTreeNode[],
  files: ZipFileEntry[],
): { nodes: FileTreeNode[]; resolved: Array<ZipFileEntry & { node: FileTreeNode }> } => {
  const allPaths = new Set(flattenTree(existingNodes).map(n => n.path));
  let result = [...existingNodes];
  const resolved: Array<ZipFileEntry & { node: FileTreeNode }> = [];

  files.forEach(({ path, content, size, binary, mimeType }) => {
    const parts = path.split('/').filter(Boolean);
    for (let depth = 0; depth < parts.length - 1; depth += 1) {
      const dirPath = parts.slice(0, depth + 1).join('/');
      if (!allPaths.has(dirPath)) {
        const parentDir = depth === 0 ? null : parts.slice(0, depth).join('/');
        result = insertNodeIntoTree(result, parentDir, {
          id: dirPath, name: parts[depth], path: dirPath, type: 'directory', children: [],
        });
        allPaths.add(dirPath);
      }
    }
    const baseName = parts.at(-1) ?? path;
    const parentDir = parts.length > 1 ? parts.slice(0, -1).join('/') : null;
    let resolvedName = baseName;
    let resolvedPath = parentDir ? `${parentDir}/${resolvedName}` : resolvedName;
    let copyIndex = 1;
    while (allPaths.has(resolvedPath)) {
      const nameParts = baseName.split('.');
      if (nameParts.length > 1) {
        const ext = nameParts.pop();
        resolvedName = `${nameParts.join('.')}-${copyIndex}.${ext}`;
      } else {
        resolvedName = `${baseName}-${copyIndex}`;
      }
      resolvedPath = parentDir ? `${parentDir}/${resolvedName}` : resolvedName;
      copyIndex += 1;
    }
    const fileNode: FileTreeNode = {
      id: resolvedPath, name: resolvedName, path: resolvedPath, type: 'file',
      extension: resolvedName.split('.').pop(),
      size,
      metadata: {
        content,
        binary: Boolean(binary),
        mimeType,
      },
    };
    result = insertNodeIntoTree(result, parentDir, fileNode);
    allPaths.add(resolvedPath);
    resolved.push({ path: resolvedPath, content, size, binary, mimeType, node: fileNode });
  });

  return { nodes: result, resolved };
};

const extractTextFilesFromZip = (data: Uint8Array, archiveName: string): Promise<ZipFileEntry[]> => new Promise(resolve => {
  unzip(data, (err, unzipped) => {
    if (err) {
      resolve([]);
      return;
    }

    const entries = Object.entries(unzipped)
      .filter(([zipPath]) => !isIgnoredZipEntry(zipPath))
      .map(([zipPath, entryData]) => {
        const binary = !isTextFile(zipPath);
        return {
          path: zipPath,
          content: binary ? uint8ArrayToBase64(entryData) : new TextDecoder().decode(entryData),
          size: entryData.length,
          binary,
          mimeType: getMimeType(zipPath),
        };
      });
    resolve(normalizeZipEntryPaths(entries, archiveName));
  });
});

const marketplaceParentPath = (path: string): string | null => {
  const normalized = path.replace(/\/$/, '');
  const index = normalized.lastIndexOf('/');
  if (index <= 0) return null;
  return normalized.slice(0, index);
};

const marketplaceFeatureItemsToFileTree = (
  items: MarketplaceEditorResourceItem[],
  basePath: string,
): FileTreeNode[] => {
  const roots: FileTreeNode[] = [];
  const directories = new Map<string, FileTreeNode>();

  const ensureDirectory = (path: string, name: string, parent: FileTreeNode[] | undefined) => {
    const existing = directories.get(path);
    if (existing) return existing;
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: 'directory',
      children: [],
    };
    directories.set(path, node);
    (parent ?? roots).push(node);
    return node;
  };

  items.forEach(item => {
    const relativePath = item.path.replace(new RegExp(`^${basePath}/?`), '');
    const parts = relativePath.split('/').filter(Boolean);
    let parentChildren = roots;
    let currentPath = '';

    parts.slice(0, -1).forEach(part => {
      currentPath = marketplaceJoinPath(currentPath || null, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1) ?? getMarketplaceItemFileName(item);
    const filePath = marketplaceJoinPath(currentPath || null, fileName);
    parentChildren.push({
      id: filePath,
      name: fileName,
      path: filePath,
      type: 'file',
      extension: fileName.split('.').pop(),
      size: item.content.length,
      metadata: { content: item.content },
    });
  });

  return sortTreeNodes(roots);
};

const marketplaceCloneNodeForParent = (
  node: FileTreeNode,
  parentPath: string | null,
  existingNodes: FileTreeNode[],
): { node: FileTreeNode } => {
  const existingPaths = new Set(existingNodes.map(item => item.path));
  let name = node.name;
  let path = marketplaceJoinPath(parentPath, name);
  let copyIndex = 1;
  while (existingPaths.has(path)) {
    const parts = node.name.split('.');
    if (parts.length > 1 && node.type === 'file') {
      const extension = parts.pop();
      name = `${parts.join('.')}-${copyIndex}.${extension}`;
    } else {
      name = `${node.name}-${copyIndex}`;
    }
    path = marketplaceJoinPath(parentPath, name);
    copyIndex += 1;
  }

  const cloneChildren = (children?: FileTreeNode[], sourceParentPath = node.path, targetParentPath = path): FileTreeNode[] | undefined => (
    children?.map(child => {
      const childPath = child.path.replace(sourceParentPath, targetParentPath);
      return {
        ...child,
        id: childPath,
        path: childPath,
        children: cloneChildren(child.children, sourceParentPath, targetParentPath),
      };
    })
  );

  return {
    node: {
      ...node,
      id: path,
      path,
      name,
      children: cloneChildren(node.children),
    },
  };
};

const marketplaceRemapContentPaths = (
  contents: Record<string, string>,
  oldPath: string,
  nextPath: string,
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents)
    .filter(([path]) => path === oldPath || path.startsWith(`${oldPath}/`))
    .map(([path, content]) => [path.replace(oldPath, nextPath), content]))
);

const marketplaceDeleteContentPaths = (
  contents: Record<string, string>,
  paths: string[],
): Record<string, string> => (
  Object.fromEntries(Object.entries(contents).filter(([path]) => (
    !paths.some(deletedPath => path === deletedPath || path.startsWith(`${deletedPath}/`))
  )))
);

export interface MarketplaceSkillsSectionProps {
  items: MarketplaceEditorResourceItem[];
  onDirty: () => void;
  onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
}

export const MarketplaceSkillsSection: React.FC<MarketplaceSkillsSectionProps> = ({
  items,
  onDirty,
  onPackageFilesChange,
}) => {
  const { t } = useI18n();
  const initialNodes = React.useMemo(() => marketplaceFeatureItemsToFileTree(items, 'skills'), [items]);
  const firstFilePath = React.useMemo(() => {
    const walk = (nodes: FileTreeNode[]): string | undefined => {
      for (const node of nodes) {
        if (node.type === 'file') return node.path;
        const childPath = node.children ? walk(node.children) : undefined;
        if (childPath) return childPath;
      }
      return undefined;
    };
    return walk(initialNodes);
  }, [initialNodes]);
  const treeState = useFileTreeState({
    initialNodes,
    initialExpandedIds: [],
    initialSelectedId: firstFilePath,
    enableMultiSelect: true,
  });
  const [dialogState, setDialogState] = React.useState<MarketplaceFileDialogState>(null);
  const [draggingPath, setDraggingPath] = React.useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = React.useState<string | null>(null);
  const [clipboardItem, setClipboardItem] = React.useState<FileTreeNode | null>(null);
  const lastPackageFilesSnapshotRef = React.useRef<string | null>(null);

  const uploadInputRef = React.useRef<HTMLInputElement>(null);

  const handleUpload = React.useCallback(() => {
    uploadInputRef.current?.click();
  }, []);

  const workbench = useManagedDocumentWorkbenchTabs<FileTreeNode>({
    adapter: {
      getKey: node => node.path,
      getName: node => node.name,
      readFile: async (node) => (
        typeof node.metadata?.content === 'string' ? node.metadata.content : ''
      ),
      saveFile: async () => {
        onDirty();
      },
      isWritable: () => true,
    } satisfies SkillsFileTreePersistenceAdapter<FileTreeNode>,
  });

  const fullContents = React.useMemo(
    () => ({
      ...marketplaceFileContentsFromTree(treeState.nodes),
      ...workbench.contents,
    }),
    [treeState.nodes, workbench.contents],
  );

  const packageFiles = React.useMemo(
    () => marketplaceFeaturePackageFilesFromTree(treeState.nodes, 'skills', fullContents),
    [fullContents, treeState.nodes],
  );

  const packageFilesSnapshot = React.useMemo(
    () => JSON.stringify(packageFiles),
    [packageFiles],
  );

  React.useEffect(() => {
    if (lastPackageFilesSnapshotRef.current === packageFilesSnapshot) return;
    const isFirstSync = lastPackageFilesSnapshotRef.current === null;
    lastPackageFilesSnapshotRef.current = packageFilesSnapshot;
    onPackageFilesChange(packageFiles);
    if (!isFirstSync) onDirty();
  }, [onDirty, onPackageFilesChange, packageFiles, packageFilesSnapshot]);

  const handleUploadFiles = React.useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    files.forEach(file => {
      const readContent = isZipFileName(file.name) ? readFileBase64(file) : readFileText(file);
      void readContent.then(content => {
        const existingPaths = new Set(treeState.flatNodes.map(n => n.path));
        let name = file.name;
        let path = name;
        let copyIndex = 1;
        while (existingPaths.has(path)) {
          const parts = name.split('.');
          if (parts.length > 1) {
            const ext = parts.pop();
            path = `${parts.join('.')}-${copyIndex}.${ext}`;
          } else {
            path = `${name}-${copyIndex}`;
          }
          copyIndex += 1;
        }
        const node: FileTreeNode = {
          id: path, name: path, path, type: 'file',
          extension: path.split('.').pop(),
          size: file.size,
          metadata: isZipFileName(file.name)
            ? { content, binary: true, mimeType: file.type || 'application/zip' }
            : { content },
        };
        treeState.addNode(null, node);
        if (!isZipFileName(file.name)) {
          workbench.setDocumentContent(path, content);
        }
        treeState.selectNode(path);
        if (!isZipFileName(file.name)) {
          workbench.openDocument(node);
        }
        onDirty();
      });
    });
    event.target.value = '';
  }, [onDirty, treeState, workbench]);

  const handleExtractArchive = React.useCallback(async (node: FileTreeNode) => {
    const content = typeof node.metadata?.content === 'string'
      ? node.metadata.content
      : fullContents[node.path];
    if (!content) return;

    const data = node.metadata?.binary === true
      ? base64ToUint8Array(content)
      : new TextEncoder().encode(content);
    const textFiles = await extractTextFilesFromZip(data, node.name);
    if (textFiles.length === 0) return;

    const { nodes: newNodes, resolved } = addFilesToTree(treeState.nodes, textFiles);
    treeState.setNodes(newNodes);
    resolved.forEach(({ path, content: extractedContent, binary }) => {
      if (!binary) {
        workbench.setDocumentContent(path, extractedContent);
      }
    });
    const last = resolved.filter(item => !item.binary).at(-1);
    if (last) {
      treeState.selectNode(last.path);
      workbench.openDocument(last.node);
    }
    onDirty();
  }, [fullContents, onDirty, treeState, workbench]);

  const openFileInTab = React.useCallback((node: FileTreeNode) => {
    if (node.type !== 'file') return;
    workbench.openDocument(node);
  }, [workbench]);

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      openFileInTab(node);
    }
  }, [openFileInTab, treeState]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    if (node.type === 'file') {
      openFileInTab(node);
    } else {
      treeState.toggleNode(node.path);
    }
  }, [openFileInTab, treeState]);

  const handleContextMenu = React.useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    treeState.openContextMenu(event.clientX, event.clientY, node);
  }, [treeState]);

  const handleCreate = React.useCallback((name: string) => {
    if (!dialogState || (dialogState.type !== 'create-file' && dialogState.type !== 'create-folder')) return;
    const parentPath = dialogState.parentPath;
    const path = marketplaceJoinPath(parentPath, name);
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: dialogState.type === 'create-folder' ? 'directory' : 'file',
      extension: dialogState.type === 'create-file' ? name.split('.').pop() : undefined,
      children: dialogState.type === 'create-folder' ? [] : undefined,
      size: dialogState.type === 'create-file' ? 0 : undefined,
    };

    treeState.addNode(parentPath, node);
    if (node.type === 'file') {
      workbench.setDocumentContent(path, '');
      treeState.selectNode(path);
      workbench.openDocument(node);
    } else {
      treeState.expandNode(path);
    }
    setDialogState(null);
    onDirty();
  }, [dialogState, onDirty, treeState, workbench]);

  const handleRename = React.useCallback((name: string) => {
    if (!dialogState || dialogState.type !== 'rename') return;
    const { node } = dialogState;
    const parentPath = marketplaceParentPath(node.path);
    const nextPath = marketplaceJoinPath(parentPath, name);
    treeState.setNodes(marketplaceRenameNode(treeState.nodes, node.path, nextPath, name));
    workbench.renamePath(node.path, nextPath, name);
    setDialogState(null);
    onDirty();
  }, [dialogState, onDirty, treeState, workbench]);

  const handleDelete = React.useCallback(() => {
    if (!dialogState || dialogState.type !== 'delete') return;
    const { node } = dialogState;
    treeState.removeNode(node.path);
    workbench.removePaths([node.path]);
    setDialogState(null);
    onDirty();
  }, [dialogState, onDirty, treeState, workbench]);

  const handleBatchDelete = React.useCallback(() => {
    const paths = Array.from(treeState.selectedIds);
    paths.forEach(path => treeState.removeNode(path));
    workbench.removePaths(paths);
    treeState.clearSelection();
    setDialogState(null);
    onDirty();
  }, [onDirty, treeState, workbench]);

  const contextMenuItems = useFileTreeContextMenu({
    node: treeState.contextMenu?.node ?? null,
    enableMultiSelect: true,
    selectedCount: treeState.selectedIds.size,
    selectedIds: treeState.selectedIds,
    hasClipboard: Boolean(clipboardItem),
    features: {
      upload: true,
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: true,
      paste: true,
      rename: true,
      delete: true,
      extractArchive: true,
      refresh: true,
    },
    callbacks: {
      onUpload: () => {
        treeState.closeContextMenu();
        handleUpload();
      },
      onCreateFile: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-file', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') });
      },
      onCreateFolder: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-folder', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') });
      },
      onCopy: node => setClipboardItem(node),
      onCopyPath: path => void navigator.clipboard.writeText(path),
      onPaste: () => {
        if (!clipboardItem || !treeState.contextMenu) return;
        const target = treeState.contextMenu.node;
        const parentPath = target.type === 'directory' ? target.path : marketplaceParentPath(target.path);
        const pasted = marketplaceCloneNodeForParent(clipboardItem, parentPath, treeState.flatNodes);
        treeState.addNode(parentPath, pasted.node);
        const nextContents = marketplaceRemapContentPaths(fullContents, clipboardItem.path, pasted.node.path);
        Object.entries(nextContents).forEach(([path, content]) => workbench.setDocumentContent(path, content));
        onDirty();
      },
      onRename: node => setDialogState({ type: 'rename', node }),
      onDelete: node => setDialogState({ type: 'delete', node }),
      onBatchDelete: () => {
        const node = treeState.contextMenu?.node;
        if (node) setDialogState({ type: 'batch-delete', node });
      },
      onExtractArchive: node => {
        void handleExtractArchive(node);
      },
      onRefresh: treeState.closeContextMenu,
      onClose: treeState.closeContextMenu,
    },
    t,
  });

  const headerActions = (
    <>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.refresh')}
        aria-label={t('marketplace.editor.fileManager.sidebar.refresh')}
      >
        <RefreshCw className="h-4 w-4" />
      </Button>
      <input
        ref={uploadInputRef}
        type="file"
        accept=".md,.txt,.zip"
        multiple
        className="hidden"
        onChange={handleUploadFiles}
      />
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.upload')}
        aria-label={t('marketplace.editor.fileManager.sidebar.upload')}
        onClick={handleUpload}
      >
        <Upload className="h-4 w-4" />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            title={t('marketplace.editor.fileManager.actions.create.trigger')}
            aria-label={t('marketplace.editor.fileManager.actions.create.trigger')}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-file', parentPath: null })} className="text-xs">
            <Plus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFile')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-folder', parentPath: null })} className="text-xs">
            <FolderPlus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFolder')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );

  return (
    <div className="flex h-full overflow-hidden border-x border-b bg-background">
      <div className="w-80">
        <MarketplaceSectionSidebarShell
          title={t('marketplace.editor.fileManager.skills.title')}
          icon={<Wand2 className="h-4 w-4" />}
          actions={headerActions}
          searchValue={treeState.searchQuery}
          onSearchChange={treeState.setSearchQuery}
          onSearchClear={treeState.clearSearch}
          searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
          body={(
            <FileTreePanel
              state={treeState}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              onContextMenu={handleContextMenu}
              onDragStart={node => setDraggingPath(node.path)}
              onDragEnd={() => {
                setDraggingPath(null);
                setDragOverPath(null);
              }}
              onDragOver={(node, event) => {
                event.preventDefault();
                if (node.type === 'directory') {
                  setDragOverPath(node.path);
                }
              }}
              onDragLeave={() => setDragOverPath(null)}
              onDrop={(node, event) => {
                event.preventDefault();
                setDragOverPath(null);
                setDraggingPath(null);
              }}
              onCreateFile={() => setDialogState({ type: 'create-file', parentPath: null })}
              onCreateFolder={() => setDialogState({ type: 'create-folder', parentPath: null })}
              onUpload={handleUpload}
              onRefresh={() => undefined}
              onBatchDelete={() => {
                const node = treeState.selectedNodes[0];
                if (node) setDialogState({ type: 'batch-delete', node });
              }}
              enableSearch={false}
              enableToolbar={false}
              enableMultiSelectBar
              enableDragDrop
              draggingPath={draggingPath}
              dragOverPath={dragOverPath}
              className="flex-1"
            />
          )}
        />

        <FileTreeContextMenu
          contextMenu={treeState.contextMenu}
          items={contextMenuItems}
          onClose={treeState.closeContextMenu}
        />
      </div>

      <div className="min-w-0 flex-1 overflow-hidden">
        {workbench.tabs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : (
          <FileViewerWorkbench
            tabs={workbench.tabs}
            activeTabId={workbench.activeTabId}
            adapter={workbench.adapter}
            capabilities={{
              canEdit: true,
              canSave: true,
              canCopyPath: true,
              canCloseTabs: true,
            }}
            onTabsChange={workbench.applyTabsChange}
            onActiveTabChange={workbench.setActiveTabId}
            className="h-full"
          />
        )}
      </div>

      <FileCreateDialog
        open={dialogState?.type === 'create-file'}
        type="file"
        onClose={() => setDialogState(null)}
        onConfirm={handleCreate}
      />
      <FileCreateDialog
        open={dialogState?.type === 'create-folder'}
        type="folder"
        onClose={() => setDialogState(null)}
        onConfirm={handleCreate}
      />
      <FileRenameDialog
        open={dialogState?.type === 'rename'}
        currentName={dialogState?.type === 'rename' ? dialogState.node.name : ''}
        onClose={() => setDialogState(null)}
        onConfirm={handleRename}
      />
      <FileDeleteDialog
        open={dialogState?.type === 'delete'}
        fileName={dialogState?.type === 'delete' ? dialogState.node.name : ''}
        fileType={dialogState?.type === 'delete' ? dialogState.node.type : 'file'}
        onClose={() => setDialogState(null)}
        onConfirm={handleDelete}
      />
      <BatchDeleteDialog
        open={dialogState?.type === 'batch-delete'}
        files={treeState.selectedNodes.map(node => ({ name: node.name, path: node.path, type: node.type }))}
        onClose={() => setDialogState(null)}
        onConfirm={handleBatchDelete}
      />
    </div>
  );
};

MarketplaceSkillsSection.displayName = 'MarketplaceSkillsSection';

export default MarketplaceSkillsSection;
