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

export const FILE_SIZE_LIMITS = {
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
  MAX_UPLOAD_SIZE: 50 * 1024 * 1024, // 50MB
} as const;

export const DEFAULTS = {
  SEARCH_DEBOUNCE: 300,
  AUTO_SAVE_DELAY: 1000,
} as const;
