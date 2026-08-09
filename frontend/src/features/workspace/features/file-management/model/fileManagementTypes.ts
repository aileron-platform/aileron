import type { SelectionModifier } from '@/shared/components/file-workbench';

/**
 */

export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  lastModified?: string;
  children?: FileNode[];
  hasChildren?: boolean;
  isExpanded?: boolean;
  isLoading?: boolean;
  depth: number;
}

export type FileOperationStatus = 'pending' | 'running' | 'succeeded' | 'failed';

export type FileOperationType = 'delete' | 'rename' | 'create' | 'upload' | 'extract';

export interface PendingFileAction {
  id: string;
  type: FileOperationType;
  sourcePath?: string;
  targetDirectory?: string;
  targetPath?: string;
  status: FileOperationStatus;
  progress?: number | null;
  errorMessage?: string | null;
}

export interface FileTreeState {
  nodes: FileNode[];
  selectedFile: string | null;
  selectedFiles: Set<string>;
  lastSelectedFile: string | null;
  isLoading: boolean;
  error: string | null;
  expandedNodes: Set<string>;
  pendingAction: PendingFileAction | null;
  draggedNode: string | null;
  dropTarget: string | null;
  showHiddenEntries: boolean;
}

export interface FileOperationResult {
  success: boolean;
  message: string;
  data?: unknown;
  errorCode?: string;
  revision?: string;
}

export interface CreateFilePayload {
  name: string;
  path: string;
  content?: string;
  isDirectory: boolean;
}

export interface RenameFilePayload {
  oldPath: string;
  newPath: string;
}

export interface DeleteFilePayload {
  path: string;
  recursive?: boolean;
}

export interface UploadFilePayload {
  files: FileList | File[];
  targetPath: string;
}

export interface FileContent {
  content: string;
  encoding: string;
  size: number;
  lastModified: string;
  revision?: string;
  language?: string | null;
}

export interface FileTreeActions {
  loadFileTree: () => Promise<void>;
  refreshFileTree: () => Promise<void>;
  setShowHiddenEntries: (showHiddenEntries: boolean) => Promise<void>;
  toggleShowHiddenEntries: () => Promise<void>;
  selectFile: (filePath: string) => void;
  selectFileWithModifier: (filePath: string, modifier: SelectionModifier) => void;
  selectRange: (fromPath: string, toPath: string) => void;
  toggleMultiSelect: (filePath: string) => void;
  clearSelection: () => void;
  selectAllFiles: (filePaths: string[]) => void;
  expandNode: (nodePath: string) => void;
  collapseNode: (nodePath: string) => void;
  createFile: (request: CreateFilePayload) => Promise<FileOperationResult>;
  createFolder: (request: CreateFilePayload) => Promise<FileOperationResult>;
  renameFile: (request: RenameFilePayload) => Promise<FileOperationResult>;
  deleteFile: (request: DeleteFilePayload) => Promise<FileOperationResult>;
  deleteFiles: (paths: string[], options?: { recursive?: boolean }) => Promise<FileOperationResult>;
  uploadFiles: (request: UploadFilePayload) => Promise<FileOperationResult>;
  downloadFile: (filePath: string) => Promise<void>;
  downloadFiles: (filePaths: string[]) => Promise<void>;
  readFileContent: (filePath: string) => Promise<FileContent>;
  saveFileContent: (filePath: string, content: string, revision?: string | null) => Promise<FileOperationResult>;
  moveNode: (sourcePath: string, targetPath: string) => Promise<FileOperationResult>;
  setDraggedNode: (nodePath: string | null) => void;
  setDropTarget: (nodePath: string | null) => void;
}
