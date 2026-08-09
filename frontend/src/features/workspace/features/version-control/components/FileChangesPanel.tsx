/**
 *
 *
 */

import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileChangesPanel');
import { Loader2, Settings } from 'lucide-react';
import { useToast } from '@/shared/components/ui/use-toast';
import { GitContextSelector } from './GitContextSelector';
import { RepositoryNotInitializedEmptyState } from './RepositoryNotInitializedEmptyState';
import { WorktreeSettingsDialog } from './WorktreeSettingsDialog';
import {
  VersionControlChangesSidebar,
  VersionControlChangesSkeleton,
  createVersionControlActionItems,
  VersionControlDialogHost,
  useVersionControlBranchMutationBindings,
  useVersionControlChangeMutationBindings,
  useVersionControlLfsDialogBinding,
  useVersionControlPagedChanges,
  useVersionControlStatusQueryBindings,
  useVersionControlWorkbenchController,
  type VersionControlActionMenuExtensionItem,
  type VersionControlCreateBranchPayload,
  type VersionControlFileGroup,
} from '@/shared/components/version-control';
import {
  getVersionControlErrorMessageKey,
  isVersionControlOperationInProgressError,
  type VersionControlFileChange,
} from '@/shared/version-control';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useQueryClient } from '@tanstack/react-query';
import { isVersionControlNotInitializedError } from '../model/versionControlModel';

interface FileChangesPanelProps {
  onFileSelect?: (file: VersionControlFileChange | null) => void;
}

const DEFAULT_BRANCH = 'main';
const VERSION_CONTROL_OPERATION_LOCKED_CODE = 'operation_locked';

/**
 */
export const FileChangesPanel: React.FC<FileChangesPanelProps> = ({ onFileSelect }) => {
  // ==================== State Management ====================

  const [worktreeSettingsOpen, setWorktreeSettingsOpen] = useState(false);
  const [pendingHeaderAction, setPendingHeaderAction] = useState<'stageAll' | 'unstageAll' | null>(null);

  // ==================== Refs ====================

  const previousViewIdentityRef = useRef<string | null>(null);

  // ==================== Hooks ====================

  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, state, permissions } = useWorkspace();
  const canWrite = permissions.canWrite;
  const queryClient = useQueryClient();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const selectedGitContextId = state.versionControl.selectedGitContextId;
  const vc = useWorkspaceVersionControlSession({
    workspaceId,
    runtimeBaseUrl,
    contextId: selectedGitContextId,
  });

  const pagedChanges = useVersionControlPagedChanges(vc.changes);
  const {
    staged: stagedChangesQuery,
    unstaged: unstagedChangesQuery,
    untracked: untrackedChangesQuery,
  } = pagedChanges.queries;
  const changesQueries = pagedChanges.queries.all;

  const branchesQuery = vc.history.useBranchesQuery({
    includeRemote: true,
    includeMetadata: false,
  });
  const { statusQuery, operationStatusQuery } = useVersionControlStatusQueryBindings(vc.changes);

  const {
    stageMutation,
    unstageMutation,
    commitMutation,
    discardMutation,
    markResolvedMutation,
    abortConflictMutation,
    forceUnlockMutation,
  } = useVersionControlChangeMutationBindings(vc.changes);
  const {
    createBranchMutation,
    switchBranchMutation,
    renameBranchMutation,
    deleteBranchMutation,
    publishBranchMutation,
  } = useVersionControlBranchMutationBindings(vc.history);
  const fetchMutation = vc.remote.useFetchMutation();
  const pullMutation = vc.remote.usePullMutation();
  const pushMutation = vc.remote.usePushMutation();
  const setRemoteUrlMutation = vc.remote.useSetRemoteUrlMutation();

  // ==================== Computed Data ====================

  const {
    staged: stagedFiles,
    unstaged: unstagedFiles,
    untracked: untrackedFiles,
    conflicts: conflictFiles,
  } = pagedChanges.files;

  const branches = useMemo(() => branchesQuery.data ?? [], [branchesQuery.data]);
  const currentBranch = useMemo(() => {
    const activeBranch = branches.find(b => b.isCurrent);
    return activeBranch?.name ?? statusQuery.data?.currentBranch ?? DEFAULT_BRANCH;
  }, [branches, statusQuery.data]);

  const allUnstagedFiles = useMemo(
    () => [...unstagedFiles, ...untrackedFiles],
    [unstagedFiles, untrackedFiles]
  );
  const stagedTotalCount = statusQuery.data?.stagedTotal ?? stagedChangesQuery.data?.staged.total ?? stagedFiles.length;
  const unstagedTotalCount = (
    statusQuery.data?.unstagedTotal ?? unstagedChangesQuery.data?.unstaged.total ?? unstagedFiles.length
  ) + (
    statusQuery.data?.untrackedTotal ?? untrackedChangesQuery.data?.untracked.total ?? untrackedFiles.length
  );
  const activeOperation = operationStatusQuery.data?.isActive ? operationStatusQuery.data.operation : null;
  const isOperationActive = operationStatusQuery.data?.isActive === true;
  const isStageAllPending = pendingHeaderAction === 'stageAll' || activeOperation === 'changes.stageAll';
  const isUnstageAllPending = pendingHeaderAction === 'unstageAll' || activeOperation === 'changes.unstageAll';

  const controller = useVersionControlWorkbenchController({
    mode: 'changes',
    stagedFiles,
    unstagedFiles: allUnstagedFiles,
    onFileSelect: (file) => onFileSelect?.(file),
  });
  const { dialogs, pending, selection: fileSelection } = controller;
  const lfs = useVersionControlLfsDialogBinding({
    remote: vc.remote,
    controller,
    requestIdentity: `workspace:${workspaceId}:${selectedGitContextId ?? 'primary'}`,
    operationStatus: statusQuery.data?.operationStatus,
  });
  const { clearSelection } = fileSelection;
  const remoteSettingsQuery = vc.remote.useRemoteSettingsQuery(dialogs.remoteSettingsOpen);

  const isMutating = commitMutation.isPending
    || stageMutation.isPending
    || unstageMutation.isPending
    || discardMutation.isPending
    || markResolvedMutation.isPending
    || abortConflictMutation.isPending
    || createBranchMutation.isPending
    || switchBranchMutation.isPending
    || renameBranchMutation.isPending
    || deleteBranchMutation.isPending
    || publishBranchMutation.isPending
    || fetchMutation.isPending
    || pullMutation.isPending
    || pushMutation.isPending
    || setRemoteUrlMutation.isPending
    || lfs.isPending
    || isOperationActive;

  const showGitMutationErrorToast = useCallback((
    error: unknown,
    fallbackTitleKey: string,
    fallbackDescriptionKey: string,
  ) => {
    if (isVersionControlOperationInProgressError(error, VERSION_CONTROL_OPERATION_LOCKED_CODE)) {
      toast({
        title: t('workspace.versionControl.toasts.operationInProgress.title'),
        description: t('workspace.versionControl.toasts.operationInProgress.description'),
        variant: 'destructive',
      });
      return;
    }

    toast({
      title: t(fallbackTitleKey),
      description: t(getVersionControlErrorMessageKey(error) ?? fallbackDescriptionKey),
      variant: 'destructive',
    });
  }, [t, toast]);

  // ==================== Event Handlers ====================

  const resetPagination = pagedChanges.reset;

  useEffect(() => {
    resetPagination();
  }, [resetPagination, selectedGitContextId]);

  useEffect(() => {
    const currentViewIdentity = `${selectedGitContextId ?? 'primary'}::${currentBranch}`;
    const previousViewIdentity = previousViewIdentityRef.current;
    previousViewIdentityRef.current = currentViewIdentity;

    if (previousViewIdentity === null || previousViewIdentity === currentViewIdentity) {
      return;
    }

    clearSelection();
    onFileSelect?.(null);
  }, [clearSelection, currentBranch, onFileSelect, selectedGitContextId]);

  const handleBranchChange = useCallback(async (branch: string) => {
    if (!canWrite || branch === currentBranch) return;

    try {
      await switchBranchMutation.mutateAsync({ name: branch });
      resetPagination();
      toast({
        title: t('workspace.versionControl.toasts.checkoutSuccess.title'),
        description: t('workspace.versionControl.toasts.checkoutSuccess.description', { branch }),
        variant: 'success',
      });
    } catch (err) {
      logger.error('Branch change error', { error: err });
      showGitMutationErrorToast(
        err,
        'workspace.versionControl.toasts.checkoutFailed.title',
        'workspace.versionControl.toasts.checkoutFailed.description',
      );
    }
  }, [canWrite, currentBranch, resetPagination, showGitMutationErrorToast, switchBranchMutation, t, toast]);

  const handleRefresh = useCallback(async () => {
    try {
      await vc.refresh(queryClient, ['changes', 'history', 'remote']);
      toast({ title: t('workspace.versionControl.toasts.refreshSuccess.title'), variant: 'success' });
    } catch (err) {
      logger.error('Git refresh error', { error: err });
      toast({
        title: t('workspace.versionControl.toasts.refreshFailed.title'),
        description: t(getVersionControlErrorMessageKey(err) ?? 'workspace.versionControl.toasts.refreshFailed.description'),
        variant: 'destructive',
      });
    }
  }, [queryClient, t, toast, vc]);

  const addPendingPaths = pending.addPaths;
  const removePendingPaths = pending.removePaths;

  const handleGitAction = useCallback(async (action: 'fetch' | 'pull' | 'push') => {
    if (!canWrite) {
      return;
    }
    try {
      if (action === 'fetch') {
        await fetchMutation.mutateAsync({ remote: 'origin' });
      } else if (action === 'pull') {
        await pullMutation.mutateAsync({ remote: 'origin', branch: currentBranch });
      } else {
        if (!statusQuery.data?.upstream) {
          dialogs.setPublishBranchOpen(true);
          return;
        }
        await pushMutation.mutateAsync({ remote: 'origin', branch: currentBranch });
      }
      resetPagination();
      toast({ title: t(`workspace.versionControl.toasts.${action}Success.title`), variant: 'success' });
    } catch (err) {
      logger.error(`Git ${action} error`, { error: err });
      showGitMutationErrorToast(
        err,
        `workspace.versionControl.toasts.${action}Failed.title`,
        `workspace.versionControl.toasts.${action}Failed.description`,
      );
    }
  }, [canWrite, currentBranch, fetchMutation, pullMutation, pushMutation, resetPagination, showGitMutationErrorToast, statusQuery.data?.upstream, t, toast]);

  const handleRenameBranch = useCallback(async (newName: string) => {
    if (!dialogs.renameBranch) return;
    await renameBranchMutation.mutateAsync({ oldName: dialogs.renameBranch.name, newName });
    toast({ title: t('shared.versionControl.branch.rename.success'), variant: 'success' });
  }, [dialogs.renameBranch, renameBranchMutation, t, toast]);

  const handleDeleteBranch = useCallback(async () => {
    if (!dialogs.deleteBranch) return;
    await deleteBranchMutation.mutateAsync({ name: dialogs.deleteBranch.name });
    toast({ title: t('shared.versionControl.branch.delete.success'), variant: 'success' });
  }, [deleteBranchMutation, dialogs.deleteBranch, t, toast]);

  const handlePublishBranch = useCallback(async (remote: string, remoteName?: string) => {
    await publishBranchMutation.mutateAsync({ remote, remoteName });
    toast({ title: t('shared.versionControl.branch.publish.success'), variant: 'success' });
  }, [publishBranchMutation, t, toast]);

  const handleSetRemoteUrl = useCallback(async (remoteUrl: string) => {
    if (!canWrite) {
      return;
    }
    try {
      await setRemoteUrlMutation.mutateAsync(remoteUrl.trim());
      dialogs.setRemoteSettingsOpen(false);
      toast({
        title: t('workspace.versionControl.toasts.remoteUrlSuccess.title'),
        variant: 'success',
      });
    } catch (err) {
      logger.error('Set remote URL error', { error: err });
      showGitMutationErrorToast(
        err,
        'workspace.versionControl.toasts.remoteUrlFailed.title',
        'workspace.versionControl.toasts.remoteUrlFailed.description',
      );
    }
  }, [canWrite, dialogs.setRemoteSettingsOpen, setRemoteUrlMutation, showGitMutationErrorToast, t, toast]);

  const handleCreateBranch = useCallback(async ({
    branch,
    startPoint,
  }: VersionControlCreateBranchPayload) => {
    if (!canWrite || !branch) return;

    try {
      await createBranchMutation.mutateAsync({
        name: branch,
        startPoint: startPoint ?? undefined,
      });
      resetPagination();
      dialogs.setCreateBranchOpen(false);
      toast({
        title: t('workspace.versionControl.toasts.createBranchSuccess.title'),
        description: t('workspace.versionControl.toasts.createBranchSuccess.description', { branch }),
        variant: 'success',
      });
    } catch (err) {
      logger.error('Create branch error', { error: err });
      showGitMutationErrorToast(
        err,
        'workspace.versionControl.toasts.createBranchFailed.title',
        'workspace.versionControl.toasts.createBranchFailed.description',
      );
    }
  }, [canWrite, createBranchMutation, dialogs.setCreateBranchOpen, resetPagination, showGitMutationErrorToast, t, toast]);

  const handleFileSelect = useCallback((
    file: VersionControlFileChange,
    type: VersionControlFileGroup,
    event?: React.MouseEvent
  ) => {
    fileSelection.selectFile(file, type, event);
  }, [fileSelection]);

  const handleStageToggle = useCallback(async (file: VersionControlFileChange, type: VersionControlFileGroup) => {
    if (!canWrite) {
      return;
    }
    const pathsToProcess = fileSelection.getActionPaths(file, type);
    const oppositeType: VersionControlFileGroup = type === 'staged' ? 'unstaged' : 'staged';
    addPendingPaths(type, pathsToProcess);
    addPendingPaths(oppositeType, pathsToProcess);

    try {
      if (type === 'staged') {
        await unstageMutation.mutateAsync(pathsToProcess);
        fileSelection.clearSelection('staged');
      } else {
        await stageMutation.mutateAsync(pathsToProcess);
        fileSelection.clearSelection('unstaged');
      }
      resetPagination();
    } catch (error) {
      logger.error('Stage/unstage failed', { error });
      showGitMutationErrorToast(
        error,
        type === 'staged'
          ? 'workspace.versionControl.toasts.unstageFailed.title'
          : 'workspace.versionControl.toasts.stageFailed.title',
        type === 'staged'
          ? 'workspace.versionControl.toasts.unstageFailed.description'
          : 'workspace.versionControl.toasts.stageFailed.description',
      );
      void vc.refresh(queryClient, ['changes'])
        .catch(refreshError => logger.error('Version control refresh after file action failed', { error: refreshError }));
    } finally {
      removePendingPaths(type, pathsToProcess);
      removePendingPaths(oppositeType, pathsToProcess);
    }
  }, [
    addPendingPaths,
    canWrite,
    fileSelection,
    queryClient,
    removePendingPaths,
    resetPagination,
    showGitMutationErrorToast,
    stageMutation,
    unstageMutation,
    vc,
  ]);

  const handleStageAll = useCallback(async () => {
    if (!canWrite || unstagedTotalCount === 0) return;

    setPendingHeaderAction('stageAll');
    try {
      await stageMutation.mutateAsync({ all: true });
      fileSelection.clearSelection('unstaged');
      resetPagination();
    } catch (error) {
      logger.error('Stage all failed', { error });
      showGitMutationErrorToast(
        error,
        'workspace.versionControl.toasts.stageFailed.title',
        'workspace.versionControl.toasts.stageFailed.description',
      );
    } finally {
      setPendingHeaderAction(null);
    }
  }, [canWrite, fileSelection, resetPagination, showGitMutationErrorToast, stageMutation, unstagedTotalCount]);

  const handleUnstageAll = useCallback(async () => {
    if (!canWrite || stagedTotalCount === 0) return;

    setPendingHeaderAction('unstageAll');
    try {
      await unstageMutation.mutateAsync({ all: true });
      fileSelection.clearSelection('staged');
      resetPagination();
    } catch (error) {
      logger.error('Unstage all failed', { error });
      showGitMutationErrorToast(
        error,
        'workspace.versionControl.toasts.unstageFailed.title',
        'workspace.versionControl.toasts.unstageFailed.description',
      );
    } finally {
      setPendingHeaderAction(null);
    }
  }, [canWrite, fileSelection, resetPagination, showGitMutationErrorToast, stagedTotalCount, unstageMutation]);

  const handleDiscard = useCallback((file: VersionControlFileChange) => {
    if (!canWrite) {
      return;
    }
    dialogs.setDiscardPaths(fileSelection.getActionPaths(file, 'unstaged'));
  }, [canWrite, dialogs.setDiscardPaths, fileSelection]);

  const handleMarkResolved = useCallback(async (file: VersionControlFileChange) => {
    if (!canWrite) return;
    const paths = fileSelection.getActionPaths(file, 'unstaged');
    await markResolvedMutation.mutateAsync(paths);
    clearSelection();
  }, [canWrite, clearSelection, fileSelection, markResolvedMutation]);

  const confirmDiscard = useCallback(async (pathsToDiscard: string[]) => {
    try {
      await discardMutation.mutateAsync(pathsToDiscard);
      fileSelection.clearSelection('unstaged');
      onFileSelect?.(null);
      resetPagination();
    } catch (error) {
      logger.error('Discard failed', { error });
      throw error;
    }
  }, [discardMutation, fileSelection, onFileSelect, resetPagination]);

  const handleCommit = useCallback(async (data: { message: string }) => {
    if (!canWrite) {
      return;
    }
    try {
      await commitMutation.mutateAsync(data.message);
      fileSelection.clearSelection();
      onFileSelect?.(null);
      resetPagination();
      toast({ title: t('workspace.versionControl.toasts.commitSuccess.title'), variant: 'success' });
    } catch (error) {
      logger.error('Commit failed', { error });
      showGitMutationErrorToast(
        error,
        'workspace.versionControl.toasts.commitFailed.title',
        'workspace.versionControl.toasts.commitFailed.description',
      );
    }
  }, [canWrite, commitMutation, fileSelection, onFileSelect, resetPagination, showGitMutationErrorToast, t, toast]);

  const handleForceUnlock = useCallback(async () => {
    await forceUnlockMutation.mutateAsync();
    toast({ title: t('shared.versionControl.conflict.forceUnlockSuccess.title'), variant: 'success' });
  }, [forceUnlockMutation, t, toast]);

  // ==================== Early Returns ====================

  // First load only: show a skeleton when loading with no previous data yet.
  // placeholderData: (prev) => prev keeps prior data on refetch, so a refetch
  // (isLoading && previousData) falls through and keeps rendering the panel.
  const isFirstLoad = pagedChanges.isFirstLoad
    || (branchesQuery.isLoading && changesQueries.every(query => !query.data));
  if (isFirstLoad) {
    return <VersionControlChangesSkeleton />;
  }

  const isRepositoryNotInitialized = statusQuery.data?.isInitialized === false;

  if (isRepositoryNotInitialized) {
    return <RepositoryNotInitializedEmptyState />;
  }

  const changesError = pagedChanges.error;
  if (changesError || branchesQuery.error) {
    const error = changesError ?? branchesQuery.error;
    const isNotInitialized = isVersionControlNotInitializedError(error);

    if (isNotInitialized) {
      return <RepositoryNotInitializedEmptyState />;
    }

    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-destructive">
          {t(getVersionControlErrorMessageKey(error) ?? 'workspace.versionControl.errors.loadFailed')}
        </div>
      </div>
    );
  }

  // ==================== Main Render ====================

  const actionItems = createVersionControlActionItems({
    refresh: { onClick: () => void handleRefresh() },
    fetch: { onClick: () => void handleGitAction('fetch'), disabled: !canWrite },
    pull: { onClick: () => void handleGitAction('pull'), disabled: !canWrite },
    push: { onClick: () => void handleGitAction('push'), disabled: !canWrite },
    ...(permissions.canManageSettings ? {
      remoteSettings: { onClick: () => dialogs.setRemoteSettingsOpen(true) },
      lfs: { onClick: lfs.open, disabled: lfs.isPending },
    } : {}),
  });
  const actionExtensions: VersionControlActionMenuExtensionItem[] = permissions.canManageSettings
    ? [{
      key: 'worktree-settings',
      labelKey: 'workspace.versionControl.worktree.menu.settings',
      icon: <Settings className="h-3 w-3" />,
      onClick: () => setWorktreeSettingsOpen(true),
    }]
    : [];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1">
      <VersionControlChangesSidebar
        contextSlot={<GitContextSelector />}
        branches={branches}
        currentBranch={currentBranch}
        actions={actionItems}
        actionExtensions={actionExtensions}
        stagedFiles={stagedFiles}
        unstagedFiles={allUnstagedFiles}
        stagedCount={stagedTotalCount}
        unstagedCount={unstagedTotalCount}
        conflictFiles={conflictFiles}
        selectedStagedPath={fileSelection.selectedStagedPath}
        selectedUnstagedPath={fileSelection.selectedUnstagedPath}
        selectedStagedPaths={fileSelection.selectedStagedPaths}
        selectedUnstagedPaths={fileSelection.selectedUnstagedPaths}
        pendingStagedPaths={pending.stagedPaths}
        pendingUnstagedPaths={pending.unstagedPaths}
        isMutating={isMutating}
        isCommitting={commitMutation.isPending}
        isStageAllPending={isStageAllPending}
        isUnstageAllPending={isUnstageAllPending}
        mutationDisabled={!canWrite}
        operationStatus={operationStatusQuery.data ?? null}
        onForceUnlock={permissions.canManageSettings ? handleForceUnlock : undefined}
        onBranchChange={handleBranchChange}
        onCreateBranch={() => dialogs.setCreateBranchOpen(true)}
        onRenameBranch={dialogs.setRenameBranch}
        onDeleteBranch={dialogs.setDeleteBranch}
        onCreateTrackingBranch={dialogs.setTrackingBranch}
        onCommit={handleCommit}
        onFileSelect={handleFileSelect}
        onStageToggle={handleStageToggle}
        onMarkResolved={handleMarkResolved}
        onAbortConflict={() => dialogs.setAbortConflictOpen(true)}
        onDiscard={handleDiscard}
        onStageAll={handleStageAll}
        onUnstageAll={handleUnstageAll}
        stagedFooter={(
          <>
            {stagedChangesQuery.data?.staged.hasMore && (
              <div ref={pagedChanges.loadMore.stagedRef} className="h-1" />
            )}
            {stagedChangesQuery.isFetching && stagedChangesQuery.data?.staged.hasMore && (
              <div className="text-center py-2 text-muted-foreground text-sm">
                <Loader2 className="inline-block w-4 h-4 animate-spin mr-2" />
                {t('shared.versionControl.fileChanges.loadingMore')}
              </div>
            )}
          </>
        )}
        unstagedFooter={(
          <>
            {(unstagedChangesQuery.data?.unstaged.hasMore || untrackedChangesQuery.data?.untracked.hasMore) && (
              <div ref={pagedChanges.loadMore.unstagedRef} className="h-1" />
            )}
            {(unstagedChangesQuery.isFetching || untrackedChangesQuery.isFetching)
              && (unstagedChangesQuery.data?.unstaged.hasMore || untrackedChangesQuery.data?.untracked.hasMore) && (
              <div className="text-center py-2 text-muted-foreground text-sm">
                <Loader2 className="inline-block w-4 h-4 animate-spin mr-2" />
                {t('shared.versionControl.fileChanges.loadingMore')}
              </div>
            )}
          </>
        )}
      />
      </div>
      {canWrite ? (
      <>
      <VersionControlDialogHost
        controller={controller}
        activeBranch={currentBranch}
        repository={{
          currentBranch: remoteSettingsQuery.data?.currentBranch ?? currentBranch,
          remoteUrl: remoteSettingsQuery.data?.remoteUrl ?? null,
          hasOrigin: remoteSettingsQuery.data?.hasOrigin ?? Boolean(remoteSettingsQuery.data?.remoteUrl),
        }}
        canManageRemote
        onSaveRemoteUrl={handleSetRemoteUrl}
        isSavingRemoteUrl={setRemoteUrlMutation.isPending}
        onCreateBranch={handleCreateBranch}
        isCreatingBranch={createBranchMutation.isPending}
        supportsBranchStartPoint
        onRenameBranch={handleRenameBranch}
        onDeleteBranch={handleDeleteBranch}
        onPublishBranch={handlePublishBranch}
        onDiscard={confirmDiscard}
        onAbortConflict={() => abortConflictMutation.mutateAsync()}
        lfs={lfs.dialog}
      />
      <WorktreeSettingsDialog
        open={worktreeSettingsOpen}
        workspaceId={workspaceId}
        onOpenChange={setWorktreeSettingsOpen}
        onSaved={workspaceRuntime.reload}
      />
      </>
      ) : null}
    </div>
  );
};
