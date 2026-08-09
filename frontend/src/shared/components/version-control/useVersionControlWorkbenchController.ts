import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { addPathsToSet, removePathsFromSet } from '@/shared/version-control/versionControlOptimisticUpdates';
import type {
  VersionControlBranch,
  VersionControlCommitSummary,
  VersionControlFileChange,
} from '@/shared/version-control';
import {
  useVersionControlFileSelection,
  type VersionControlFileGroup,
} from './useVersionControlFileSelection';

export type VersionControlWorkbenchMode = 'changes' | 'history';
export type VersionControlMutationKind = 'commit' | 'stageAll' | 'unstageAll' | 'other';

interface UseVersionControlWorkbenchControllerOptions {
  mode?: VersionControlWorkbenchMode;
  initialMode?: VersionControlWorkbenchMode;
  stagedFiles: VersionControlFileChange[];
  unstagedFiles: VersionControlFileChange[];
  commits?: VersionControlCommitSummary[];
  onFileSelect?: (file: VersionControlFileChange | null, group: VersionControlFileGroup) => void;
}

interface RunVersionControlMutationOptions<T> {
  kind?: VersionControlMutationKind;
  clearSelectionOnSuccess?: boolean;
  onSuccess?: (result: T) => void | Promise<void>;
  onError?: (error: unknown) => void | Promise<void>;
}

export function useVersionControlWorkbenchController({
  mode: controlledMode,
  initialMode = 'changes',
  stagedFiles,
  unstagedFiles,
  commits = [],
  onFileSelect,
}: UseVersionControlWorkbenchControllerOptions) {
  const [uncontrolledMode, setUncontrolledMode] = useState<VersionControlWorkbenchMode>(initialMode);
  const mode = controlledMode ?? uncontrolledMode;
  const [selectedFile, setSelectedFile] = useState<VersionControlFileChange | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<VersionControlFileGroup>('unstaged');
  const [selectedCommitId, setSelectedCommitId] = useState<string | null>(null);
  const [selectedCommitFile, setSelectedCommitFile] = useState<VersionControlFileChange | null>(null);
  const [pendingStagedPaths, setPendingStagedPaths] = useState<Set<string>>(() => new Set());
  const [pendingUnstagedPaths, setPendingUnstagedPaths] = useState<Set<string>>(() => new Set());
  const [isMutating, setIsMutating] = useState(false);
  const [activeMutation, setActiveMutation] = useState<VersionControlMutationKind | null>(null);

  const [remoteSettingsOpen, setRemoteSettingsOpen] = useState(false);
  const [lfsSettingsOpen, setLfsSettingsOpen] = useState(false);
  const [createBranchOpen, setCreateBranchOpen] = useState(false);
  const [trackingBranch, setTrackingBranch] = useState<VersionControlBranch | null>(null);
  const [renameBranch, setRenameBranch] = useState<VersionControlBranch | null>(null);
  const [deleteBranch, setDeleteBranch] = useState<VersionControlBranch | null>(null);
  const [publishBranchOpen, setPublishBranchOpen] = useState(false);
  const [discardPaths, setDiscardPaths] = useState<string[]>([]);
  const [abortConflictOpen, setAbortConflictOpen] = useState(false);
  const [revertCommit, setRevertCommit] = useState<VersionControlCommitSummary | null>(null);

  const fileSelection = useVersionControlFileSelection({
    stagedFiles,
    unstagedFiles,
    onFileSelect: (file, group) => {
      setSelectedFile(file);
      setSelectedGroup(group);
      onFileSelect?.(file, group);
    },
  });

  const clearChangeSelection = useCallback(() => {
    setSelectedFile(null);
    fileSelection.clearSelection();
    onFileSelect?.(null, selectedGroup);
  }, [fileSelection.clearSelection, onFileSelect, selectedGroup]);

  useEffect(() => {
    setSelectedCommitId((current) => (
      commits.some((commit) => commit.id === current)
        ? current
        : commits[0]?.id ?? null
    ));
  }, [commits]);

  useEffect(() => {
    setSelectedCommitFile(null);
  }, [selectedCommitId]);

  useEffect(() => {
    if (mode === 'changes') {
      setSelectedCommitFile(null);
      return;
    }
    clearChangeSelection();
  }, [clearChangeSelection, mode]);

  const addPendingPaths = useCallback((group: VersionControlFileGroup, paths: string[]) => {
    if (group === 'staged') {
      setPendingStagedPaths((current) => addPathsToSet(current, paths));
      return;
    }
    setPendingUnstagedPaths((current) => addPathsToSet(current, paths));
  }, []);

  const removePendingPaths = useCallback((group: VersionControlFileGroup, paths: string[]) => {
    if (group === 'staged') {
      setPendingStagedPaths((current) => removePathsFromSet(current, paths));
      return;
    }
    setPendingUnstagedPaths((current) => removePathsFromSet(current, paths));
  }, []);

  const runMutation = useCallback(async <T,>(
    operation: Promise<T>,
    options: RunVersionControlMutationOptions<T> = {},
  ): Promise<boolean> => {
    setIsMutating(true);
    setActiveMutation(options.kind ?? 'other');
    try {
      const result = await operation;
      if (options.clearSelectionOnSuccess !== false) {
        clearChangeSelection();
      }
      await options.onSuccess?.(result);
      return true;
    } catch (error) {
      await options.onError?.(error);
      return false;
    } finally {
      setIsMutating(false);
      setActiveMutation(null);
    }
  }, [clearChangeSelection]);

  const selectFile = useCallback((
    file: VersionControlFileChange,
    group: VersionControlFileGroup,
    event?: React.MouseEvent,
  ) => {
    fileSelection.selectFile(file, group, event);
  }, [fileSelection.selectFile]);

  const selectCommit = useCallback((commit: VersionControlCommitSummary) => {
    setSelectedCommitId(commit.id);
    setSelectedCommitFile(null);
  }, []);

  const resetForMode = useCallback(() => {
    clearChangeSelection();
    setSelectedCommitFile(null);
  }, [clearChangeSelection]);

  return {
    mode,
    setMode: setUncontrolledMode,
    selection: {
      ...fileSelection,
      selectedFile,
      selectedGroup,
      selectedCommitId,
      selectedCommitFile,
      selectedDiffFile: mode === 'history' ? selectedCommitFile : selectedFile,
      selectFile,
      selectCommit,
      setSelectedCommitId,
      setSelectedCommitFile,
      clearChangeSelection,
      resetForMode,
    },
    pending: {
      stagedPaths: pendingStagedPaths,
      unstagedPaths: pendingUnstagedPaths,
      addPaths: addPendingPaths,
      removePaths: removePendingPaths,
    },
    mutation: {
      isMutating,
      activeMutation,
      run: runMutation,
    },
    dialogs: {
      remoteSettingsOpen,
      setRemoteSettingsOpen,
      lfsSettingsOpen,
      setLfsSettingsOpen,
      createBranchOpen,
      setCreateBranchOpen,
      trackingBranch,
      setTrackingBranch,
      renameBranch,
      setRenameBranch,
      deleteBranch,
      setDeleteBranch,
      publishBranchOpen,
      setPublishBranchOpen,
      discardPaths,
      setDiscardPaths,
      abortConflictOpen,
      setAbortConflictOpen,
      revertCommit,
      setRevertCommit,
    },
  };
}

export type VersionControlWorkbenchController = ReturnType<typeof useVersionControlWorkbenchController>;
