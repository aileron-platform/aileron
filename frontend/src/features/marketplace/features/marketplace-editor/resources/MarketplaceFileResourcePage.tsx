import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, FileArchive, FileText, Folder, RefreshCw, Wand2 } from 'lucide-react';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Button } from '@/shared/components/ui/button';
import { EmptyState } from '@/shared/components/ui/empty-state';
import {
  buildTree,
  FileConflictDialog,
  FileTreeContextMenu,
  FileTreePanel,
  FileManagementDialogs,
  FileManagementSidebarWorkflow,
  composeFileConflictTransports,
  createLocalFileConflictTransport,
  isStaleFileTreeRequestError,
  parseFileTree,
  useFileTreeState,
  useFileManagementContextMenuBuilder,
  useFileConflictController,
  type FileManagementDialogState,
  type FileManagementSidebarInteractionState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import {
  FileViewerWorkbench,
  useFileViewerTabs,
  type FileViewerWorkbenchAdapter,
} from '@/shared/components/file-workbench/viewer-entry';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { createLogger } from '@/shared/services/logger';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import {
  createPackageFileEntry,
  createSkillEntry,
  deletePackageFileEntry,
  deleteSkillEntry,
  getPackage,
  listPackageFilesTree,
  listSkillTree,
  loadPackageFile,
  loadSkillFile,
  movePackageFileEntry,
  moveSkillEntry,
  savePackageFile,
  saveSkillFile,
  type MarketplaceTextFileResource,
  type MarketplaceFileConflictPayload,
  type MarketplaceSkillFileConflictPayload,
} from '../../../api/marketplaceApi';
import {
  buildChildPath,
  getContextParentPath,
  isManagedFileRootPath,
  marketplaceContextMenuFeatures,
  renamePath,
  sortEntries,
  toFileTreeNode,
  toResourceEntries,
  type MarketplaceFileResourceType,
  type ResourceEntry,
} from '../marketplaceFileResourceModel';
import type { MarketplacePackageMutationResult } from '../../../model/marketplaceMutation';
import { MarketplaceResourceLoadError } from '../../../components/MarketplaceResourceLoadError';
import { useMarketplaceResourceSession } from '../../../model/marketplaceResourceSession';
import {
  MarketplaceShellAdapter,
  type MarketplaceShellColumnSurface,
  type MarketplaceShellMainSurface,
} from '../../../components/MarketplaceShellAdapter';
import { useMarketplaceVersionControlSession } from '@/shared/version-control';
import {
  createMarketplaceFileConflictTransport,
  createMarketplaceSkillFileConflictTransport,
} from './marketplaceFileConflictTransport';

const logger = createLogger('MarketplaceFileResourcePage');

interface MarketplaceFileResourcePageProps {
  title: string;
  resourceType: MarketplaceFileResourceType;
  packageDetail: MarketplacePackageDetail;
  onMutation: (result: MarketplacePackageMutationResult) => Promise<void>;
  renderSurface?: (surface: MarketplaceFileResourceRenderSurface) => React.ReactNode;
}

export interface MarketplaceFileResourceRenderSurface {
  kind: 'regions';
  navigator: MarketplaceShellColumnSurface;
  main: MarketplaceShellMainSurface;
}

interface MarketplaceFileTreeSidebarBodyProps {
  entries: ResourceEntry[];
  syncError: boolean;
  resourceType: MarketplaceFileResourceType;
  treeState: ReturnType<typeof useFileTreeState>;
  interactionState: FileManagementSidebarInteractionState<FileManagementDialogState>;
  onNodeClick: (node: FileTreeNode, modifier: SelectionModifier) => void;
  onNodeDoubleClick: (node: FileTreeNode) => void;
  onUpload: (targetPath: string, files: File[]) => Promise<void>;
  onCopy: (node: FileTreeNode) => void;
  onPaste: (targetPath: string) => void;
  onExtractArchive: (node: FileTreeNode) => Promise<void>;
  onMove: (sourcePath: string, targetPath: string) => Promise<void>;
  onBatchDelete: (paths: string[]) => void;
  onRefresh: () => void;
  t: (key: string, options?: Record<string, unknown>) => string;
}

export const runMarketplaceUploadBatch = async ({
  files,
  initialRevision,
  upload,
}: {
  files: File[];
  initialRevision: string;
  upload: (file: File, revision: string) => Promise<MarketplacePackageMutationResult>;
}): Promise<MarketplacePackageMutationResult> => {
  const firstFile = files[0];
  if (!firstFile) {
    throw new Error('Marketplace upload batch requires at least one file');
  }
  let lastResult = await upload(firstFile, initialRevision);
  for (const file of files.slice(1)) {
    lastResult = await upload(file, lastResult.revision);
  }
  return lastResult;
};

const MarketplaceFileTreeSidebarBody: React.FC<MarketplaceFileTreeSidebarBodyProps> = ({
  entries,
  syncError,
  resourceType,
  treeState,
  interactionState,
  onNodeClick,
  onNodeDoubleClick,
  onUpload,
  onCopy,
  onPaste,
  onExtractArchive,
  onMove,
  onBatchDelete,
  onRefresh,
  t,
}) => {
  const contextNode = treeState.contextMenu?.node ?? null;
  const contextMenuItems = useFileManagementContextMenuBuilder({
    node: contextNode,
    selectedIds: treeState.selectedIds,
    isPathWritable: path => resourceType !== 'files' || !isManagedFileRootPath(path),
    features: marketplaceContextMenuFeatures(resourceType, contextNode),
    callbacks: {
      onOpen: node => {
        onNodeClick(node, 'none');
      },
      onUpload: () => {
        const targetPath = getContextParentPath(contextNode);
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.onchange = event => {
          const files = (event.target as HTMLInputElement).files;
          if (!files?.length) {
            return;
          }
          void onUpload(targetPath, Array.from(files)).catch((error) => {
            if (isStaleFileTreeRequestError(error)) {
              return;
            }
            logger.error('uploadFilesFailed', { resourceType, targetPath, error });
          });
        };
        input.click();
      },
      onCreateFile: () => {
        interactionState.setDialogState({
          type: 'create-file',
          parentPath: getContextParentPath(contextNode),
        });
      },
      onCreateFolder: () => {
        interactionState.setDialogState({
          type: 'create-folder',
          parentPath: getContextParentPath(contextNode),
        });
      },
      onCopy,
      onCopyPath: path => {
        void navigator.clipboard?.writeText(path);
      },
      onExtractArchive: node => {
        void onExtractArchive(node).catch((error) => {
          if (isStaleFileTreeRequestError(error)) {
            return;
          }
          logger.error('extractArchiveFailed', { resourceType, path: node.path, error });
        });
      },
      onPaste: () => onPaste(getContextParentPath(contextNode)),
      onRename: node => {
        interactionState.setDialogState({ type: 'rename', node });
      },
      onDelete: node => {
        interactionState.setDialogState({ type: 'delete', node });
      },
      onRefresh,
      onClose: treeState.closeContextMenu,
    },
    t,
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      {syncError ? (
        <div
          role="alert"
          className="flex items-center gap-2 border-b border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
        >
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 flex-1">{t('marketplace.common.resourceSyncError')}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-6 shrink-0 px-2 text-xs"
            onClick={onRefresh}
          >
            {t('marketplace.common.actions.retry')}
          </Button>
        </div>
      ) : null}
      <FileTreePanel
        state={treeState}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        onContextMenu={(node, event) => {
          treeState.openContextMenu(event.clientX, event.clientY, node);
        }}
        onDragStart={(node) => interactionState.setDraggingPath(node.path)}
        onDragEnd={() => {
          interactionState.setDraggingPath(null);
          interactionState.setDragOverPath(null);
        }}
        onDragOver={(node, event) => {
          event.preventDefault();
          if (node.type === 'directory') {
            interactionState.setDragOverPath(node.path);
          }
        }}
        onDragLeave={() => interactionState.setDragOverPath(null)}
        onDrop={async (targetNode, event) => {
          event.preventDefault();
          const sourcePath = interactionState.draggingPath;
          if (
            sourcePath
            && targetNode.type === 'directory'
            && sourcePath !== targetNode.path
            && !targetNode.path.startsWith(`${sourcePath}/`)
          ) {
            const fileName = sourcePath.split('/').filter(Boolean).pop() ?? sourcePath;
            const nextPath = buildChildPath(resourceType, targetNode.path, fileName);
            await onMove(sourcePath, nextPath);
          }
          interactionState.setDraggingPath(null);
          interactionState.setDragOverPath(null);
        }}
        isPathWritable={path => resourceType !== 'files' || !isManagedFileRootPath(path)}
        enableSearch={false}
        enableToolbar={false}
        enableMultiSelectBar
        enableDragDrop
        draggingPath={interactionState.draggingPath}
          dragOverPath={interactionState.dragOverPath}
        onBatchDelete={onBatchDelete}
        className="flex-1"
      />
      <FileTreeContextMenu
        contextMenu={treeState.contextMenu}
        items={contextMenuItems}
        onClose={treeState.closeContextMenu}
      />
      {!entries.length ? (
        <div className="border-t px-3 py-2 text-xs text-muted-foreground">
          {t('marketplace.editor.fileResources.empty')}
        </div>
      ) : null}
    </div>
  );
};

export const MarketplaceFileResourcePage: React.FC<MarketplaceFileResourcePageProps> = ({
  title,
  resourceType,
  packageDetail,
  onMutation,
  renderSurface,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const fileTabs = useFileViewerTabs();
  const applyFileTabsChange = fileTabs.applyTabsChange;
  const treeState = useFileTreeState({
    initialNodes: [],
    initialExpandedIds: [],
    initialSelectedId: null,
    enableMultiSelect: true,
  });
  const {
    resetState: resetTreeState,
    selectNode: selectTreeNode,
    setLoading: setTreeLoading,
    setNodes: setTreeNodes,
  } = treeState;
  const [entries, setEntries] = React.useState<ResourceEntry[]>([]);
  const [selectedPath, setSelectedPath] = React.useState<string | null>(null);
  const [contentByPath, setContentByPath] = React.useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState(false);
  const [syncError, setSyncError] = React.useState(false);
  const entriesRef = React.useRef<ResourceEntry[]>([]);
  const [clipboardItem, setClipboardItem] = React.useState<{ path: string; type: 'file' | 'directory' } | null>(null);
  const {
    identityGeneration,
    session,
  } = useMarketplaceResourceSession({
    targetClient: packageDetail.targetClient,
    packageId: packageDetail.packageId,
    resourceType,
  }, packageDetail.revision);

  React.useLayoutEffect(() => {
    setEntries([]);
    setSelectedPath(null);
    setContentByPath({});
    setIsLoading(true);
    setLoadError(false);
    setSyncError(false);
    entriesRef.current = [];
    resetTreeState();
    applyFileTabsChange([]);
  }, [applyFileTabsChange, identityGeneration, resetTreeState]);

  const listEntries = React.useCallback(async () => {
    const result = resourceType === 'skills'
      ? await listSkillTree(packageDetail.targetClient, packageDetail.packageId)
      : await listPackageFilesTree(packageDetail.targetClient, packageDetail.packageId);
    return sortEntries(toResourceEntries(resourceType, parseFileTree(result)));
  }, [packageDetail.packageId, packageDetail.targetClient, resourceType]);

  const loadEntries = React.useCallback(async (preferredPath?: string | null) => {
    setIsLoading(true);
    setTreeLoading(true);
    setLoadError(false);
    await session.query(
      identityGeneration,
      'file-tree',
      listEntries,
      {
        onSuccess: (nextEntries) => {
          entriesRef.current = nextEntries;
          setEntries(nextEntries);
          setLoadError(false);
          setSyncError(false);
          if (!nextEntries.length) {
            setSelectedPath(null);
            return;
          }
          const nextSelected = preferredPath && nextEntries.some((entry) => entry.path === preferredPath)
            ? preferredPath
            : nextEntries.find((entry) => !entry.isDirectory)?.path ?? null;
          setSelectedPath(nextSelected);
        },
        onError: () => {
          if (entriesRef.current.length > 0) {
            setLoadError(false);
            setSyncError(true);
            return;
          }
          setLoadError(true);
          setSyncError(false);
        },
        onSettled: () => {
          setIsLoading(false);
          setTreeLoading(false);
        },
      },
    );
    return entriesRef.current;
  }, [identityGeneration, listEntries, session, setTreeLoading]);

  const versionControl = useMarketplaceVersionControlSession({ isGitRepo: true });
  const refreshAfterConflictSettlement = React.useCallback(async (
    preferredPath: string | null | undefined,
  ) => {
    try {
      const refreshedPackage = await getPackage(packageDetail.targetClient, packageDetail.packageId);
      await onMutation({
        success: true,
        path: preferredPath ?? selectedPath ?? '',
        revision: refreshedPackage.revision,
        ownerFilePath: null,
        baseEntryFingerprint: null,
      });
    } catch (error) {
      logger.error('fileConflictRevisionRefreshFailed', { error, resourceType });
    }

    await Promise.allSettled([
      loadEntries(preferredPath ?? selectedPath),
      versionControl.refresh(queryClient, ['changes', 'history']),
    ]);
  }, [
    loadEntries,
    onMutation,
    packageDetail.packageId,
    packageDetail.targetClient,
    queryClient,
    resourceType,
    selectedPath,
    versionControl,
  ]);
  const reloadOpenFileTabs = React.useCallback(async (paths: string[]) => {
    await Promise.allSettled(paths.map(async (path) => {
      if (!fileTabs.tabs.some((tab) => tab.path === path)) {
        return;
      }
      try {
        const loaded: MarketplaceTextFileResource = await session.run(
          identityGeneration,
          `file-content-reload:${path}`,
          () => (
            resourceType === 'skills'
              ? loadSkillFile(packageDetail.targetClient, packageDetail.packageId, path)
              : loadPackageFile(packageDetail.targetClient, packageDetail.packageId, path)
          ),
        );
        setContentByPath((current) => ({ ...current, [path]: loaded.content }));
        fileTabs.replaceFileContent(path, loaded.content);
      } catch (error) {
        fileTabs.removePaths([path]);
        logger.error('fileTabReloadFailed', { error, path, resourceType });
      }
    }));
  }, [
    fileTabs.removePaths,
    fileTabs.replaceFileContent,
    fileTabs.tabs,
    identityGeneration,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    session,
  ]);

  const runDestinationMutation = React.useCallback(async (
    operation: () => Promise<MarketplacePackageMutationResult>,
  ): Promise<MarketplacePackageMutationResult> => {
    let committedResult: MarketplacePackageMutationResult | null = null;
    await session.mutate(
      identityGeneration,
      'file-destination-mutation',
      operation,
      async (result) => {
        committedResult = result;
        await onMutation(result);
        await loadEntries(result.path);
      },
    );
    if (!committedResult) throw new Error('FILE_DESTINATION_MUTATION_NOT_COMMITTED');
    return committedResult;
  }, [identityGeneration, loadEntries, onMutation, session]);
  const localFileConflictOptions = React.useMemo(() => ({
    findEntry: (path: string) => entries.find((entry) => entry.path === path) ?? null,
    refreshTree: () => loadEntries(selectedPath),
    createEntry: (path: string, entryType: 'file' | 'directory', content: string) => runDestinationMutation(
      () => resourceType === 'skills'
        ? createSkillEntry(packageDetail.targetClient, packageDetail.packageId, {
            revision: session.revision,
            path,
            type: entryType,
            content: entryType === 'file' ? content : undefined,
          })
        : createPackageFileEntry(packageDetail.targetClient, packageDetail.packageId, {
            revision: session.revision,
            path,
            type: entryType,
            content: entryType === 'file' ? content : undefined,
          }),
    ),
    moveEntry: (sourcePath: string, targetPath: string) => runDestinationMutation(
      () => resourceType === 'skills'
        ? moveSkillEntry(packageDetail.targetClient, packageDetail.packageId, {
            revision: session.revision,
            previousPath: sourcePath,
            nextPath: targetPath,
          })
        : movePackageFileEntry(packageDetail.targetClient, packageDetail.packageId, {
            revision: session.revision,
            previousPath: sourcePath,
            nextPath: targetPath,
          }),
    ),
    deleteEntry: (path: string, _recursive: boolean) => runDestinationMutation(
      () => resourceType === 'skills'
        ? deleteSkillEntry(packageDetail.targetClient, packageDetail.packageId, path, session.revision)
        : deletePackageFileEntry(packageDetail.targetClient, packageDetail.packageId, path, session.revision),
    ),
  }), [
    entries,
    loadEntries,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    runDestinationMutation,
    selectedPath,
    session.revision,
  ]);
  const localFileConflictTransport = React.useMemo(
    () => resourceType === 'skills'
      ? createLocalFileConflictTransport<MarketplaceSkillFileConflictPayload>({
          ...localFileConflictOptions,
          getPayload: (payload) => payload,
        })
      : createLocalFileConflictTransport<MarketplaceFileConflictPayload>({
          ...localFileConflictOptions,
          getPayload: (payload) => payload,
        }),
    [localFileConflictOptions, resourceType],
  );
  const fileConflictTransport = React.useMemo(
    () => resourceType === 'skills'
      ? composeFileConflictTransports(
          createMarketplaceSkillFileConflictTransport(
            packageDetail.targetClient,
            packageDetail.packageId,
            session.revision,
          ),
          localFileConflictTransport,
        )
      : composeFileConflictTransports(
          createMarketplaceFileConflictTransport(packageDetail.targetClient, packageDetail.packageId),
          localFileConflictTransport,
        ),
    [localFileConflictTransport, packageDetail.packageId, packageDetail.targetClient, resourceType, session.revision],
  );
  const destinationConflictRef = React.useRef<{ operation: 'create' | 'move'; sourcePath?: string } | null>(null);
  const fileConflictController = useFileConflictController({
    transport: fileConflictTransport,
    onCompleted: (result) => {
      const successfulItems = result.items.filter((item) => (
        item.finalPath !== null
        && ['created', 'kept-both', 'replaced', 'merged'].includes(item.status)
      ));
      const finalItem = successfulItems[0];
      const destinationOperation = destinationConflictRef.current;
      destinationConflictRef.current = null;
      const replacedPaths = successfulItems
        .filter((item) => item.status === 'replaced' && item.finalPath)
        .map((item) => item.finalPath!);
      void (async () => {
        if (
          destinationOperation?.operation === 'move'
          && destinationOperation.sourcePath
          && finalItem?.finalPath
          && result.failed === 0
        ) {
          const canonicalName = finalItem.finalPath.split('/').filter(Boolean).at(-1) ?? finalItem.finalPath;
          fileTabs.renamePath(destinationOperation.sourcePath, finalItem.finalPath, canonicalName);
        }
        await refreshAfterConflictSettlement(
          finalItem?.finalPath ?? selectedPath,
        );
        await reloadOpenFileTabs(replacedPaths);
        result.items
          .filter((item) => item.status === 'failed')
          .forEach((item) => {
            toast({
              title: t('common.fileOperations.error.fileOperationFailed'),
              description: item.error ?? item.sourcePath,
              variant: 'destructive',
            });
          });
        if (finalItem?.finalPath && result.failed === 0) setSelectedPath(finalItem.finalPath);
        if (result.failed === 0) setClipboardItem(null);
      })();
    },
    onError: (error, stage) => {
      destinationConflictRef.current = null;
      if (stage === 'execute') {
        void refreshAfterConflictSettlement(selectedPath);
        toast({
          title: t('common.fileOperations.error.fileOperationFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
        return;
      }
      logger.error('fileConflictPreflightFailed', { error, resourceType });
    },
    onCancelled: () => {
      destinationConflictRef.current = null;
    },
  });

  React.useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  React.useEffect(() => {
    setTreeNodes(buildTree(entries.map((entry) => toFileTreeNode(entry, resourceType))));
  }, [entries, resourceType, setTreeNodes]);

  React.useEffect(() => {
    if (selectedPath) {
      selectTreeNode(selectedPath);
    }
  }, [selectTreeNode, selectedPath]);

  const loadContent = React.useCallback(async (path: string): Promise<string> => {
    const loaded: MarketplaceTextFileResource = await session.run(
      identityGeneration,
      `file-content:${path}`,
      () => (
        resourceType === 'skills'
          ? loadSkillFile(packageDetail.targetClient, packageDetail.packageId, path)
          : loadPackageFile(packageDetail.targetClient, packageDetail.packageId, path)
      ),
    );
    setContentByPath((current) => ({
      ...current,
      [path]: loaded.content,
    }));
    return loaded.content;
  }, [
    identityGeneration,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    session,
  ]);

  const openFileEntry = React.useCallback(async (entry: ResourceEntry) => {
    if (entry.isDirectory) {
      return;
    }
    try {
      const content = entry.path in contentByPath
        ? contentByPath[entry.path]
        : await loadContent(entry.path);
      fileTabs.openFile(toFileTreeNode(entry, resourceType), content);
    } catch (error) {
      if (!isStaleFileTreeRequestError(error)) {
        throw error;
      }
    }
  }, [contentByPath, fileTabs, loadContent, resourceType]);

  React.useEffect(() => {
    if (!selectedPath) {
      return;
    }
    const selectedEntry = entries.find((entry) => entry.path === selectedPath);
    if (!selectedEntry || selectedEntry.isDirectory || selectedPath in contentByPath) {
      return;
    }
    void openFileEntry(selectedEntry);
  }, [contentByPath, entries, openFileEntry, selectedPath]);

  const selectedEntry = entries.find((entry) => entry.path === selectedPath) ?? null;

  const applyMutation = React.useCallback(async (
    operation: () => Promise<MarketplacePackageMutationResult>,
    options: {
      onCurrent?(result: MarketplacePackageMutationResult): void | Promise<void>;
      preferredPath?(result: MarketplacePackageMutationResult): string | null | undefined;
    } = {},
  ) => {
    await session.mutate(
      identityGeneration,
      'file-mutation',
      operation,
      async (result) => {
        await options.onCurrent?.(result);
        await onMutation(result);
        await loadEntries(options.preferredPath?.(result));
      },
    );
  }, [identityGeneration, loadEntries, onMutation, session]);

  const handleCreateEntry = React.useCallback(async (
    entryType: 'file' | 'directory',
    parentPath: string,
    name: string,
  ) => {
    const path = buildChildPath(resourceType, parentPath, name);
    if (!path) {
      return;
    }
    destinationConflictRef.current = { operation: 'create' };
    const result = await fileConflictController.start({
      operation: 'create',
      targetPath: path,
      sources: [{ sourcePath: path, entryType }],
      archivePath: null,
    }, {
      files: [],
      sourcePath: path,
      entryType,
      content: entryType === 'file' ? '' : undefined,
    });
    if (!result) return { suppressSuccessToast: true };
  }, [
    fileConflictController,
    resourceType,
  ]);

  const handleDeleteEntry = React.useCallback(async (path: string) => {
    await applyMutation(
      () => (
        resourceType === 'skills'
          ? deleteSkillEntry(
              packageDetail.targetClient,
              packageDetail.packageId,
              path,
              session.revision,
            )
          : deletePackageFileEntry(
              packageDetail.targetClient,
              packageDetail.packageId,
              path,
              session.revision,
            )
      ),
      {
        onCurrent: (result) => {
          setSelectedPath(null);
          setContentByPath((current) => {
            const next = { ...current };
            Object.keys(next)
              .filter((currentPath) => (
                currentPath === result.path || currentPath.startsWith(`${result.path}/`)
              ))
              .forEach((currentPath) => delete next[currentPath]);
            return next;
          });
          fileTabs.removePaths([result.path]);
        },
        preferredPath: () => null,
      },
    );
  }, [
    applyMutation,
    fileTabs,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    session,
  ]);

  const handleBatchDeleteEntries = React.useCallback(async (paths: string[]) => {
    const failures: Array<{ path: string; error: string }> = [];
    for (const path of paths) {
      try {
        const result = await session.run(
          identityGeneration,
          `file-batch-delete:${path}`,
          () => (
            resourceType === 'skills'
              ? deleteSkillEntry(
                  packageDetail.targetClient,
                  packageDetail.packageId,
                  path,
                  session.revision,
                )
              : deletePackageFileEntry(
                  packageDetail.targetClient,
                  packageDetail.packageId,
                  path,
                  session.revision,
                )
          ),
        );
        session.acceptMutation(identityGeneration, result);
        try {
          await onMutation(result);
        } catch (error) {
          logger.error('batchDeleteMutationRefreshFailed', { error, path, resourceType });
        }
        setContentByPath((current) => {
          const next = { ...current };
          Object.keys(next)
            .filter((currentPath) => (
              currentPath === result.path || currentPath.startsWith(`${result.path}/`)
            ))
            .forEach((currentPath) => delete next[currentPath]);
          return next;
        });
        fileTabs.removePaths([result.path]);
      } catch (error) {
        failures.push({
          path,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    await Promise.allSettled([
      loadEntries(selectedPath),
      versionControl.refresh(queryClient, ['changes', 'history']),
    ]);
    failures.forEach((failure) => {
      toast({
        title: t('common.fileOperations.error.fileOperationFailed'),
        description: failure.error || failure.path,
        variant: 'destructive',
      });
    });
    if (!failures.length) {
      treeState.clearSelection();
    }
  }, [
    fileTabs.removePaths,
    identityGeneration,
    loadEntries,
    onMutation,
    packageDetail.packageId,
    packageDetail.targetClient,
    queryClient,
    resourceType,
    selectedPath,
    session,
    t,
    toast,
    treeState,
    versionControl,
  ]);

  const handleRenameEntry = React.useCallback(async (entry: FileTreeNode, nextName: string) => {
    if (!nextName || nextName === entry.name) {
      return;
    }
    const nextPath = renamePath(entry.path, nextName);
    destinationConflictRef.current = { operation: 'move', sourcePath: entry.path };
    const result = await fileConflictController.start({
      operation: 'move',
      targetPath: nextPath,
      sources: [{ sourcePath: entry.path, entryType: entry.type }],
      archivePath: null,
    }, {
      files: [],
      sourcePath: entry.path,
      entryType: entry.type,
    });
    if (!result) return { suppressSuccessToast: true };
  }, [
    fileConflictController,
  ]);

  const handleMoveEntry = React.useCallback(async (sourcePath: string, targetPath: string) => {
    const sourceEntry = entries.find((entry) => entry.path === sourcePath);
    if (!sourceEntry || sourcePath === targetPath) return;
    destinationConflictRef.current = { operation: 'move', sourcePath };
    await fileConflictController.start({
      operation: 'move',
      targetPath,
      sources: [{ sourcePath, entryType: sourceEntry.type }],
      archivePath: null,
    }, {
      files: [],
      sourcePath,
      entryType: sourceEntry.type,
    });
  }, [entries, fileConflictController]);

  const handleWorkbenchSave = React.useCallback(async (path: string, content: string) => {
    const entry = entries.find((item) => item.path === path);
    if (entry?.isDirectory) {
      return;
    }
    await applyMutation(
      () => (
        resourceType === 'skills'
          ? saveSkillFile(packageDetail.targetClient, packageDetail.packageId, path, {
              revision: session.revision,
              content,
            })
          : savePackageFile(packageDetail.targetClient, packageDetail.packageId, path, {
              revision: session.revision,
              content,
            })
      ),
      {
        onCurrent: (result) => {
          setContentByPath((current) => ({
            ...current,
            [result.path]: content,
          }));
        },
        preferredPath: result => result.path,
      },
    );
  }, [
    applyMutation,
    entries,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    session,
  ]);

  const handleUploadFiles = React.useCallback(async (targetPath: string, files: File[]) => {
    if (!files.length) {
      return;
    }
    await fileConflictController.start({
      operation: 'upload',
      targetPath: targetPath || (resourceType === 'skills' ? 'skills' : '/'),
      sources: files.map((file) => ({ sourcePath: file.name, entryType: 'file' })),
      archivePath: null,
    }, { files, revision: session.revision });
  }, [
    applyMutation,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    session,
    fileConflictController,
  ]);

  const handleExtractArchive = React.useCallback(async (node: FileTreeNode) => {
    const targetPath = node.path.split('/').slice(0, -1).join('/') || (resourceType === 'skills' ? 'skills' : '/');
    await fileConflictController.start({
      operation: 'extract',
      targetPath,
      sources: null,
      archivePath: node.path,
    }, { revision: session.revision });
  }, [
    applyMutation,
    packageDetail.packageId,
    packageDetail.targetClient,
    resourceType,
    session,
    fileConflictController,
  ]);

  const handlePasteEntry = React.useCallback(async (targetPath: string) => {
    if (!clipboardItem || resourceType !== 'files') return;
    await fileConflictController.start({
      operation: 'paste',
      targetPath: targetPath || '/',
      sources: [{ sourcePath: clipboardItem.path, entryType: clipboardItem.type }],
      archivePath: null,
    }, { revision: session.revision });
  }, [clipboardItem, fileConflictController, resourceType, session.revision]);

  const openUploadPicker = React.useCallback((targetPath: string) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = event => {
      const files = (event.target as HTMLInputElement).files;
      if (!files?.length) {
        return;
      }
      void handleUploadFiles(targetPath, Array.from(files)).catch((error) => {
        if (isStaleFileTreeRequestError(error)) {
          return;
        }
        logger.error('uploadFilesFailed', { resourceType, targetPath, error });
      });
    };
    input.click();
  }, [handleUploadFiles, resourceType]);

  const viewerAdapter = React.useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async (path) => (
      path in contentByPath ? contentByPath[path] : loadContent(path)
    ),
    saveFile: handleWorkbenchSave,
    copyPath: async (path) => {
      await navigator.clipboard?.writeText(path);
    },
    revealInTree: (path) => {
      setSelectedPath(path);
    },
  }), [contentByPath, handleWorkbenchSave, loadContent]);

  const handleOpenPath = React.useCallback((path: string) => {
    const entry = entries.find((item) => item.path === path && !item.isDirectory);
    if (!entry) {
      return;
    }
    setSelectedPath(path);
    void openFileEntry(entry);
  }, [entries, openFileEntry]);

  const handleTreeNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    setSelectedPath(node.path);
    void openFileEntry({
      path: node.path,
      name: node.name,
      type: node.type,
      isDirectory: node.type === 'directory',
    });
  }, [openFileEntry, treeState]);

  const handleTreeNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    if (node.type === 'directory') {
      treeState.toggleNode(node.path);
      return;
    }
    setSelectedPath(node.path);
    void openFileEntry({
      path: node.path,
      name: node.name,
      type: 'file',
      isDirectory: false,
    });
  }, [openFileEntry, treeState]);

  const sidebarManager = React.useMemo(() => ({
    state: treeState,
    loadTree: async () => {
      await loadEntries(selectedPath);
    },
  }), [loadEntries, selectedPath, treeState]);
  const HeaderIcon = resourceType === 'skills' ? Wand2 : FileArchive;

  if (loadError) {
    return <MarketplaceResourceLoadError onRetry={() => { void loadEntries(); }} />;
  }

  const navigator = {
    content: ({ collapsed }: { collapsed: boolean }) => collapsed ? null : (
      <div className="flex h-full min-h-0 flex-col">
        <FileManagementSidebarWorkflow
          manager={sidebarManager}
          title={title}
          searchPlaceholder={t('marketplace.editor.fileManager.search.placeholder')}
          headerIcon={HeaderIcon}
          showHeader={false}
          showToolbar
          loadEnabled={false}
          capabilities={{
            canCreateFile: true,
            canCreateFolder: true,
            canUpload: true,
          }}
          isCollapsed={false}
          onToggleCollapse={() => undefined}
          onCreateFile={(_, interactionState) => {
            interactionState.setDialogState({ type: 'create-file', parentPath: '' });
          }}
          onCreateFolder={(_, interactionState) => {
            interactionState.setDialogState({ type: 'create-folder', parentPath: '' });
          }}
          onUpload={() => {
            openUploadPicker('');
          }}
          renderBody={({ interactionState }) => (
            <MarketplaceFileTreeSidebarBody
              entries={entries}
              syncError={syncError}
              resourceType={resourceType}
              treeState={treeState}
              interactionState={interactionState as FileManagementSidebarInteractionState<FileManagementDialogState>}
              onNodeClick={handleTreeNodeClick}
              onNodeDoubleClick={handleTreeNodeDoubleClick}
              onUpload={handleUploadFiles}
              onCopy={(node) => setClipboardItem({ path: node.path, type: node.type })}
              onPaste={(targetPath) => { void handlePasteEntry(targetPath); }}
              onExtractArchive={handleExtractArchive}
              onMove={handleMoveEntry}
              onBatchDelete={handleBatchDeleteEntries}
              onRefresh={() => { void loadEntries(selectedPath); }}
              t={t}
            />
          )}
          dialogs={({ interactionState }) => (
            <FileManagementDialogs
              dialogState={interactionState.dialogState as FileManagementDialogState}
              onClose={interactionState.closeDialog}
              onCreateFile={async (name) => {
                const dialogState = interactionState.dialogState as FileManagementDialogState;
                if (dialogState?.type !== 'create-file') {
                  return;
                }
                await handleCreateEntry('file', dialogState.parentPath, name);
              }}
              onCreateFolder={async (name) => {
                const dialogState = interactionState.dialogState as FileManagementDialogState;
                if (dialogState?.type !== 'create-folder') {
                  return;
                }
                await handleCreateEntry('directory', dialogState.parentPath, name);
              }}
              onRename={async (name) => {
                const dialogState = interactionState.dialogState as FileManagementDialogState;
                if (dialogState?.type !== 'rename') {
                  return;
                }
                await handleRenameEntry(dialogState.node, name);
              }}
              onDelete={async () => {
                const dialogState = interactionState.dialogState as FileManagementDialogState;
                if (dialogState?.type !== 'delete') {
                  return;
                }
                await handleDeleteEntry(dialogState.node.path);
              }}
              onBatchDelete={async () => {
                const dialogState = interactionState.dialogState as FileManagementDialogState;
                if (dialogState?.type !== 'batch-delete') {
                  return;
                }
                await handleBatchDeleteEntries(dialogState.nodes.map((node) => node.path));
              }}
              getAffectedUnsavedTabsCount={(paths) => fileTabs.tabs.filter((tab) => (
                tab.isModified
                && paths.some((path) => tab.path === path || tab.path.startsWith(`${path}/`))
              )).length}
            />
          )}
        />
      </div>
    ),
    accessibleLabel: title,
    preset: 'navigator',
    header: {
      leading: <HeaderIcon className="h-4 w-4 shrink-0 text-sidebar-primary" />,
      title,
      actions: (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => { void loadEntries(selectedPath); }}
            disabled={treeState.isLoading}
            aria-label={t('common.fileTree.contextMenu.refresh')}
            title={t('common.fileTree.contextMenu.refresh')}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${treeState.isLoading ? 'animate-spin' : ''}`} />
          </Button>
        ),
    },
  } satisfies MarketplaceFileResourceRenderSurface['navigator'];

  const main = {
    content: (
      <>
        <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
            {isLoading ? (
              <LoadingSpinner text={t('marketplace.common.loading')} className="h-full" />
            ) : fileTabs.tabs.length ? (
              <FileViewerWorkbench
                tabs={fileTabs.tabs}
                activeTabId={fileTabs.activeTabId}
                adapter={viewerAdapter}
                capabilities={{
                  canEdit: true,
                  canSave: true,
                  canCopyPath: true,
                  canRevealInTree: true,
                  canCloseTabs: true,
                }}
                isPathWritable={(path) => !entries.find((entry) => entry.path === path)?.isDirectory}
                onOpenPath={handleOpenPath}
                onTabsChange={fileTabs.applyTabsChange}
                onActiveTabChange={fileTabs.setActiveTabId}
              />
            ) : selectedEntry?.isDirectory ? (
              <EmptyState
                icon={Folder}
                title={t('marketplace.editor.fileResources.directorySelected')}
              />
            ) : (
              <EmptyState
                icon={FileText}
                title={t('marketplace.editor.fileManager.viewer.noFile')}
              />
            )}
        </div>
        <FileConflictDialog
          open={fileConflictController.open}
          operation={fileConflictController.operation}
          conflicts={fileConflictController.conflicts}
          defaultStrategy={fileConflictController.defaultStrategy}
          itemStrategies={fileConflictController.itemStrategies}
          pending={fileConflictController.pending}
          error={fileConflictController.error}
          getAffectedUnsavedTabsCount={(paths) => fileTabs.tabs.filter((tab) => (
            tab.isModified
            && paths.some((path) => tab.path === path || tab.path.startsWith(`${path}/`))
          )).length}
          onDefaultStrategyChange={fileConflictController.setDefaultStrategy}
          onItemStrategyChange={fileConflictController.setItemStrategy}
          onCancel={fileConflictController.cancel}
          onConfirm={fileConflictController.confirm}
        />
      </>
    ),
    accessibleLabel: t('marketplace.detail.viewer.contentRegion'),
  } satisfies MarketplaceFileResourceRenderSurface['main'];

  const surface: MarketplaceFileResourceRenderSurface = {
    kind: 'regions',
    navigator,
    main,
  };

  return renderSurface
    ? renderSurface(surface)
    : <MarketplaceShellAdapter surface={surface} />;
};
