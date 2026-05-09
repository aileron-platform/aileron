import React from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  FileArchive,
  FolderPlus,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Sparkles,
  Upload,
  Wand2,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  sortTreeNodes,
  useFileTreeContextMenu,
  useFileTreeState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { FileFocusToolbar, FileViewerWorkbench, useFileViewerTabs } from '@/shared/components/file-workbench/viewer-entry';
import type {
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchTab,
} from '@/shared/components/file-workbench/viewer-entry';
import type {
  MarketplaceFeatureContentItem,
  MarketplacePackageDetail,
  MarketplacePackageFile,
  MarketplaceProvider,
} from '@/shared/types/marketplace';
import { cn } from '@/shared/utils/cn';
import {
  marketplaceDeleteContentPaths,
  marketplaceFeaturePackageFilesFromTree,
  marketplaceFileContentsFromTree,
  marketplaceFindFirstFilePath,
  marketplaceJoinPath,
  marketplacePackageFilesFromTree,
  marketplacePackageFilesToFileTreeNodes,
  marketplaceRenameContentPaths,
  marketplaceRenameNode,
} from '../adapters/marketplaceFileTreeAdapter';
import { createMarketplaceFileWorkbenchAdapter } from '../adapters/marketplaceFileWorkbenchAdapter';
import { downloadBlob } from '../utils/downloadBlob';
import { MarketplaceSectionSidebarShell } from './MarketplaceSectionSidebarShell';

const MARKETPLACE_FILES_SIDEBAR_DEFAULT_WIDTH = 320;
const MARKETPLACE_FILES_SIDEBAR_MIN_WIDTH = 240;
const MARKETPLACE_FILES_SIDEBAR_MAX_WIDTH = 520;
const MARKETPLACE_FILES_SIDEBAR_COLLAPSED_WIDTH = 44;

type MarketplaceFilesSectionProps =
  | {
    mode: 'package';
    detail: MarketplacePackageDetail;
  }
  | {
    mode: 'skills';
    items: MarketplaceFeatureContentItem[];
  }
  | {
    mode: 'editor-skills';
    items: MarketplaceEditorResourceItem[];
    onDirty: () => void;
    onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
  }
  | {
    mode: 'editor-package';
    provider: MarketplaceProvider;
    packageId: string;
    packageRoot: string;
    displayName: string;
    packageFiles: MarketplacePackageFile[];
    initialNodes: FileTreeNode[];
    onDirty: () => void;
    onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
  };

interface MarketplaceReadOnlyFileTreeViewerProps {
  titleKey: string;
  icon: React.ComponentType<{ className?: string }>;
  initialNodes: FileTreeNode[];
  rootLabel?: string;
  viewerAdapter?: FileViewerWorkbenchAdapter;
}

interface MarketplaceReadOnlyContentWorkbenchProps {
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  adapter?: FileViewerWorkbenchAdapter;
}

const defaultFileName = (item: MarketplaceFeatureContentItem, extension = 'md') =>
  item.path?.split('/').pop() ?? `${item.id}.${extension}`;

const defaultMarkdownContent = (item: MarketplaceFeatureContentItem) =>
  item.content ?? `# ${item.name}\n\n${item.description ?? ''}`;

const joinPath = (parentPath: string | null | undefined, name: string) => (
  parentPath ? `${parentPath.replace(/\/$/, '')}/${name}` : name
);

const getPackageRoot = (provider: MarketplaceProvider, packageId: string): string => (
  provider === 'gemini'
    ? `gemini/extensions/${packageId}`
    : `${provider}/plugins/${packageId}`
);

const featureItemsToFileTree = (
  items: MarketplaceFeatureContentItem[],
  basePath: string,
): FileTreeNode[] => {
  const roots: FileTreeNode[] = [];
  const directories = new Map<string, FileTreeNode>();

  const ensureDirectory = (path: string, name: string, parent: FileTreeNode[]) => {
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
    parent.push(node);
    return node;
  };

  items.forEach(item => {
    const sourcePath = item.path?.trim() || `${basePath}/${item.id}/SKILL.md`;
    const relativePath = sourcePath.replace(new RegExp(`^${basePath}/?`), '');
    const parts = relativePath.split('/').filter(Boolean);
    let parentChildren = roots;
    let currentPath = '';

    parts.slice(0, -1).forEach(part => {
      currentPath = joinPath(currentPath || null, part);
      const directory = ensureDirectory(currentPath, part, parentChildren);
      parentChildren = directory.children ?? [];
    });

    const fileName = parts.at(-1) ?? defaultFileName(item);
    const filePath = joinPath(currentPath || null, fileName);
    const content = defaultMarkdownContent(item);
    parentChildren.push({
      id: filePath,
      name: fileName,
      path: filePath,
      type: 'file',
      extension: fileName.split('.').pop(),
      size: content.length,
      metadata: { content },
    });
  });

  return sortTreeNodes(roots);
};

export const MarketplaceFilesSection: React.FC<MarketplaceFilesSectionProps> = (props) => {
  if (props.mode === 'skills') {
    return <MarketplaceSkillsFilesSection items={props.items} />;
  }
  if (props.mode === 'editor-skills') {
    return (
      <MarketplaceSkillsFileManager
        items={props.items}
        onDirty={props.onDirty}
        onPackageFilesChange={props.onPackageFilesChange}
      />
    );
  }
  if (props.mode === 'editor-package') {
    return (
      <MarketplacePackageFileManager
        provider={props.provider}
        packageId={props.packageId}
        packageRoot={props.packageRoot}
        displayName={props.displayName}
        packageFiles={props.packageFiles}
        initialNodes={props.initialNodes}
        onDirty={props.onDirty}
        onPackageFilesChange={props.onPackageFilesChange}
      />
    );
  }
  return <MarketplacePackageFilesSection detail={props.detail} />;
};

const MarketplacePackageFilesSection: React.FC<{ detail: MarketplacePackageDetail }> = ({ detail }) => {
  const packageRoot = detail.registryPath || getPackageRoot(detail.provider, detail.packageId);
  const readOnlyAdapter = React.useMemo(() => createMarketplaceFileWorkbenchAdapter({
    provider: detail.provider,
    packageId: detail.packageId,
    packageRoot,
    displayName: detail.displayName,
    getPackageFiles: () => detail.packageFiles,
    onPackageFilesChange: () => undefined,
    readOnly: true,
  }), [detail.displayName, detail.packageFiles, detail.packageId, detail.provider, packageRoot]);
  const initialNodes = React.useMemo(
    () => marketplacePackageFilesToFileTreeNodes(detail.packageFiles, {
      rootPath: `/${packageRoot}`,
      scope: detail.provider === 'gemini' ? 'extension' : 'plugin',
    }),
    [detail.packageFiles, detail.provider, packageRoot],
  );

  return (
    <MarketplaceReadOnlyFileTreeViewer
      titleKey="marketplace.editor.fileManager.packageFiles.title"
      icon={FileArchive}
      initialNodes={initialNodes}
      rootLabel={packageRoot}
      viewerAdapter={readOnlyAdapter}
    />
  );
};

const MarketplaceSkillsFilesSection: React.FC<{ items: MarketplaceFeatureContentItem[] }> = ({ items }) => {
  const initialNodes = React.useMemo(() => featureItemsToFileTree(items, 'skills'), [items]);

  return (
    <MarketplaceReadOnlyFileTreeViewer
      titleKey="marketplace.editor.fileManager.skills.title"
      icon={Sparkles}
      initialNodes={initialNodes}
    />
  );
};


const isMarketplaceBinaryFile = (node: FileTreeNode | null): boolean => {
  if (!node) return false;
  if (node.metadata?.binary === true) return true;
  const mimeType = typeof node.metadata?.mimeType === 'string' ? node.metadata.mimeType : '';
  return Boolean(mimeType && !mimeType.startsWith('text/') && mimeType !== 'application/json');
};

const getStringField = (value: unknown, fallback = ''): string => (
  typeof value === 'string' && value.trim() ? value : fallback
);

interface MarketplaceEditorResourceItem {
  id: string;
  titleKey?: string;
  descriptionKey?: string;
  path: string;
  content: string;
  title?: string;
  description?: string;
  badge?: string;
  code?: string;
  meta?: Array<{ labelKey: string; value: string }>;
}

interface MarketplaceSkillsFileManagerProps {
  items: MarketplaceEditorResourceItem[];
  onDirty: () => void;
  onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
}

export const shouldUpdateMarketplaceEditorFileContent = (nextContent: string, currentContent: string): boolean => (
  nextContent !== currentContent
);

const MarketplaceSkillsFileManager: React.FC<MarketplaceSkillsFileManagerProps> = ({ items, onDirty, onPackageFilesChange }) => {
  const { t } = useI18n();
  const initialNodes = React.useMemo(() => marketplaceFeatureItemsToFileTree(items, 'skills'), [items]);
  const firstFilePath = React.useMemo(() => marketplaceFindFirstFilePath(initialNodes), [initialNodes]);
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
  const [contents, setContents] = React.useState<Record<string, string>>(
    () => marketplaceFileContentsFromTree(initialNodes),
  );
  const fileTabs = useFileViewerTabs();
  const contentsRef = React.useRef(contents);
  React.useEffect(() => {
    contentsRef.current = contents;
  }, [contents]);
  const flatNodesRef = React.useRef(treeState.flatNodes);
  React.useEffect(() => {
    flatNodesRef.current = treeState.flatNodes;
  }, [treeState.flatNodes]);

  React.useEffect(() => {
    onPackageFilesChange(marketplaceFeaturePackageFilesFromTree(treeState.nodes, 'skills', contents));
  }, [contents, onPackageFilesChange, treeState.nodes]);

  const openFileInTab = React.useCallback((node: FileTreeNode) => {
    if (node.type !== 'file') return;
    fileTabs.openFile(node, contentsRef.current[node.path] ?? '');
  }, [fileTabs]);

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
      setContents(prev => ({ ...prev, [path]: '' }));
      treeState.selectNode(path);
      fileTabs.openFile(node, '');
    } else {
      treeState.expandNode(path);
    }
    setDialogState(null);
    onDirty();
  }, [dialogState, fileTabs, onDirty, treeState]);

  const handleRename = React.useCallback((name: string) => {
    if (!dialogState || dialogState.type !== 'rename') return;
    const { node } = dialogState;
    const parentPath = marketplaceParentPath(node.path);
    const nextPath = marketplaceJoinPath(parentPath, name);
    treeState.setNodes(marketplaceRenameNode(treeState.nodes, node.path, nextPath, name));
    setContents(prev => marketplaceRenameContentPaths(prev, node.path, nextPath));
    fileTabs.renamePath(node.path, nextPath, name);
    setDialogState(null);
    onDirty();
  }, [dialogState, fileTabs, onDirty, treeState]);

  const handleDelete = React.useCallback(() => {
    if (!dialogState || dialogState.type !== 'delete') return;
    const { node } = dialogState;
    treeState.removeNode(node.path);
    setContents(prev => marketplaceDeleteContentPaths(prev, [node.path]));
    fileTabs.removePaths([node.path]);
    setDialogState(null);
    onDirty();
  }, [dialogState, fileTabs, onDirty, treeState]);

  const handleBatchDelete = React.useCallback(() => {
    const paths = Array.from(treeState.selectedIds);
    paths.forEach(path => treeState.removeNode(path));
    setContents(prev => marketplaceDeleteContentPaths(prev, paths));
    fileTabs.removePaths(paths);
    treeState.clearSelection();
    setDialogState(null);
    onDirty();
  }, [fileTabs, onDirty, treeState]);

  const handleSaveFile = React.useCallback(async (path: string, content: string) => {
    if (!shouldUpdateMarketplaceEditorFileContent(content, contentsRef.current[path] ?? '')) return;
    setContents(prev => ({ ...prev, [path]: content }));
    onDirty();
  }, [onDirty]);

  const viewerAdapter = React.useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async (path) => contentsRef.current[path] ?? '',
    saveFile: handleSaveFile,
    copyPath: async (path) => {
      await navigator.clipboard.writeText(path);
    },
  }), [handleSaveFile]);

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
      refresh: true,
    },
    callbacks: {
      onUpload: treeState.closeContextMenu,
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
        setContents(prev => ({ ...prev, ...marketplaceRemapContentPaths(prev, clipboardItem.path, pasted.node.path) }));
        onDirty();
      },
      onRename: node => setDialogState({ type: 'rename', node }),
      onDelete: node => setDialogState({ type: 'delete', node }),
      onBatchDelete: () => {
        const node = treeState.contextMenu?.node;
        if (node) setDialogState({ type: 'batch-delete', node });
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
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.upload')}
        aria-label={t('marketplace.editor.fileManager.sidebar.upload')}
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
              onUpload={() => undefined}
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
        {fileTabs.tabs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : (
          <FileViewerWorkbench
            tabs={fileTabs.tabs}
            activeTabId={fileTabs.activeTabId}
            adapter={viewerAdapter}
            capabilities={{
              canEdit: true,
              canSave: true,
              canCopyPath: true,
              canCloseTabs: true,
            }}
            renderFocusToolbar={(params) => (
              <FileFocusToolbar
                {...params}
                exitLabel={t('shared.fileViewer.toolbar.collapse')}
                onExit={params.onExit ?? (() => undefined)}
              />
            )}
            onTabsChange={fileTabs.applyTabsChange}
            onActiveTabChange={fileTabs.setActiveTabId}
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

interface MarketplacePackageFileManagerProps {
  provider: MarketplaceProvider;
  packageId: string;
  packageRoot: string;
  displayName: string;
  packageFiles: MarketplacePackageFile[];
  initialNodes: FileTreeNode[];
  onDirty: () => void;
  onPackageFilesChange: (files: MarketplacePackageFile[]) => void;
}

type MarketplaceFileDialogState =
  | { type: 'create-file' | 'create-folder'; parentPath: string | null }
  | { type: 'rename' | 'delete' | 'batch-delete'; node: FileTreeNode }
  | null;

const MarketplacePackageFileManager: React.FC<MarketplacePackageFileManagerProps> = ({
  provider,
  packageId,
  packageRoot,
  displayName,
  packageFiles,
  initialNodes,
  onDirty,
  onPackageFilesChange,
}) => {
  const { t } = useI18n();
  const packageRootPath = `/${packageRoot}`;
  const initialSelectedPath = React.useMemo(() => marketplaceFindFirstFilePath(initialNodes), [initialNodes]);
  const treeState = useFileTreeState({
    initialNodes,
    initialExpandedIds: [],
    initialSelectedId: initialSelectedPath,
    enableMultiSelect: true,
  });
  const hasPackageRootNode = React.useMemo(
    () => treeState.flatNodes.some(node => node.path === packageRootPath && node.type === 'directory'),
    [packageRootPath, treeState.flatNodes],
  );
  const packageRootParentPath = hasPackageRootNode ? packageRootPath : null;
  const [dialogState, setDialogState] = React.useState<MarketplaceFileDialogState>(null);
  const [draggingPath, setDraggingPath] = React.useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = React.useState<string | null>(null);
  const [clipboardItem, setClipboardItem] = React.useState<FileTreeNode | null>(null);
  const [contents, setContents] = React.useState<Record<string, string>>(
    () => marketplaceFileContentsFromTree(initialNodes),
  );
  const fileTabs = useFileViewerTabs();
  const contentsRef = React.useRef(contents);
  React.useEffect(() => {
    contentsRef.current = contents;
  }, [contents]);
  const flatNodesRef = React.useRef(treeState.flatNodes);
  React.useEffect(() => {
    flatNodesRef.current = treeState.flatNodes;
  }, [treeState.flatNodes]);
  const workbenchAdapter = React.useMemo(() => createMarketplaceFileWorkbenchAdapter({
    provider,
    packageId,
    packageRoot,
    displayName,
    getPackageFiles: () => packageFiles,
    onPackageFilesChange,
  }), [displayName, onPackageFilesChange, packageFiles, packageId, packageRoot, provider]);

  React.useEffect(() => {
    onPackageFilesChange(marketplacePackageFilesFromTree(treeState.nodes, packageRootPath, contents));
  }, [contents, onPackageFilesChange, packageRootPath, treeState.nodes]);

  const openFileInTab = React.useCallback((node: FileTreeNode) => {
    if (node.type !== 'file') return;
    fileTabs.openFile(node, contentsRef.current[node.path] ?? '');
  }, [fileTabs]);

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
    const parentPath = dialogState.parentPath ?? packageRootParentPath;
    const fileParentPath = parentPath ?? packageRootPath;
    const path = marketplaceJoinPath(fileParentPath, name);
    const node: FileTreeNode = {
      id: path,
      name,
      path,
      type: dialogState.type === 'create-folder' ? 'directory' : 'file',
      extension: dialogState.type === 'create-file' ? name.split('.').pop() : undefined,
      children: dialogState.type === 'create-folder' ? [] : undefined,
      size: dialogState.type === 'create-file' ? 0 : undefined,
    };

    void workbenchAdapter.create({
      type: 'create',
      path,
      content: '',
      isDirectory: node.type === 'directory',
    });
    treeState.addNode(parentPath, node);
    if (node.type === 'file') {
      setContents(prev => ({ ...prev, [path]: '' }));
      treeState.selectNode(path);
      fileTabs.openFile(node, '');
    } else {
      treeState.expandNode(path);
    }
    setDialogState(null);
    onDirty();
  }, [dialogState, fileTabs, onDirty, packageRootParentPath, packageRootPath, treeState, workbenchAdapter]);

  const handleRename = React.useCallback((name: string) => {
    if (!dialogState || dialogState.type !== 'rename') return;
    const { node } = dialogState;
    if (node.path === packageRootPath) {
      setDialogState(null);
      return;
    }
    const parentPath = marketplaceParentPath(node.path);
    const nextPath = marketplaceJoinPath(parentPath, name);
    void workbenchAdapter.rename(node.path, nextPath);
    const renamedNodes = marketplaceRenameNode(treeState.nodes, node.path, nextPath, name);
    treeState.setNodes(renamedNodes);
    setContents(prev => marketplaceRenameContentPaths(prev, node.path, nextPath));
    fileTabs.renamePath(node.path, nextPath, name);
    setDialogState(null);
    onDirty();
  }, [dialogState, fileTabs, onDirty, packageRootPath, treeState, workbenchAdapter]);

  const handleDelete = React.useCallback(() => {
    if (!dialogState || dialogState.type !== 'delete') return;
    const { node } = dialogState;
    if (node.path === packageRootPath) {
      setDialogState(null);
      return;
    }
    void workbenchAdapter.delete(node.path, true);
    treeState.removeNode(node.path);
    setContents(prev => marketplaceDeleteContentPaths(prev, [node.path]));
    fileTabs.removePaths([node.path]);
    setDialogState(null);
    onDirty();
  }, [dialogState, fileTabs, onDirty, packageRootPath, treeState, workbenchAdapter]);

  const handleBatchDelete = React.useCallback(() => {
    const paths = Array.from(treeState.selectedIds).filter(path => path !== packageRootPath);
    if (!paths.length) {
      setDialogState(null);
      return;
    }
    void workbenchAdapter.batchDelete({ paths, recursive: true });
    paths.forEach(path => treeState.removeNode(path));
    setContents(prev => marketplaceDeleteContentPaths(prev, paths));
    fileTabs.removePaths(paths);
    treeState.clearSelection();
    setDialogState(null);
    onDirty();
  }, [fileTabs, onDirty, packageRootPath, treeState, workbenchAdapter]);

  const handleSaveFile = React.useCallback(async (path: string, content: string) => {
    const node = flatNodesRef.current.find(item => item.path === path && item.type === 'file');
    if (!node || isMarketplaceBinaryFile(node)) return;
    void workbenchAdapter.write(path, content);
    setContents(prev => ({ ...prev, [path]: content }));
    onDirty();
  }, [onDirty, workbenchAdapter]);

  const viewerAdapter = React.useMemo<FileViewerWorkbenchAdapter>(() => ({
    ...workbenchAdapter,
    readFile: workbenchAdapter.readFile,
    readBlob: async (path) => {
      const node = flatNodesRef.current.find(item => item.path === path);
      const previewDataUrl = typeof node?.metadata?.previewDataUrl === 'string' ? node.metadata.previewDataUrl : '';
      if (previewDataUrl) {
        const response = await fetch(previewDataUrl);
        return response.blob();
      }
      const mimeType = getStringField(node?.metadata?.mimeType, 'application/octet-stream');
      return new Blob([contentsRef.current[path] ?? ''], { type: mimeType });
    },
    saveFile: handleSaveFile,
    copyPath: async (path) => {
      await navigator.clipboard.writeText(path);
    },
  }), [handleSaveFile, workbenchAdapter]);

  const isFileWritable = React.useCallback((path: string) => {
    const node = flatNodesRef.current.find(item => item.path === path);
    return !isMarketplaceBinaryFile(node ?? null);
  }, []);

  const handleUploadBinaryAsset = React.useCallback(() => {
    const assetsPath = `${packageRootPath}/assets`;
    const uploadPath = `${assetsPath}/uploaded-image.png`;
    const uploadNode: FileTreeNode = {
      id: uploadPath,
      name: 'uploaded-image.png',
      path: uploadPath,
      type: 'file',
      extension: 'png',
      scope: packageRoot.includes('/extensions/') ? 'extension' : 'plugin',
      size: 68,
      metadata: {
        binary: true,
        mimeType: 'image/png',
        previewDataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
      },
    };
    const hasAssetsDirectory = treeState.flatNodes.some(node => node.path === assetsPath && node.type === 'directory');
    if (!hasAssetsDirectory) {
      treeState.addNode(packageRootParentPath, {
        id: assetsPath,
        name: 'assets',
        path: assetsPath,
        type: 'directory',
        scope: packageRoot.includes('/extensions/') ? 'extension' : 'plugin',
        children: [],
      });
    }
    if (!treeState.flatNodes.some(node => node.path === uploadPath)) {
      treeState.addNode(assetsPath, uploadNode);
    }
    treeState.expandNode(assetsPath);
    treeState.selectNode(uploadPath);
    fileTabs.openFile(uploadNode, '');
    onDirty();
  }, [fileTabs, onDirty, packageRoot, packageRootParentPath, packageRootPath, treeState]);

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
      refresh: true,
    },
    callbacks: {
      onUpload: () => {
        treeState.closeContextMenu();
        handleUploadBinaryAsset();
      },
      onCreateFile: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-file', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') ?? packageRootParentPath });
      },
      onCreateFolder: () => {
        const node = treeState.contextMenu?.node;
        setDialogState({ type: 'create-folder', parentPath: node?.type === 'directory' ? node.path : marketplaceParentPath(node?.path ?? '') ?? packageRootParentPath });
      },
      onCopy: node => setClipboardItem(node),
      onCopyPath: path => void navigator.clipboard.writeText(path),
      onPaste: () => {
        if (!clipboardItem || !treeState.contextMenu) return;
        const target = treeState.contextMenu.node;
        const parentPath = target.type === 'directory' ? target.path : marketplaceParentPath(target.path);
        const pasted = marketplaceCloneNodeForParent(clipboardItem, parentPath, treeState.flatNodes);
        treeState.addNode(parentPath, pasted.node);
        setContents(prev => ({ ...prev, ...marketplaceRemapContentPaths(prev, clipboardItem.path, pasted.node.path) }));
        onDirty();
      },
      onRename: node => {
        if (node.path !== packageRootPath) setDialogState({ type: 'rename', node });
      },
      onDelete: node => {
        if (node.path !== packageRootPath) setDialogState({ type: 'delete', node });
      },
      onBatchDelete: () => {
        const node = treeState.contextMenu?.node;
        if (node) setDialogState({ type: 'batch-delete', node });
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
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        title={t('marketplace.editor.fileManager.sidebar.upload')}
        aria-label={t('marketplace.editor.fileManager.sidebar.upload')}
        onClick={handleUploadBinaryAsset}
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
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-file', parentPath: packageRootParentPath })} className="text-xs">
            <Plus className="mr-2 h-4 w-4" />
            {t('marketplace.editor.fileManager.sidebar.createFile')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDialogState({ type: 'create-folder', parentPath: packageRootParentPath })} className="text-xs">
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
          title={t('marketplace.editor.fileManager.packageFiles.title')}
          icon={<FileArchive className="h-4 w-4" />}
          actions={headerActions}
          searchValue={treeState.searchQuery}
          onSearchChange={treeState.setSearchQuery}
          onSearchClear={treeState.clearSearch}
          searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
          body={(
            <div className="flex h-full min-h-0 flex-col">
              <div className="border-b border-border bg-muted/20 px-3 py-2">
                <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {t('marketplace.editor.fileManager.packageFiles.rootLabel')}
                </div>
                <div className="mt-1 truncate font-mono text-xs text-foreground" title={packageRoot}>
                  {packageRoot}
                </div>
              </div>
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
                onCreateFile={() => setDialogState({ type: 'create-file', parentPath: packageRootParentPath })}
                onCreateFolder={() => setDialogState({ type: 'create-folder', parentPath: packageRootParentPath })}
                onUpload={handleUploadBinaryAsset}
                onRefresh={() => undefined}
                onBatchDelete={() => {
                  const node = treeState.selectedNodes.find(selectedNode => selectedNode.path !== packageRootPath);
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
            </div>
          )}
        />

        <FileTreeContextMenu
          contextMenu={treeState.contextMenu}
          items={contextMenuItems}
          onClose={treeState.closeContextMenu}
        />
      </div>

      <div className="min-w-0 flex-1 overflow-hidden">
        {fileTabs.tabs.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : (
          <FileViewerWorkbench
            tabs={fileTabs.tabs}
            activeTabId={fileTabs.activeTabId}
            adapter={viewerAdapter}
            capabilities={{
              canEdit: true,
              canSave: true,
              canCopyPath: true,
              canCloseTabs: true,
            }}
            isPathWritable={isFileWritable}
            renderFocusToolbar={(params) => (
              <FileFocusToolbar
                {...params}
                exitLabel={t('shared.fileViewer.toolbar.collapse')}
                onExit={params.onExit ?? (() => undefined)}
              />
            )}
            onTabsChange={fileTabs.applyTabsChange}
            onActiveTabChange={fileTabs.setActiveTabId}
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

  return roots;
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

const MarketplaceReadOnlyFileTreeViewer: React.FC<MarketplaceReadOnlyFileTreeViewerProps> = ({
  titleKey,
  icon: Icon,
  initialNodes,
  rootLabel,
  viewerAdapter,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [sidebarWidth, setSidebarWidth] = React.useState(MARKETPLACE_FILES_SIDEBAR_DEFAULT_WIDTH);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);
  const [isSidebarResizing, setIsSidebarResizing] = React.useState(false);
  const sidebarResizeRef = React.useRef<{ startX: number; startWidth: number } | null>(null);
  const firstFilePath = React.useMemo(() => marketplaceFindFirstFilePath(initialNodes), [initialNodes]);
  const treeState = useFileTreeState({
    initialNodes,
    initialExpandedIds: [],
    initialSelectedId: firstFilePath,
    enableMultiSelect: false,
  });
  const [activePath, setActivePath] = React.useState(firstFilePath ?? '');
  const contents = React.useMemo(() => marketplaceFileContentsFromTree(initialNodes), [initialNodes]);
  const fallbackViewerAdapter = React.useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async (path) => contents[path] ?? '',
    copyPath: async (path) => {
      await navigator.clipboard.writeText(path);
    },
  }), [contents]);

  const activeNode = React.useMemo(
    () => treeState.flatNodes.find(node => node.path === activePath && node.type === 'file') ?? null,
    [activePath, treeState.flatNodes],
  );

  const activeViewerTabs = React.useMemo<FileViewerWorkbenchTab[]>(() => {
    if (!activeNode) return [];
    const content = contents[activeNode.path] ?? '';
    return [{
      id: activeNode.path,
      path: activeNode.path,
      name: activeNode.name,
      content,
      originalContent: content,
      isModified: false,
    }];
  }, [activeNode, contents]);

  React.useEffect(() => {
    if (activeNode) return;
    const nextFile = treeState.flatNodes.find(node => node.type === 'file');
    setActivePath(nextFile?.path ?? '');
  }, [activeNode, treeState.flatNodes]);

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file') {
      setActivePath(node.path);
    }
  }, [treeState]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    if (node.type === 'file') {
      setActivePath(node.path);
    } else {
      treeState.toggleNode(node.path);
    }
  }, [treeState]);

  const handleCopy = async () => {
    if (!activeNode) return;
    try {
      await navigator.clipboard.writeText(contents[activeNode.path] ?? '');
      toast({ title: t('marketplace.detail.viewer.copySuccess') });
    } catch {
      toast({ title: t('marketplace.detail.viewer.copyFailed'), variant: 'destructive' });
    }
  };

  const handleDownload = () => {
    if (!activeNode) return;
    const blob = new Blob([contents[activeNode.path] ?? ''], { type: 'text/markdown' });
    downloadBlob(blob, activeNode.name);
  };

  const handleSidebarResizeStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsSidebarCollapsed(false);
    setIsSidebarResizing(true);
    sidebarResizeRef.current = {
      startX: event.clientX,
      startWidth: isSidebarCollapsed ? MARKETPLACE_FILES_SIDEBAR_MIN_WIDTH : sidebarWidth,
    };
    document.body.classList.add('select-none', 'cursor-col-resize');
  };

  React.useEffect(() => {
    if (!isSidebarResizing) return undefined;

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = sidebarResizeRef.current;
      if (!dragState) return;
      const nextWidth = Math.min(
        Math.max(dragState.startWidth + event.clientX - dragState.startX, MARKETPLACE_FILES_SIDEBAR_MIN_WIDTH),
        MARKETPLACE_FILES_SIDEBAR_MAX_WIDTH,
      );
      setSidebarWidth(nextWidth);
    };

    const handleMouseUp = () => {
      sidebarResizeRef.current = null;
      setIsSidebarResizing(false);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };
  }, [isSidebarResizing]);

  return (
    <div className="flex h-full overflow-hidden border-x border-b bg-background">
      <div
        className="relative flex-shrink-0"
        style={{ width: isSidebarCollapsed ? MARKETPLACE_FILES_SIDEBAR_COLLAPSED_WIDTH : sidebarWidth }}
      >
        {isSidebarCollapsed ? (
          <div className="flex h-full flex-col items-center gap-2 border-r border-border bg-background px-1 py-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              aria-label={t('marketplace.detail.viewer.expandSidebar')}
              title={t('marketplace.detail.viewer.expandSidebar')}
              onClick={() => setIsSidebarCollapsed(false)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Icon className="h-4 w-4 text-primary" />
          </div>
        ) : (
          <MarketplaceSectionSidebarShell
            title={t(titleKey)}
            icon={<Icon className="h-4 w-4" />}
            actions={(
              <>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  title={t('marketplace.detail.viewer.refresh')}
                  aria-label={t('marketplace.detail.viewer.refresh')}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  title={t('marketplace.detail.viewer.collapseSidebar')}
                  aria-label={t('marketplace.detail.viewer.collapseSidebar')}
                  onClick={() => setIsSidebarCollapsed(true)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </>
            )}
            searchValue={treeState.searchQuery}
            onSearchChange={treeState.setSearchQuery}
            onSearchClear={treeState.clearSearch}
            searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
            body={(
              <div className="flex h-full min-h-0 flex-col">
                {rootLabel ? (
                  <div className="border-b border-border bg-muted/20 px-3 py-2">
                    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      {t('marketplace.editor.fileManager.packageFiles.rootLabel')}
                    </div>
                    <div className="mt-1 truncate font-mono text-xs text-foreground" title={rootLabel}>
                      {rootLabel}
                    </div>
                  </div>
                ) : null}
                <FileTreePanel
                  state={treeState}
                  onNodeClick={handleNodeClick}
                  onNodeDoubleClick={handleNodeDoubleClick}
                  enableSearch={false}
                  enableToolbar={false}
                  enableMultiSelectBar={false}
                  enableBottomStatusBar={false}
                  enableDragDrop={false}
                  className="flex-1"
                />
              </div>
            )}
          />
        )}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={t('marketplace.detail.viewer.resizeSidebar')}
          className={cn(
            'absolute right-0 top-0 z-20 h-full w-1 cursor-col-resize transition-colors',
            isSidebarResizing ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
          )}
          onMouseDown={handleSidebarResizeStart}
        />
      </div>

      <div className="min-w-0 flex-1 overflow-hidden">
        {!activeNode ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {t('marketplace.editor.fileManager.viewer.noFile')}
          </div>
        ) : (
          <div className="flex h-full flex-col bg-background">
            <div className="flex h-12 items-center justify-between border-b border-border px-4">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-foreground">{activeNode.name}</div>
                <div className="truncate font-mono text-xs text-muted-foreground">{activeNode.path}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleCopy}>
                  <Copy className="mr-1.5 h-3.5 w-3.5" />
                  {t('marketplace.detail.viewer.copy')}
                </Button>
                <Button variant="outline" size="sm" onClick={handleDownload}>
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  {t('marketplace.detail.viewer.download')}
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <div className="mx-auto max-w-4xl">
                <MarketplaceReadOnlyContentWorkbench
                  tabs={activeViewerTabs}
                  activeTabId={activeNode.path}
                  adapter={viewerAdapter ?? fallbackViewerAdapter}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const MarketplaceReadOnlyContentWorkbench: React.FC<MarketplaceReadOnlyContentWorkbenchProps> = ({
  tabs,
  activeTabId,
  adapter,
}) => {
  const fallbackAdapter = React.useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async (path) => tabs.find(tab => tab.path === path)?.content ?? '',
  }), [tabs]);

  return (
    <div className="h-[32rem] min-h-64 overflow-hidden rounded-md border border-border">
      <FileViewerWorkbench
        tabs={tabs}
        activeTabId={activeTabId}
        adapter={adapter ?? fallbackAdapter}
        readOnly
        hideChrome
        capabilities={{
          canEdit: false,
          canSave: false,
          canCloseTabs: false,
        }}
        onTabsChange={() => undefined}
        onActiveTabChange={() => undefined}
        className="h-full"
      />
    </div>
  );
};
