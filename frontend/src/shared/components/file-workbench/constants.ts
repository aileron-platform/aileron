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

export const DEFAULTS = {
  SEARCH_DEBOUNCE: 300,
  AUTO_SAVE_DELAY: 1000,
} as const;
