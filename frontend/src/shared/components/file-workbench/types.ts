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
  pluginId?: string;
  pluginName?: string;
  marketplaceName?: string;
  modifiedAt?: string;
  createdAt?: string;
}

export interface FileTreeDataAdapter {
  getTree: () => Promise<FileTreeNode[]>;
  getChildren: (path: string) => Promise<FileTreeNode[]>;
  getContent: (path: string) => Promise<string>;
  create: (request: FileOperationRequest) => Promise<FileOperationResponse>;
  update: (path: string, content: string) => Promise<FileOperationResponse>;
  delete: (path: string, recursive?: boolean) => Promise<FileOperationResponse>;
  batchDelete: (request: BatchDeleteRequest) => Promise<BatchDeleteResponse>;
  move: (sourcePath: string, targetPath: string) => Promise<FileOperationResponse>;
  upload: (options: FileUploadOptions) => Promise<FileUploadResult[]>;
  download: (options: FileDownloadOptions) => Promise<void>;
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
}

export interface FileOperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  data?: any;
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
  node: FileTreeNode;
}

export interface FileTreeFeatures {
  enableMultiSelect?: boolean;
  enableDragDrop?: boolean;
  enableUpload?: boolean;
  enableDownload?: boolean;
  enableRename?: boolean;
  enableDelete?: boolean;
  enableCreate?: boolean;
  enableContextMenu?: boolean;
  enableSearch?: boolean;
  readOnly?: boolean;
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
  archiveAction?: 'store' | 'extract';
  keepArchive?: boolean;
  conflictStrategy?: 'rename' | 'overwrite' | 'reject';
}

export interface FileUploadResult {
  fileName: string;
  success: boolean;
  error?: string;
  path?: string;
}

export interface FileDownloadOptions {
  path: string;
  fileName?: string;
}

export const DEFAULT_FEATURES: Required<FileTreeFeatures> = {
  enableMultiSelect: true,
  enableDragDrop: true,
  enableUpload: true,
  enableDownload: true,
  enableRename: true,
  enableDelete: true,
  enableCreate: true,
  enableContextMenu: true,
  enableSearch: true,
  readOnly: false,
};

export const FILE_TYPE_EXTENSIONS = {
  image: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'],
  markdown: ['md', 'markdown'],
  code: ['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'cs', 'go', 'rs', 'rb', 'php', 'swift', 'kt'],
  config: ['json', 'yaml', 'yml', 'toml', 'xml', 'ini', 'env'],
  document: ['txt', 'pdf', 'doc', 'docx'],
} as const;
