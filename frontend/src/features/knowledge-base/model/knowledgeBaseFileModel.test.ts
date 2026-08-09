import { describe, expect, it } from 'vitest';
import type { FileTreeNode } from '@/shared/components/file-workbench';
import {
  KNOWLEDGE_BASE_FILE_ROOT_PATH,
  getKnowledgeBaseFileApiErrorCode,
  getKnowledgeBaseFileName,
  getKnowledgeBaseFileParentPath,
  getKnowledgeBaseFileTargetPath,
  isKnowledgeBaseFileContentConflictError,
  joinKnowledgeBaseFilePath,
} from './knowledgeBaseFileModel';

const directoryNode: FileTreeNode = {
  id: '/docs',
  name: 'docs',
  path: '/docs',
  type: 'directory',
};

const fileNode: FileTreeNode = {
  id: '/docs/readme.md',
  name: 'readme.md',
  path: '/docs/readme.md',
  type: 'file',
};

describe('knowledgeBaseFileModel', () => {
  it.each([
    ['', 'readme.md', '/readme.md'],
    [KNOWLEDGE_BASE_FILE_ROOT_PATH, 'readme.md', '/readme.md'],
    ['/docs', 'readme.md', '/docs/readme.md'],
  ])('joins %s and %s with the knowledge base root contract', (parentPath, name, expected) => {
    expect(joinKnowledgeBaseFilePath(parentPath, name)).toBe(expected);
  });

  it('derives target, parent, and node-name paths without changing root semantics', () => {
    expect(getKnowledgeBaseFileTargetPath()).toBe(KNOWLEDGE_BASE_FILE_ROOT_PATH);
    expect(getKnowledgeBaseFileTargetPath(fileNode)).toBe(KNOWLEDGE_BASE_FILE_ROOT_PATH);
    expect(getKnowledgeBaseFileTargetPath(directoryNode)).toBe('/docs');
    expect(getKnowledgeBaseFileParentPath('/docs/readme.md')).toBe('/docs');
    expect(getKnowledgeBaseFileParentPath('/readme.md')).toBe(KNOWLEDGE_BASE_FILE_ROOT_PATH);
    expect(getKnowledgeBaseFileName('/docs/readme.md')).toBe('readme.md');
  });

  it('reads file API error codes and recognizes existing conflict variants', () => {
    expect(getKnowledgeBaseFileApiErrorCode({ errorCode: 'KB_QUOTA_EXCEEDED' }))
      .toBe('KB_QUOTA_EXCEEDED');
    expect(getKnowledgeBaseFileApiErrorCode({ errorCode: 409 })).toBeUndefined();
    expect(isKnowledgeBaseFileContentConflictError({ status: 409 })).toBe(true);
    expect(isKnowledgeBaseFileContentConflictError({ errorCode: 'CONTENT_CONFLICT' })).toBe(true);
    expect(isKnowledgeBaseFileContentConflictError(new Error('failed'))).toBe(false);
  });
});
