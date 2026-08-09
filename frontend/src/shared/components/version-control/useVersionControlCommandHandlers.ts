import { useCallback } from 'react';
import type { VersionControlFileChange } from '@/shared/version-control';
import type { VersionControlWorkbenchController } from './useVersionControlWorkbenchController';
import type { VersionControlFileGroup } from './useVersionControlFileSelection';

interface CommandMutationOptions {
  kind?: 'commit' | 'stageAll' | 'unstageAll' | 'other';
}

interface UseVersionControlChangeCommandsOptions {
  controller: VersionControlWorkbenchController;
  canMutate: boolean;
  runMutation: (operation: Promise<unknown>, options?: CommandMutationOptions) => Promise<boolean>;
  stage: (payload: string[] | { all: true }) => Promise<unknown>;
  unstage: (payload: string[] | { all: true }) => Promise<unknown>;
  discard: (paths: string[]) => Promise<unknown>;
  markResolved: (paths: string[]) => Promise<unknown>;
}

type BranchCommand = 'switch' | 'create' | 'rename' | 'delete' | 'publish';

interface UseVersionControlBranchCommandsOptions {
  controller: VersionControlWorkbenchController;
  canMutate: boolean;
  currentBranch: string;
  runMutation: (operation: Promise<unknown>, options?: CommandMutationOptions) => Promise<boolean>;
  switchBranch: (name: string) => Promise<unknown>;
  createBranch: (payload: { name: string; startPoint?: string }) => Promise<unknown>;
  renameBranch: (payload: { oldName: string; newName: string }) => Promise<unknown>;
  deleteBranch: (name: string) => Promise<unknown>;
  publishBranch: (payload: { remote?: string; remoteName?: string }) => Promise<unknown>;
  onSuccess?: (command: BranchCommand) => void;
}

export const useVersionControlChangeCommands = ({
  controller,
  canMutate,
  runMutation,
  stage,
  unstage,
  discard,
  markResolved,
}: UseVersionControlChangeCommandsOptions) => {
  const { dialogs, pending, selection } = controller;

  const handleStageToggle = useCallback((
    file: VersionControlFileChange,
    group: VersionControlFileGroup,
  ) => {
    if (!canMutate) return;
    const paths = selection.getActionPaths(file, group);
    const oppositeGroup: VersionControlFileGroup = group === 'staged' ? 'unstaged' : 'staged';
    pending.addPaths(group, paths);
    pending.addPaths(oppositeGroup, paths);
    void runMutation(group === 'staged' ? unstage(paths) : stage(paths))
      .then(succeeded => {
        if (succeeded) selection.clearChangeSelection();
      })
      .finally(() => {
        pending.removePaths(group, paths);
        pending.removePaths(oppositeGroup, paths);
      });
  }, [canMutate, pending, runMutation, selection, stage, unstage]);

  const handleStageAll = useCallback(() => {
    if (!canMutate) return;
    void runMutation(stage({ all: true }), { kind: 'stageAll' })
      .then(succeeded => {
        if (succeeded) selection.clearChangeSelection();
      });
  }, [canMutate, runMutation, selection, stage]);

  const handleUnstageAll = useCallback(() => {
    if (!canMutate) return;
    void runMutation(unstage({ all: true }), { kind: 'unstageAll' })
      .then(succeeded => {
        if (succeeded) selection.clearChangeSelection();
      });
  }, [canMutate, runMutation, selection, unstage]);

  const handleDiscard = useCallback((file: VersionControlFileChange) => {
    if (!canMutate) return;
    dialogs.setDiscardPaths(selection.getActionPaths(file, 'unstaged'));
  }, [canMutate, dialogs, selection]);

  const handleMarkResolved = useCallback((file: VersionControlFileChange) => {
    if (!canMutate) return;
    const paths = selection.getActionPaths(file, 'unstaged');
    void runMutation(markResolved(paths));
  }, [canMutate, markResolved, runMutation, selection]);

  const confirmDiscard = useCallback(async (paths: string[]) => {
    await discard(paths);
    selection.clearChangeSelection();
  }, [discard, selection]);

  return {
    handleStageToggle,
    handleStageAll,
    handleUnstageAll,
    handleDiscard,
    handleMarkResolved,
    confirmDiscard,
  };
};

export const useVersionControlBranchCommands = ({
  controller,
  canMutate,
  currentBranch,
  runMutation,
  switchBranch,
  createBranch,
  renameBranch,
  deleteBranch,
  publishBranch,
  onSuccess,
}: UseVersionControlBranchCommandsOptions) => {
  const { dialogs, selection } = controller;

  const handleSwitchBranch = useCallback((branch: string) => {
    if (!canMutate || branch === currentBranch) return;
    void runMutation(switchBranch(branch)).then(succeeded => {
      if (!succeeded) return;
      selection.clearChangeSelection();
      onSuccess?.('switch');
    });
  }, [canMutate, currentBranch, onSuccess, runMutation, selection, switchBranch]);

  const handleCreateBranch = useCallback(async ({
    branch,
    startPoint,
  }: { branch: string; startPoint?: string }) => {
    if (!canMutate) return;
    await createBranch({ name: branch, startPoint });
    selection.clearChangeSelection();
    onSuccess?.('create');
  }, [canMutate, createBranch, onSuccess, selection]);

  const handleRenameBranch = useCallback(async (newName: string) => {
    if (!canMutate || !dialogs.renameBranch) return;
    await renameBranch({ oldName: dialogs.renameBranch.name, newName });
    onSuccess?.('rename');
  }, [canMutate, dialogs.renameBranch, onSuccess, renameBranch]);

  const handleDeleteBranch = useCallback(async () => {
    if (!canMutate || !dialogs.deleteBranch) return;
    await deleteBranch(dialogs.deleteBranch.name);
    onSuccess?.('delete');
  }, [canMutate, deleteBranch, dialogs.deleteBranch, onSuccess]);

  const handlePublishBranch = useCallback(async (remote: string, remoteName?: string) => {
    if (!canMutate) return;
    await publishBranch({ remote, remoteName });
    onSuccess?.('publish');
  }, [canMutate, onSuccess, publishBranch]);

  return {
    handleSwitchBranch,
    handleCreateBranch,
    handleRenameBranch,
    handleDeleteBranch,
    handlePublishBranch,
  };
};
