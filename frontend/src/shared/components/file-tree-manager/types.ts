/**
 * 統一檔案樹管理組件 - 核心類型定義
 * 
 * 提供所有組件、Hooks 和服務層使用的類型定義
 */

/**
 * 檔案節點
 */
export interface FileTreeNode {
  /** 節點唯一識別碼 */
  id: string;
  /** 節點名稱 */
  name: string;
  /** 節點完整路徑 */
  path: string;
  /** 節點類型 */
  type: 'file' | 'directory';
  /** 子節點（僅資料夾有） */
  children?: FileTreeNode[];
  /** 目錄是否有子項（後端在 maxDepth 截斷時仍會回傳此欄位，用於懶載入判斷） */
  hasChildren?: boolean;
  /** 檔案大小（bytes） */
  size?: number;
  /** 檔案副檔名 */
  extension?: string;
  /** 文檔範圍（Claude Code 專用） */
  scope?: 'project' | 'user' | 'plugin';
  /** 修改時間 */
  modifiedAt?: string;
  /** 建立時間 */
  createdAt?: string;
}

/**
 * API 端點類型
 */
export type ApiEndpointType = 
  | 'workspace'      // Workspace 檔案管理
  | 'template'       // 模板中心
  | 'claude-code'    // Claude Code
  | 'knowledge-base'; // Knowledge Base

/**
 * API 配置
 */
export interface FileTreeApiConfig {
  /** API 端點類型 */
  type: ApiEndpointType;
  /** Workspace ID（workspace 和 claude-code 使用） */
  workspaceId?: string;
  /** Workspace Git context ID（workspace 使用） */
  contextId?: string | null;
  /** Template ID（template 使用） */
  templateId?: string;
  /** Knowledge Base ID（knowledge-base 使用） */
  knowledgeBaseId?: string;
  /** 範圍識別（template 使用：'scripts' | 'skills'；claude-code 使用：'project' | 'user' | 'plugin'） */
  scope?: string;
  /** Collection 類型（claude-code 使用：'skills' | 'scripts'） */
  collection?: 'skills' | 'scripts';
  /** 自定義 API 基礎 URL（可選，用於 workspace runtime 等） */
  baseUrl?: string;
  /** 是否包含隱藏檔與隱藏資料夾 */
  includeHidden?: boolean;
}

/**
 * 檔案操作類型
 */
export type FileOperationType = 
  | 'create'      // 建立
  | 'read'        // 讀取
  | 'update'      // 更新
  | 'delete'      // 刪除
  | 'rename'      // 重新命名
  | 'move'        // 移動
  | 'copy'        // 複製
  | 'upload'      // 上傳
  | 'download';   // 下載

/**
 * 檔案操作請求
 */
export interface FileOperationRequest {
  /** 操作類型 */
  type: FileOperationType;
  /** 目標路徑 */
  path: string;
  /** 目的路徑（用於 move, copy, rename） */
  targetPath?: string;
  /** 檔案內容（用於 create, update） */
  content?: string;
  /** 是否為資料夾 */
  isDirectory?: boolean;
  /** 是否遞迴（用於 delete） */
  recursive?: boolean;
}

/**
 * 檔案操作回應
 */
export interface FileOperationResponse {
  /** 操作是否成功 */
  success: boolean;
  /** 成功訊息 */
  message?: string;
  /** 錯誤訊息 */
  error?: string;
  /** 回應資料 */
  data?: any;
}

/**
 * 批次刪除請求
 */
export interface BatchDeleteRequest {
  /** 要刪除的路徑列表 */
  paths: string[];
  /** 是否遞迴刪除 */
  recursive?: boolean;
}

/**
 * 批次刪除回應
 */
export interface BatchDeleteResponse {
  /** 操作是否成功 */
  success: boolean;
  /** 成功刪除的路徑 */
  deleted: string[];
  /** 刪除失敗的路徑 */
  failed: Array<{ path: string; error: string }>;
  /** 總數 */
  total: number;
  /** 成功數 */
  successCount: number;
  /** 失敗數 */
  failedCount: number;
}

/**
 * 檔案標籤（編輯器標籤）
 */
export interface FileTab {
  /** 檔案路徑（唯一識別碼） */
  path: string;
  /** 檔案名稱 */
  name: string;
  /** 檔案內容 */
  content: string;
  /** 原始內容（用於判斷是否修改） */
  originalContent: string;
  /** 是否已修改 */
  isModified: boolean;
  /** 檔案節點 */
  node: FileTreeNode;
}

/**
 * 功能配置
 */
export interface FileTreeFeatures {
  /** 啟用多選 */
  enableMultiSelect?: boolean;
  /** 啟用拖放 */
  enableDragDrop?: boolean;
  /** 啟用上傳 */
  enableUpload?: boolean;
  /** 啟用下載 */
  enableDownload?: boolean;
  /** 啟用重新命名 */
  enableRename?: boolean;
  /** 啟用刪除 */
  enableDelete?: boolean;
  /** 啟用新增 */
  enableCreate?: boolean;
  /** 啟用右鍵選單 */
  enableContextMenu?: boolean;
  /** 啟用搜尋 */
  enableSearch?: boolean;
  /** 唯讀模式 */
  readOnly?: boolean;
}

/**
 * 選擇修飾鍵類型
 */
export type SelectionModifier = 'none' | 'ctrl' | 'shift';

/**
 * 右鍵選單狀態
 */
export interface ContextMenuState {
  /** X 座標 */
  x: number;
  /** Y 座標 */
  y: number;
  /** 目標節點 */
  node: FileTreeNode;
}

/**
 * 檔案上傳選項
 */
export interface FileUploadOptions {
  /** 目標路徑 */
  targetPath: string;
  /** 檔案列表 */
  files: File[];
  /** 壓縮檔處理方式 */
  archiveAction?: 'store' | 'extract';
  /** 解壓時是否保留原始壓縮檔 */
  keepArchive?: boolean;
  /** 衝突策略 */
  conflictStrategy?: 'rename' | 'overwrite' | 'reject';
}

/**
 * 檔案上傳結果
 */
export interface FileUploadResult {
  /** 檔案名稱 */
  fileName: string;
  /** 是否成功 */
  success: boolean;
  /** 錯誤訊息 */
  error?: string;
  /** 上傳後的路徑 */
  path?: string;
}

/**
 * 檔案下載選項
 */
export interface FileDownloadOptions {
  /** 檔案路徑 */
  path: string;
  /** 下載檔名（可選） */
  fileName?: string;
}

/**
 * 預設功能配置
 */
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

/**
 * 檔案類型判斷
 */
export const FILE_TYPE_EXTENSIONS = {
  image: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'],
  markdown: ['md', 'markdown'],
  code: ['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'cs', 'go', 'rs', 'rb', 'php', 'swift', 'kt'],
  config: ['json', 'yaml', 'yml', 'toml', 'xml', 'ini', 'env'],
  document: ['txt', 'pdf', 'doc', 'docx'],
} as const;
