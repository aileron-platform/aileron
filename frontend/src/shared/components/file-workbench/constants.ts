/**
 */

/**
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
  knowledgeBase: {
    getTree: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/tree`,
    getContent: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
    create: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
    update: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
    delete: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
    move: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
    upload: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
    copy: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/copy`,
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

    move: (workspaceId: string, collection: 'skills' | 'scripts', scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}/move?scope=${scope}`,

    copy: (workspaceId: string, collection: 'skills' | 'scripts', scope: string = 'project') =>
      `/workspaces/${workspaceId}/claude-code/${collection}/copy?scope=${scope}`,
  },
} as const;

/**
 */
export const ERROR_MESSAGES = {
  INVALID_CONFIG: 'Invalid API configuration',
  MISSING_WORKSPACE_ID: 'Missing Workspace ID',
  MISSING_TEMPLATE_ID: 'Missing Template ID',
  MISSING_KNOWLEDGE_BASE_ID: 'Missing Knowledge Base ID',
  MISSING_SCOPE: 'Missing scope parameter',
  FILE_NOT_FOUND: 'File not found',
  OPERATION_FAILED: 'Operation failed',
  NETWORK_ERROR: 'Network error',
  PERMISSION_DENIED: 'Permission denied',
} as const;

/**
 */
export const SUCCESS_MESSAGES = {
  FILE_CREATED: 'File created successfully',
  FILE_UPDATED: 'File updated successfully',
  FILE_DELETED: 'File deleted successfully',
  FILE_RENAMED: 'File renamed successfully',
  FILE_MOVED: 'File moved successfully',
  FILE_UPLOADED: 'File uploaded successfully',
  BATCH_DELETE_SUCCESS: 'Batch delete succeeded',
  BATCH_DELETE_PARTIAL: 'Batch delete partially succeeded',
} as const;

/**
 */
export const FILE_SIZE_LIMITS = {
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
  MAX_UPLOAD_SIZE: 50 * 1024 * 1024, // 50MB
} as const;

/**
 */
export const DEFAULTS = {
  SEARCH_DEBOUNCE: 300,
  AUTO_SAVE_DELAY: 1000,
} as const;
