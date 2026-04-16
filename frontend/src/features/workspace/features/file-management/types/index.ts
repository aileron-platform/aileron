/**
 * 檔案管理功能類型定義
 * 完全按照原始設計重構
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

export type FileOperationType = 'copy' | 'delete' | 'rename' | 'create' | 'upload' | 'extract';

export type FileCreationAction = 'upload' | 'folder' | 'file';

/**
 * 選擇修飾鍵類型
 * - none: 無修飾鍵，清除其他選擇
 * - ctrl: Ctrl/Cmd 鍵，切換選擇狀態
 * - shift: Shift 鍵，範圍選擇
 */
export type SelectionModifier = 'none' | 'ctrl' | 'shift';

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
  lastSelectedFile: string | null; // 記錄上次選擇的檔案（用於 Shift 範圍選擇）
  isLoading: boolean;
  error: string | null;
  expandedNodes: Set<string>;
  pendingAction: PendingFileAction | null;
  draggedNode: string | null; // 正在拖曳的節點路徑
  dropTarget: string | null; // 拖曳目標節點路徑
  showHiddenEntries: boolean;
}

export interface FileOperationResult {
  success: boolean;
  message: string;
  data?: any;
  errorCode?: string;
}

export interface CreateFileRequest {
  name: string;
  path: string;
  content?: string;
  isDirectory: boolean;
}

export interface RenameFileRequest {
  oldPath: string;
  newPath: string;
}

export interface DeleteFileRequest {
  path: string;
  recursive?: boolean;
}

export interface UploadFileRequest {
  files: FileList | File[];
  targetPath: string;
  useSystemTmp?: boolean;
  archiveAction?: 'store' | 'extract';
  keepArchive?: boolean;
  conflictStrategy?: 'rename' | 'overwrite' | 'reject';
}

export interface FileContent {
  content: string;
  encoding: string;
  size: number;
  lastModified: string;
  versionId?: string;
  contentHash?: string;
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
  createFile: (request: CreateFileRequest) => Promise<FileOperationResult>;
  createFolder: (request: CreateFileRequest) => Promise<FileOperationResult>;
  renameFile: (request: RenameFileRequest) => Promise<FileOperationResult>;
  deleteFile: (request: DeleteFileRequest) => Promise<FileOperationResult>;
  deleteFiles: (paths: string[], options?: { recursive?: boolean }) => Promise<FileOperationResult>;
  uploadFiles: (request: UploadFileRequest) => Promise<FileOperationResult>;
  downloadFile: (filePath: string) => Promise<void>;
  downloadFiles: (filePaths: string[]) => Promise<void>;
  readFileContent: (filePath: string) => Promise<FileContent>;
  saveFileContent: (filePath: string, content: string) => Promise<FileOperationResult>;
  copyNode: (sourcePath: string, targetDirectory: string) => Promise<FileOperationResult>;
  moveNode: (sourcePath: string, targetPath: string) => Promise<FileOperationResult>;
  setDraggedNode: (nodePath: string | null) => void;
  setDropTarget: (nodePath: string | null) => void;
}

export interface FileTreeContextType {
  state: FileTreeState;
  actions: FileTreeActions;
}

// 檔案圖示映射
export const FILE_ICONS = {
  // TypeScript/JavaScript
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.js': 'javascript',
  '.jsx': 'javascript',
  '.mjs': 'javascript',
  '.cjs': 'javascript',
  
  // 樣式檔案
  '.css': 'css',
  '.scss': 'sass',
  '.sass': 'sass',
  '.less': 'less',
  '.styl': 'stylus',
  
  // 標記語言
  '.html': 'html',
  '.htm': 'html',
  '.xml': 'xml',
  '.svg': 'svg',
  
  // 配置檔案
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.toml': 'toml',
  '.ini': 'config',
  '.env': 'env',
  
  // 文檔
  '.md': 'markdown',
  '.mdx': 'markdown',
  '.txt': 'text',
  '.log': 'log',
  
  // 圖片
  '.png': 'image',
  '.jpg': 'image',
  '.jpeg': 'image',
  '.gif': 'image',
  '.webp': 'image',
  '.ico': 'image',
  
  // 其他
  '.pdf': 'pdf',
  '.zip': 'archive',
  '.tar': 'archive',
  '.gz': 'archive',
  
  // 預設
  default: 'file'
} as const;

export type FileIconType = typeof FILE_ICONS[keyof typeof FILE_ICONS];
