import { describe, expect, it } from 'vitest';
import {
  buildFileConflictResolutions,
  canApplyFileConflictStrategyToAll,
  isFileAlreadyExistsError,
} from './fileConflictModel';
import type { FileConflictItem } from './types';

const conflicts: FileConflictItem[] = [
  {
    sourcePath: 'draft.md',
    targetPath: '/docs/draft.md',
    sourceType: 'file',
    targetType: 'file',
    canReplace: true,
  },
  {
    sourcePath: 'assets',
    targetPath: '/docs/assets',
    sourceType: 'directory',
    targetType: 'file',
    canReplace: false,
  },
];

describe('fileConflictModel', () => {
  it('builds one explicit resolution per conflict while preserving overrides', () => {
    expect(buildFileConflictResolutions(conflicts, 'keep-both', {
      'draft.md': 'replace',
      assets: 'skip',
    })).toEqual([
      { sourcePath: 'draft.md', strategy: 'replace' },
      { sourcePath: 'assets', strategy: 'skip' },
    ]);
  });

  it('forbids applying replace to all when any item cannot be replaced', () => {
    expect(canApplyFileConflictStrategyToAll(conflicts, 'replace')).toBe(false);
    expect(canApplyFileConflictStrategyToAll(conflicts, 'keep-both')).toBe(true);
    expect(canApplyFileConflictStrategyToAll(conflicts, 'skip')).toBe(true);
  });

  it('recognizes the canonical create and rename conflict error code only', () => {
    expect(isFileAlreadyExistsError({ errorCode: 'FILE_ALREADY_EXISTS' })).toBe(true);
    expect(isFileAlreadyExistsError({ detail: { errorCode: 'FILE_ALREADY_EXISTS' } })).toBe(true);
    expect(isFileAlreadyExistsError(new Error('FILE_ALREADY_EXISTS'))).toBe(false);
    expect(isFileAlreadyExistsError({ code: 'FILE_ALREADY_EXISTS' })).toBe(false);
  });
});
