/**
 * 統一檔案樹管理組件 - 公開 API
 */

// 類型定義
export type {
  FileTreeNode,
  ApiEndpointType,
  FileTreeApiConfig,
  FileOperationType,
  FileOperationRequest,
  FileOperationResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileTab,
  FileTreeFeatures,
  FileTreeManagerProps,
  SelectionModifier,
  ContextMenuState,
  FileUploadOptions,
  FileUploadResult,
  FileDownloadOptions,
} from './types';

// 常數
export {
  DEFAULT_FEATURES,
  FILE_TYPE_EXTENSIONS,
} from './types';

export {
  API_ENDPOINTS,
  ERROR_MESSAGES,
  SUCCESS_MESSAGES,
  FILE_SIZE_LIMITS,
  DEFAULTS,
} from './constants';

// 工具函數
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

// 服務
export { FileTreeApiAdapter } from './services/fileTreeAdapter';

// 組件
export { FileTreeManager } from './components/FileTreeManager';

export { FileTreePanel } from './components/FileTreePanel';
export type { FileTreePanelProps } from './components/FileTreePanel';

export { FileEditorPanel } from './components/FileEditorPanel';
export type { FileEditorPanelProps } from './components/FileEditorPanel';

export { FileTreeNode as FileTreeNodeComponent } from './components/FileTreeNode';
export type { FileTreeNodeProps } from './components/FileTreeNode';

export { FileTreeEmpty } from './components/FileTreeEmpty';
export type { FileTreeEmptyProps } from './components/FileTreeEmpty';

export { FileTreeToolbar } from './components/FileTreeToolbar';
export type { FileTreeToolbarProps } from './components/FileTreeToolbar';

export { ScopeSelector } from './components/ScopeSelector';
export type { ScopeSelectorProps, ScopeOption } from './components/ScopeSelector';

export { FileTreeContextMenu } from './components/FileTreeContextMenu';
export type { FileTreeContextMenuProps } from './components/FileTreeContextMenu';
export * from './components/FileOperationDialogs';

// 佈局
export { StandardFileTreeLayout } from './layouts/StandardFileTreeLayout';
export type { StandardFileTreeLayoutProps } from './layouts/StandardFileTreeLayout';

// Hooks
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
