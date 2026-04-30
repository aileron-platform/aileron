export type {
  FileTreeNode,
  FileTreeDataAdapter,
  FileOperationType,
  FileOperationRequest,
  FileOperationResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileTab,
  FileTreeFeatures,
  SelectionModifier,
  ContextMenuState,
  FileUploadOptions,
  FileUploadResult,
  FileDownloadOptions,
} from './types';

export {
  DEFAULT_FEATURES,
  FILE_TYPE_EXTENSIONS,
} from './types';

export {
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
  FILE_SIZE_LIMITS,
  DEFAULTS,
} from './constants';

export {
  findNodeByPath,
  filterNodesBySearch,
  flattenTree,
  buildTree,
  getParentPath,
  getNodeDepth,
  isAncestor,
  getFileExtension,
  getLanguageFromExtension,
  isImageFile,
  isMarkdownFile,
  formatFileSize,
  getAllFileNodes,
  getAllDirectoryNodes,
  getDescendantPaths,
  sortNodes,
  validateFileName,
} from './utils/fileTreeUtils';

export { FileTreePanel } from './tree/FileTreePanel';
export type { FileTreePanelProps } from './tree/FileTreePanel';

export { FileTreeNode as FileTreeNodeComponent } from './tree/FileTreeNode';
export type { FileTreeNodeProps } from './tree/FileTreeNode';

export { FileTreeEmpty } from './tree/FileTreeEmpty';
export type { FileTreeEmptyProps } from './tree/FileTreeEmpty';

export { FileTreeToolbar } from './tree/FileTreeToolbar';
export type { FileTreeToolbarProps } from './tree/FileTreeToolbar';

export { ScopeSelector } from './tree/ScopeSelector';
export type { ScopeSelectorProps, ScopeOption } from './tree/ScopeSelector';

export { FileTreeContextMenu } from './tree/FileTreeContextMenu';
export type { FileTreeContextMenuProps } from './tree/FileTreeContextMenu';
export * from './tree/FileOperationDialogs';
export * from './adapters';
export type {
  FileEditorProps,
  FileViewerWorkbenchAdapter,
  FileViewerWorkbenchCapabilities,
  FileViewerWorkbenchProps,
  FileViewerWorkbenchStatusMetadata,
  FileViewerWorkbenchTab,
} from './viewer/types';

export { StandardFileTreeLayout } from './layouts/StandardFileTreeLayout';
export type { StandardFileTreeLayoutProps } from './layouts/StandardFileTreeLayout';

export { useFileTreeManager } from './hooks/useFileTreeManager';
export type { UseFileTreeManagerOptions } from './hooks/useFileTreeManager';

export { useFileTreeState } from './hooks/useFileTreeState';
export type { UseFileTreeStateOptions, UseFileTreeStateReturn } from './hooks/useFileTreeState';

export { useFileOperations } from './hooks/useFileOperations';
export type { UseFileOperationsOptions, UseFileOperationsReturn } from './hooks/useFileOperations';

export { useFileOperationsWithDialog } from './hooks/useFileOperationsWithDialog';
export type { UseFileOperationsWithDialogOptions, DialogState } from './hooks/useFileOperationsWithDialog';

export { useFileEditor } from './hooks/useFileEditor';
export type { UseFileEditorOptions, UseFileEditorReturn } from './hooks/useFileEditor';

export { useFileTreeContextMenu } from './hooks/useFileTreeContextMenu';
export type { FileTreeContextMenuConfig } from './hooks/useFileTreeContextMenu';

export { FileTreeSearchBar } from './primitives/FileTreeSearchBar';
