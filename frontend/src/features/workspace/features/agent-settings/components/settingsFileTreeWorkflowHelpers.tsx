import React, { useCallback } from 'react';
import {
  FileManagementDialogs,
  FileConflictDialog,
  FileTreeContextMenu,
  composeFileConflictTransports,
  createLocalFileConflictTransport,
  FileTreePanel,
  useFileConflictController,
  useFileManagementContextMenuBuilder,
  useFileTreeManager,
  type FileManagementSidebarInteractionState,
  type FileConflictWorkflowTransport,
  type FileOperationDialogResult,
  type FileTreeNode as FileTreeNodeType,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { createLogger } from '@/shared/services/logger';
import {
  buildSettingsFileTreeContextMenuFeatures,
  toSettingsFileSelection,
  type SettingsFileSelection,
} from './settingsFileTreeWorkflowModel';

const logger = createLogger('SettingsFileTreeWorkflow');

export interface SettingsFileConflictPayload {
  files: File[];
  sourcePath?: string;
  entryType?: 'file' | 'directory';
  content?: string;
}

export type DialogState = React.ComponentProps<typeof FileManagementDialogs>['dialogState'];
export type SettingsFileTreeManager = ReturnType<typeof useFileTreeManager>;

export interface SettingsDestinationConflictRequest {
  operation: 'create' | 'move';
  targetPath: string;
  sourcePath: string;
  entryType: 'file' | 'directory';
  content?: string;
}

export type StartSettingsDestinationConflict = (
  request: SettingsDestinationConflictRequest,
) => Promise<void | FileOperationDialogResult>;

export const getParentPath = (node: FileTreeNodeType | null | undefined) => {
  if (!node) return '/';
  if (node.type === 'directory') return node.path;
  return node.path.split('/').slice(0, -1).join('/') || '/';
};

export const buildChildPath = (parentPath: string, name: string) =>
  parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;

export const uploadFilesWithPicker = (
  manager: SettingsFileTreeManager,
  loggerContext: Record<string, unknown>,
  targetPath = '',
  startConflict?: (targetPath: string, files: File[]) => Promise<void>,
) => {
  const input = document.createElement('input');
  input.type = 'file';
  input.multiple = true;
  input.onchange = async (event) => {
    const files = (event.target as HTMLInputElement).files;
    if (!files || files.length === 0) return;
    try {
      const selectedFiles = Array.from(files);
      if (startConflict) {
        await startConflict(targetPath, selectedFiles);
      } else {
        await manager.operations.uploadFiles({ targetPath, files: selectedFiles });
        await manager.loadTree();
      }
    } catch (error) {
      logger.error('uploadFailed', { ...loggerContext, error });
    }
  };
  input.click();
};

interface SettingsFileTreeSidebarBodyProps<TScope extends string = string> {
  manager: SettingsFileTreeManager;
  isReadOnly: boolean;
  scope: TScope;
  onSelect: (file: SettingsFileSelection<TScope>) => void;
  interactionState: FileManagementSidebarInteractionState<DialogState>;
  loggerContext: Record<string, unknown>;
  fileConflictTransport?: FileConflictWorkflowTransport<SettingsFileConflictPayload>;
  registerStartUpload?: (handler: ((targetPath: string, files: File[]) => Promise<void>) | null) => void;
  registerStartDestinationConflict?: (handler: StartSettingsDestinationConflict | null) => void;
}

export const SettingsFileTreeSidebarBody = <TScope extends string = string>({
  manager,
  isReadOnly,
  scope,
  onSelect,
  interactionState,
  loggerContext,
  fileConflictTransport,
  registerStartUpload,
  registerStartDestinationConflict,
}: SettingsFileTreeSidebarBodyProps<TScope>) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const selectFile = useCallback((node: FileTreeNodeType) => {
    onSelect(toSettingsFileSelection(node, scope));
  }, [onSelect, scope]);
  const completedOperationRef = React.useRef<'upload' | 'paste' | 'extract' | 'create' | 'move' | null>(null);
  const destinationConflictRef = React.useRef<SettingsDestinationConflictRequest | null>(null);
  const localFileConflictTransport = React.useMemo(() => createLocalFileConflictTransport<SettingsFileConflictPayload>({
    findEntry: (path) => manager.state.flatNodes.find((node) => node.path === path) ?? null,
    refreshTree: manager.loadTree,
    createEntry: (path, entryType, content) => entryType === 'directory'
      ? manager.operations.createDirectory(path)
      : manager.operations.createFile(path, content),
    moveEntry: manager.operations.moveFile,
    deleteEntry: manager.operations.deleteFile,
    getPayload: (payload) => payload,
  }), [manager.loadTree, manager.operations, manager.state.flatNodes]);
  const conflictTransport = React.useMemo(() => fileConflictTransport
    ? composeFileConflictTransports(fileConflictTransport, localFileConflictTransport)
    : localFileConflictTransport, [fileConflictTransport, localFileConflictTransport]);
  const conflictController = useFileConflictController({
    transport: conflictTransport,
    onCompleted: (result) => {
      const successfulItems = result.items.filter((item) => (
        item.finalPath !== null
        && ['created', 'kept-both', 'replaced', 'merged'].includes(item.status)
      ));
      const replacedPaths = successfulItems
        .filter((item) => item.status === 'replaced' && item.finalPath)
        .map((item) => item.finalPath!);
      const finalItem = successfulItems[0];
      const destinationOperation = destinationConflictRef.current;
      destinationConflictRef.current = null;

      void (async () => {
        if (
          destinationOperation?.operation === 'move'
          && finalItem?.finalPath
          && result.failed === 0
        ) {
          manager.editor.remapPath(destinationOperation.sourcePath, finalItem.finalPath);
        }
        await Promise.allSettled([
          manager.loadTree(),
          ...replacedPaths.map((path) => manager.reloadFileTab(path)),
        ]);
        result.items
          .filter((item) => item.status === 'failed')
          .forEach((item) => {
            toast({
              title: t('common.fileOperations.error.fileOperationFailed'),
              description: item.error ?? item.sourcePath,
              variant: 'destructive',
            });
          });
        if (
          finalItem?.finalPath
          && finalItem.type === 'file'
          && result.failed === 0
          && destinationOperation?.operation !== 'move'
        ) {
          selectFile({
            id: finalItem.finalPath,
            name: finalItem.finalPath.split('/').pop() || finalItem.finalPath,
            path: finalItem.finalPath,
            type: 'file',
          });
        }
        completedOperationRef.current = null;
      })();
    },
    onCancelled: () => {
      completedOperationRef.current = null;
      destinationConflictRef.current = null;
    },
    onError: (error, stage) => {
      if (stage === 'execute') return;
      completedOperationRef.current = null;
      destinationConflictRef.current = null;
      toast({
        title: t('common.fileOperations.error.fileOperationFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    },
  });

  const startUploadConflict = useCallback(async (targetPath: string, files: File[]) => {
    completedOperationRef.current = 'upload';
    if (!fileConflictTransport) {
      await manager.operations.uploadFiles({ targetPath, files });
      await manager.loadTree();
      return;
    }
    await conflictController.start({
      operation: 'upload',
      targetPath: targetPath || '/',
      sources: files.map((file) => ({ sourcePath: file.name, entryType: 'file' })),
      archivePath: null,
    }, { files });
  }, [conflictController, fileConflictTransport, manager.operations, manager.loadTree]);

  const startExtractConflict = useCallback(async (node: FileTreeNodeType) => {
    completedOperationRef.current = 'extract';
    if (!fileConflictTransport) return;
    await conflictController.start({
      operation: 'extract',
      targetPath: getParentPath(node),
      sources: null,
      archivePath: node.path,
    }, { files: [] });
  }, [conflictController, fileConflictTransport]);

  React.useEffect(() => {
    registerStartUpload?.(startUploadConflict);
    return () => registerStartUpload?.(null);
  }, [registerStartUpload, startUploadConflict]);

  const startDestinationConflict = useCallback(async (
    request: SettingsDestinationConflictRequest,
  ): Promise<void | FileOperationDialogResult> => {
    completedOperationRef.current = request.operation;
    destinationConflictRef.current = request;
    const result = await conflictController.start({
      operation: request.operation,
      targetPath: request.targetPath,
      sources: [{ sourcePath: request.sourcePath, entryType: request.entryType }],
      archivePath: null,
    }, {
      files: [],
      sourcePath: request.sourcePath,
      entryType: request.entryType,
      content: request.content,
    });
    if (!result) return { suppressSuccessToast: true };
    return undefined;
  }, [conflictController]);

  React.useEffect(() => {
    registerStartDestinationConflict?.(startDestinationConflict);
    return () => registerStartDestinationConflict?.(null);
  }, [registerStartDestinationConflict, startDestinationConflict]);

  const handleSelectNode = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      selectFile(node);
    }
  }, [manager.state, selectFile]);

  const contextMenuItems = useFileManagementContextMenuBuilder({
    node: manager.state.contextMenu?.node || null,
    readOnly: isReadOnly,
    selectedIds: manager.state.selectedIds,
    features: buildSettingsFileTreeContextMenuFeatures(isReadOnly),
    callbacks: {
      onView: selectFile,
      onUpload: () => {
        if (isReadOnly) return;
        const targetPath = manager.state.contextMenu?.node?.type === 'directory'
          ? manager.state.contextMenu.node.path
          : '';
        uploadFilesWithPicker(manager, loggerContext, targetPath, startUploadConflict);
      },
      onCreateFile: () => {
        if (isReadOnly) return;
        interactionState.setDialogState({ type: 'create-file', parentPath: getParentPath(manager.state.contextMenu?.node) });
      },
      onExtractArchive: node => {
        if (isReadOnly) return;
        void startExtractConflict(node).catch((error) => {
          logger.error('extractArchiveFailed', { ...loggerContext, error });
        });
      },
      onCreateFolder: () => {
        if (isReadOnly) return;
        interactionState.setDialogState({ type: 'create-folder', parentPath: getParentPath(manager.state.contextMenu?.node) });
      },
      onCopyPath: (path) => {
        void navigator.clipboard.writeText(path).catch((error) => {
          logger.error('copyPathFailed', { ...loggerContext, error });
        });
      },
      onRename: (node) => {
        if (isReadOnly) return;
        interactionState.setDialogState({ type: 'rename', node });
      },
      onDelete: (node) => {
        if (isReadOnly) return;
        interactionState.setDialogState({ type: 'delete', node });
      },
      onClose: manager.state.closeContextMenu,
    },
    t,
  });

  return (
    <>
      <FileTreePanel
        state={manager.state}
        onNodeClick={handleSelectNode}
        onNodeDoubleClick={(node) => {
          if (node.type === 'file') {
            selectFile(node);
          }
        }}
        onContextMenu={(node, event) => manager.state.openContextMenu(event.clientX, event.clientY, node)}
        onDragStart={(node, event) => {
          if (isReadOnly) return;
          interactionState.setDraggingPath(node.path);
          event.dataTransfer.effectAllowed = 'move';
          event.dataTransfer.setData('text/plain', node.path);
        }}
        onDragEnd={() => {
          interactionState.setDraggingPath(null);
          interactionState.setDragOverPath(null);
        }}
        onDragOver={(node, event) => {
          if (isReadOnly || node.type !== 'directory') return;
          event.preventDefault();
          event.dataTransfer.dropEffect = 'move';
          interactionState.setDragOverPath(node.path);
        }}
        onDragLeave={() => interactionState.setDragOverPath(null)}
        onDrop={async (node, event) => {
          if (isReadOnly || node.type !== 'directory') return;
          event.preventDefault();
          const sourcePath = event.dataTransfer.getData('text/plain');
          if (!sourcePath || sourcePath === node.path || node.path.startsWith(`${sourcePath}/`)) {
            interactionState.setDragOverPath(null);
            return;
          }
          try {
            const fileName = sourcePath.split('/').pop() || sourcePath;
            const targetPath = buildChildPath(node.path, fileName);
            const sourceNode = manager.state.flatNodes.find((candidate) => candidate.path === sourcePath);
            if (!sourceNode) return;
            await startDestinationConflict({
              operation: 'move',
              sourcePath,
              targetPath,
              entryType: sourceNode.type,
            });
          } catch (error) {
            logger.error('moveFailed', { ...loggerContext, error });
          } finally {
            interactionState.setDragOverPath(null);
            interactionState.setDraggingPath(null);
          }
        }}
        onPaste={(files) => {
          if (isReadOnly) return;
          void startUploadConflict('', files);
        }}
        onBatchDelete={(paths) => {
          if (isReadOnly) return;
          const nodes = paths.map((path) => (
            manager.state.flatNodes.find((node) => node.path === path) ?? {
              id: path,
              name: path.split('/').pop() || path,
              path,
              type: 'file' as const,
            }
          ));
          interactionState.setDialogState({ type: 'batch-delete', nodes });
        }}
        enableSearch={false}
        enableToolbar={false}
        enableMultiSelectBar={!isReadOnly}
        enableDragDrop={!isReadOnly}
        draggingPath={interactionState.draggingPath}
        dragOverPath={interactionState.dragOverPath}
        onRefresh={() => { void manager.loadTree(); }}
        className="flex-1"
      />
      <FileTreeContextMenu
        contextMenu={manager.state.contextMenu}
        items={contextMenuItems}
        onClose={manager.state.closeContextMenu}
      />
      <FileConflictDialog
        open={conflictController.open}
        operation={conflictController.operation}
        conflicts={conflictController.conflicts}
        defaultStrategy={conflictController.defaultStrategy}
        itemStrategies={conflictController.itemStrategies}
        pending={conflictController.pending}
        error={conflictController.error}
        getAffectedUnsavedTabsCount={(paths) => manager.editor.tabs.filter((tab) => (
          tab.isModified
          && paths.some((path) => tab.path === path || tab.path.startsWith(`${path}/`))
        )).length}
        onDefaultStrategyChange={conflictController.setDefaultStrategy}
        onItemStrategyChange={conflictController.setItemStrategy}
        onCancel={conflictController.cancel}
        onConfirm={conflictController.confirm}
      />
    </>
  );
};
