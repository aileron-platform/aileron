export type {
  FileTreeNode,
  FileTreeDataAdapter,
  FileContentPayload,
  FileContentResult,
  FileUpdateOptions,
  FileOperationType,
  FileOperationRequest,
  FileOperationResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileTab,
  SelectionModifier,
  ContextMenuState,
  FileUploadOptions,
  FileDownloadOptions,
} from './types';

export {
  getFileOperationResponseRevision,
  parseFileContent,
  parseFileTree,
} from './adapters/fileResponseAdapter';
export type { FileContent } from './adapters/fileResponseAdapter';
export {
  toFileWorkbenchTab,
  type FileWorkbenchTabSource,
} from './adapters/fileWorkbenchTabAdapter';

export {
  WORKSPACE_FILE_REFERENCE_MIME,
  toWorkspaceFileReferencePath,
} from './dragPayload';

export {
  findNodeByPath,
  filterNodesBySearch,
  flattenTree,
  buildTree,
  getParentPath,
  getFileExtension,
  getAllFileNodes,
  getDescendantPaths,
  sortNodes,
  sortTreeNodes,
} from './model/fileTreeModel';
export {
  formatFileSize,
  isImageFile,
} from './model/fileTypeUtils';
export { getFileIcon } from './model/fileIconUtils';
export {
  createFileTreeResourceIdentity,
  FileTreeAsyncCoordinator,
  isStaleFileTreeRequestError,
  serializeFileTreeResourceIdentity,
  StaleFileTreeRequestError,
} from './model/fileTreeAsyncCoordinator';
export type {
  FileTreeAsyncRequest,
  FileTreeAsyncRequestSettlement,
  FileTreeResourceIdentity,
  FileTreeResourceIdentityValue,
} from './model/fileTreeAsyncCoordinator';

export { FileTreePanel } from './tree/FileTreePanel';
export type { FileTreePanelProps } from './tree/FileTreePanel';

export { ScopeSelector } from './tree/ScopeSelector';
export type { ScopeSelectorProps, ScopeOption } from './tree/ScopeSelector';

export { FileTreeContextMenu } from './tree/FileTreeContextMenu';
export type { FileTreeContextMenuProps } from './tree/FileTreeContextMenu';

export {
  BatchDeleteDialog,
} from './tree/FileOperationDialogs';
export type {
  BatchDeleteDialogProps,
} from './tree/FileOperationDialogs';

export { useFileTreeManager } from './hooks/useFileTreeManager';
export type { UseFileTreeManagerOptions } from './hooks/useFileTreeManager';

export { useFileTreeState } from './hooks/useFileTreeState';
export type { UseFileTreeStateOptions, UseFileTreeStateReturn } from './hooks/useFileTreeState';

export { useFileOperationsWithDialog } from './hooks/useFileOperationsWithDialog';
export type { UseFileOperationsWithDialogOptions, DialogState } from './hooks/useFileOperationsWithDialog';

export type { FileTreeContextMenuConfig } from './hooks/useFileTreeContextMenu';

export { FileTreeSearchBar } from './primitives/FileTreeSearchBar';
export type { FileTreeSearchBarProps } from './primitives/FileTreeSearchBar';

export { ArchiveProgressOverlays } from './archive/ArchiveProgressOverlays';
export type { ExtractProgressState } from './archive/ArchiveProgressOverlays';
export {
  buildArchiveProgressFromStatus,
} from './archive/archiveOperationModel';
export type { ArchiveProgressState } from './archive/archiveOperationModel';
export {
  findLatestPersistedArchiveOperation,
  loadPersistedArchiveOperations,
  markPersistedArchiveDownloadTriggered,
  removePersistedArchiveOperation,
  removePersistedArchiveOperationsForContext,
  removePersistedArchiveOperationsForResource,
  upsertPersistedArchiveOperation,
} from './archive/archivePersistence';
export type { PersistedArchiveOperation } from './archive/archivePersistence';

export { TreeView } from './primitives/TreeView';
export type {
  TreeViewProps,
  TreeViewRenderProps,
  TreeViewRenderHandlers,
  TreeViewRenderState,
} from './primitives/TreeView';

export { FileManagementSidebarWorkflow } from './workflows/FileManagementSidebarWorkflow';
export type {
  FileManagementSidebarInteractionState,
  FileManagementSidebarController,
  FileManagementSidebarWorkflowProps,
  FileManagementTreeManager,
} from './workflows/FileManagementSidebarWorkflow';
export {
  FileManagementDialogs,
  toFileManagementDialogState,
} from './workflows/FileManagementDialogs';
export type {
  FileManagementDialogState,
  FileManagementDialogsProps,
} from './workflows/FileManagementDialogs';
export { FileManagementShell } from './workflows/FileManagementShell';
export type { FileManagementShellProps } from './workflows/FileManagementShell';
export {
  useFileManagementWorkbenchWorkflow,
} from './workflows/useFileManagementWorkbenchWorkflow';
export type {
  UseFileManagementWorkbenchWorkflowOptions,
  UseFileManagementWorkbenchWorkflowReturn,
} from './workflows/useFileManagementWorkbenchWorkflow';
export {
  useFileManagementContextMenuBuilder,
} from './workflows/useFileManagementContextMenuBuilder';
export type {
  UseFileManagementContextMenuBuilderOptions,
} from './workflows/useFileManagementContextMenuBuilder';
export type { FileManagementCapabilities } from './workflows/fileManagementCapabilities';

export { FileConflictDialog } from './conflicts/FileConflictDialog';
export type { FileConflictDialogProps } from './conflicts/FileConflictDialog';
export {
  buildFileConflictResolutions,
  canApplyFileConflictStrategy,
  canApplyFileConflictStrategyToAll,
  getEffectiveFileConflictStrategy,
  isFileAlreadyExistsError,
} from './conflicts/fileConflictModel';
export type { FileConflictItemStrategies } from './conflicts/fileConflictModel';
export { useFileConflictController } from './conflicts/useFileConflictController';
export {
  composeFileConflictTransports,
  createLocalFileConflictTransport,
} from './conflicts/localFileConflictTransport';
export type {
  LocalFileConflictEntry,
  LocalFileConflictPayload,
  LocalFileConflictTransportOptions,
} from './conflicts/localFileConflictTransport';
export type {
  FileConflictController,
  UseFileConflictControllerOptions,
} from './conflicts/useFileConflictController';
export type {
  FileConflictBatchResult,
  FileConflictControllerPhase,
  FileConflictEntryType,
  FileConflictExecutionFields,
  FileConflictExecutionRequest,
  FileConflictItem,
  FileConflictOperation,
  FileConflictPreflightRequest,
  FileConflictPreflightResponse,
  FileConflictResolution,
  FileConflictResultItem,
  FileConflictResultStatus,
  FileConflictSource,
  FileConflictStrategy,
  FileConflictTransportOptions,
  FileConflictWorkflowTransport,
  ResolvableFileConflictStrategy,
} from './conflicts/types';
