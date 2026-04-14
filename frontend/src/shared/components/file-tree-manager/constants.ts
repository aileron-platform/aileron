/**
 * 統一檔案樹管理組件 - 常數定義
 */

/**
 * API 端點映射
 */
export const API_ENDPOINTS = {
  workspace: {
    getTree: (workspaceId: string) => `/workspaces/${workspaceId}/files/tree`,
    getContent: (workspaceId: string) => `/workspaces/${workspaceId}/files/content`,
    create: (workspaceId: string) => `/workspaces/${workspaceId}/files`,
    update: (workspaceId: string) => `/workspaces/${workspaceId}/files/content`,
    delete: (workspaceId: string) => `/workspaces/${workspaceId}/files`,
    batchDelete: (workspaceId: string) => `/workspaces/${workspaceId}/files/batch-delete`,
    rename: (workspaceId: string) => `/workspaces/${workspaceId}/files/rename`,
    move: (workspaceId: string) => `/workspaces/${workspaceId}/files/move`,
    upload: (workspaceId: string) => `/workspaces/${workspaceId}/files/upload`,
    download: (workspaceId: string) => `/workspaces/${workspaceId}/files/download`,
  },
  template: {
    getTree: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/tree?scope=${scope}&include_hidden=true`,
    getContent: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/content?scope=${scope}`,
    create: (templateId: string, scope: string) =>
      `/templates/${templateId}/files?scope=${scope}`,
    update: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/content?scope=${scope}`,
    delete: (templateId: string, scope: string) =>
      `/templates/${templateId}/files?scope=${scope}`,
    batchDelete: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/batch-delete?scope=${scope}`,
    move: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/move?scope=${scope}`,
    upload: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/upload?scope=${scope}`,
    copy: (templateId: string, scope: string) =>
      `/templates/${templateId}/files/copy?scope=${scope}`,
  },
  claudeCode: {
    getTree: (workspaceId: string, collection: 'skills' | 'scripts', scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}/tree?scope=${scope}&includeHidden=true`,
    getContent: (workspaceId: string, collection: 'skills' | 'scripts', path: string, scope: string) =>
      `/workspaces/${workspaceId}/claude-code/${collection}/content?path=${encodeURIComponent(path)}&scope=${scope}`,
    create: (workspaceId: string, collection: 'skills' | 'scripts', scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}?scope=${scope}`,
    update: (workspaceId: string, collection: 'skills' | 'scripts', path: string, scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}/content?path=${encodeURIComponent(path)}&scope=${scope}`,
    delete: (workspaceId: string, collection: 'skills' | 'scripts', path: string, scope: string = 'project', recursive: boolean = false) =>
      `/workspaces/${workspaceId}/claude-code/${collection}?path=${encodeURIComponent(path)}&scope=${scope}&recursive=${recursive}`,
    // Move API 不需要 path 參數，使用 POST body 傳遞 sourcePath 和 destPath
    move: (workspaceId: string, collection: 'skills' | 'scripts', scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}/move?scope=${scope}`,
    // Copy API 不需要 path 參數，使用 POST body 傳遞 sourcePath 和 destPath
    copy: (workspaceId: string, collection: 'skills' | 'scripts', scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}/copy?scope=${scope}`,
  },
} as const;

/**
 * 錯誤訊息
 */
export const ERROR_MESSAGES = {
  INVALID_CONFIG: '無效的 API 配置',
  MISSING_WORKSPACE_ID: '缺少 Workspace ID',
  MISSING_TEMPLATE_ID: '缺少 Template ID',
  MISSING_SCOPE: '缺少 scope 參數',
  FILE_NOT_FOUND: '檔案不存在',
  OPERATION_FAILED: '操作失敗',
  NETWORK_ERROR: '網路錯誤',
  PERMISSION_DENIED: '權限不足',
} as const;

/**
 * 成功訊息
 */
export const SUCCESS_MESSAGES = {
  FILE_CREATED: '檔案建立成功',
  FILE_UPDATED: '檔案更新成功',
  FILE_DELETED: '檔案刪除成功',
  FILE_RENAMED: '檔案重新命名成功',
  FILE_MOVED: '檔案移動成功',
  FILE_UPLOADED: '檔案上傳成功',
  BATCH_DELETE_SUCCESS: '批次刪除成功',
  BATCH_DELETE_PARTIAL: '部分刪除成功',
} as const;

/**
 * 檔案大小限制（bytes）
 */
export const FILE_SIZE_LIMITS = {
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
  MAX_UPLOAD_SIZE: 50 * 1024 * 1024, // 50MB
} as const;

/**
 * 預設值
 * 注意：MAX_DEPTH 已移除，階層數由後端環境設定檔 FILE_TREE_MAX_DEPTH 控制
 */
export const DEFAULTS = {
  SEARCH_DEBOUNCE: 300,
  AUTO_SAVE_DELAY: 1000,
} as const;

