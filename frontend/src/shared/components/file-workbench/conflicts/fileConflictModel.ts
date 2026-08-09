import type {
  FileConflictItem,
  FileConflictResolution,
  ResolvableFileConflictStrategy,
} from './types';

export type FileConflictItemStrategies = Record<string, ResolvableFileConflictStrategy>;

export const canApplyFileConflictStrategyToAll = (
  conflicts: FileConflictItem[],
  strategy: ResolvableFileConflictStrategy,
): boolean => strategy !== 'replace' || conflicts.every((conflict) => conflict.canReplace);

export const canApplyFileConflictStrategy = (
  conflict: FileConflictItem,
  strategy: ResolvableFileConflictStrategy,
): boolean => strategy !== 'replace' || conflict.canReplace;

export const getEffectiveFileConflictStrategy = (
  sourcePath: string,
  defaultStrategy: ResolvableFileConflictStrategy,
  itemStrategies: FileConflictItemStrategies,
): ResolvableFileConflictStrategy => itemStrategies[sourcePath] ?? defaultStrategy;

export const buildFileConflictResolutions = (
  conflicts: FileConflictItem[],
  defaultStrategy: ResolvableFileConflictStrategy,
  itemStrategies: FileConflictItemStrategies,
): FileConflictResolution[] => conflicts.map((conflict) => ({
  sourcePath: conflict.sourcePath,
  strategy: getEffectiveFileConflictStrategy(
    conflict.sourcePath,
    defaultStrategy,
    itemStrategies,
  ),
}));

export const isFileAlreadyExistsError = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') return false;
  if ('errorCode' in error && error.errorCode === 'FILE_ALREADY_EXISTS') return true;
  if (!('detail' in error) || !error.detail || typeof error.detail !== 'object') return false;
  return 'errorCode' in error.detail && error.detail.errorCode === 'FILE_ALREADY_EXISTS';
};
