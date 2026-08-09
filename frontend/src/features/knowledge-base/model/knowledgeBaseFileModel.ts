import type { FileTreeNode } from '@/shared/components/file-workbench';

export const KNOWLEDGE_BASE_FILE_ROOT_PATH = '/';

export const joinKnowledgeBaseFilePath = (parentPath: string, name: string): string => {
  if (!parentPath || parentPath === KNOWLEDGE_BASE_FILE_ROOT_PATH) {
    return `/${name}`;
  }

  return `${parentPath}/${name}`;
};

export const getKnowledgeBaseFileTargetPath = (node?: FileTreeNode): string => {
  if (!node || node.type !== 'directory') {
    return KNOWLEDGE_BASE_FILE_ROOT_PATH;
  }

  return node.path;
};

export const getKnowledgeBaseFileParentPath = (path: string): string => {
  const segments = path.split('/').filter(Boolean);
  segments.pop();
  return segments.length > 0
    ? `/${segments.join('/')}`
    : KNOWLEDGE_BASE_FILE_ROOT_PATH;
};

export const getKnowledgeBaseFileName = (path: string): string => {
  const segments = path.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? '';
};

export const getKnowledgeBaseFileApiErrorCode = (error: unknown): string | undefined => {
  if (
    typeof error === 'object' &&
    error !== null &&
    'errorCode' in error &&
    typeof (error as { errorCode?: unknown }).errorCode === 'string'
  ) {
    return (error as { errorCode: string }).errorCode;
  }

  return undefined;
};

export const isKnowledgeBaseFileContentConflictError = (error: unknown): boolean => (
  typeof error === 'object' &&
  error !== null &&
  (
    ('status' in error && (error as { status?: unknown }).status === 409) ||
    getKnowledgeBaseFileApiErrorCode(error) === 'CONTENT_CONFLICT'
  )
);
