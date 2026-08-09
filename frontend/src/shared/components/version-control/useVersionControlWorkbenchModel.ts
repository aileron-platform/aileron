import { useMemo } from 'react';
import type {
  VersionControlBranch,
  VersionControlChangesResponse,
  VersionControlCommitSummary,
  VersionControlFileChange,
  VersionControlRepositoryStatus,
  VersionControlStatus,
} from '@/shared/version-control';
import {
  useVersionControlWorkbenchController,
  type VersionControlWorkbenchMode,
} from './useVersionControlWorkbenchController';
import type { VersionControlFileGroup } from './useVersionControlFileSelection';

const emptyChangePage = {
  items: [],
  total: 0,
  nextCursor: null,
  hasMore: false,
};

export const emptyVersionControlChanges: VersionControlChangesResponse = {
  staged: emptyChangePage,
  unstaged: emptyChangePage,
  untracked: emptyChangePage,
  conflicts: emptyChangePage,
};

interface UseVersionControlWorkbenchModelOptions {
  mode?: VersionControlWorkbenchMode;
  initialMode?: VersionControlWorkbenchMode;
  changes?: VersionControlChangesResponse;
  status?: VersionControlStatus | null;
  branches?: VersionControlBranch[];
  commits?: VersionControlCommitSummary[];
  repository?: VersionControlRepositoryStatus | null;
  onFileSelect?: (file: VersionControlFileChange | null, group: VersionControlFileGroup) => void;
}

export const useVersionControlWorkbenchModel = ({
  mode,
  initialMode,
  changes = emptyVersionControlChanges,
  status = null,
  branches = [],
  commits = [],
  repository = null,
  onFileSelect,
}: UseVersionControlWorkbenchModelOptions) => {
  const stagedFiles = useMemo(
    () => changes.staged.items.map(file => ({ ...file, changeType: 'staged' as const })),
    [changes.staged.items],
  );
  const unstagedFiles = useMemo(
    () => [
      ...changes.unstaged.items.map(file => ({ ...file, changeType: 'unstaged' as const })),
      ...changes.untracked.items.map(file => ({ ...file, changeType: 'untracked' as const })),
    ],
    [changes.unstaged.items, changes.untracked.items],
  );
  const conflictFiles = useMemo(
    () => changes.conflicts.items.map(file => ({ ...file, changeType: 'unstaged' as const })),
    [changes.conflicts.items],
  );
  const numstatParams = useMemo(() => {
    const deferredPaths = (files: VersionControlFileChange[]) => files
      .filter(file => file.additions == null && file.deletions == null)
      .map(file => file.path);
    return {
      stagedPaths: deferredPaths(changes.staged.items),
      unstagedPaths: deferredPaths(changes.unstaged.items),
    };
  }, [changes.staged.items, changes.unstaged.items]);
  const currentBranch = useMemo(
    () => branches.find(branch => branch.isCurrent)?.name
      ?? status?.currentBranch
      ?? repository?.currentBranch
      ?? '',
    [branches, repository?.currentBranch, status?.currentBranch],
  );
  const controller = useVersionControlWorkbenchController({
    mode,
    initialMode,
    stagedFiles,
    unstagedFiles,
    commits,
    onFileSelect,
  });

  return {
    changes,
    stagedFiles,
    unstagedFiles,
    conflictFiles,
    numstatParams,
    currentBranch,
    changeCount: stagedFiles.length + unstagedFiles.length + conflictFiles.length,
    controller,
  };
};

export type VersionControlWorkbenchModel = ReturnType<typeof useVersionControlWorkbenchModel>;
