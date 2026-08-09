import type {
  FileConflictBatchResult,
  FileConflictExecutionFields,
} from './conflicts/types';

export interface FileTreeNodeBadge {
  key: string;
  label: string;
  title?: string;
  tone?: 'default' | 'muted' | 'warning' | 'danger';
}

export interface FileTreeNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileTreeNode[];
  hasChildren?: boolean;
  writable?: boolean;
  size?: number;
  extension?: string;
  scope?: 'project' | 'user' | 'plugin';
  metadata?: Record<string, unknown>;
  badges?: FileTreeNodeBadge[];
  pluginId?: string;
  pluginName?: string;
  marketplaceName?: string;
  revision?: string;
  modifiedAt?: string;
  createdAt?: string;
}

export interface FileTreeDataAdapter {
  getTree: () => Promise<FileTreeNode[]>;
  getChildren: (path: string) => Promise<FileTreeNode[]>;
  getContent: (path: string) => Promise<FileContentPayload>;
  create: (request: FileOperationRequest) => Promise<FileOperationResponse>;
  update: (path: string, content: string, options?: FileUpdateOptions) => Promise<FileOperationResponse>;
  delete: (path: string, recursive?: boolean) => Promise<FileOperationResponse>;
  batchDelete: (request: BatchDeleteRequest) => Promise<BatchDeleteResponse>;
  move: (sourcePath: string, targetPath: string) => Promise<FileOperationResponse>;
  upload: (options: FileUploadOptions) => Promise<FileConflictBatchResult>;
  extractArchive?: (options: FileConflictExecutionFields & {
    archivePath: string;
    targetPath: string;
  }) => Promise<FileConflictBatchResult>;
  download: (options: FileDownloadOptions) => Promise<void>;
}

export interface FileContentResult {
  content: string;
  revision?: string | null;
  readable?: boolean;
  unreadableReason?: 'binary';
}

export type FileContentPayload = string | FileContentResult;

export interface FileUpdateOptions {
  revision?: string | null;
}

export type FileOperationType = 
  | 'create'
  | 'read'
  | 'update'
  | 'delete'
  | 'rename'
  | 'move'
  | 'copy'
  | 'upload'
  | 'download';

export interface FileOperationRequest {
  type: FileOperationType;
  path: string;
  targetPath?: string;
  content?: string;
  isDirectory?: boolean;
  recursive?: boolean;
  revision?: string | null;
}

export interface FileOperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  data?: unknown;
}

export interface BatchDeleteRequest {
  paths: string[];
  recursive?: boolean;
}

export interface BatchDeleteResponse {
  success: boolean;
  deleted: string[];
  failed: Array<{ path: string; error: string }>;
  total: number;
  successCount: number;
  failedCount: number;
}

export interface FileTab {
  path: string;
  name: string;
  content: string;
  originalContent: string;
  isModified: boolean;
  revision?: string | null;
  readable?: boolean;
  unreadableReason?: 'binary';
  node: FileTreeNode;
}

export type SelectionModifier = 'none' | 'ctrl' | 'shift';

export interface ContextMenuState {
  x: number;
  y: number;
  node: FileTreeNode;
}

export interface FileUploadOptions {
  targetPath: string;
  files: File[];
}

export interface FileDownloadOptions {
  path: string;
  fileName?: string;
}
