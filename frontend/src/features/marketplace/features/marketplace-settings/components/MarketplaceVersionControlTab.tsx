import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { useToast } from '@/shared/components/ui/use-toast';
import {
  VersionControlChangesSidebar,
  VersionControlChangesSkeleton,
  createVersionControlActionItems,
  VersionControlDialogHost,
  VersionControlHistorySidebar,
  VersionControlMainDiff,
  VersionControlRefreshButton,
  VersionControlRepositorySetup,
  useVersionControlBranchCommands,
  useVersionControlBranchMutationBindings,
  useVersionControlChangeCommands,
  useVersionControlChangeMutationBindings,
  useVersionControlLfsDialogBinding,
  useVersionControlProductQueryBindings,
  useVersionControlWorkbenchModel,
  type VersionControlFileGroup,
  type VersionControlWorkbenchMode,
} from '@/shared/components/version-control';
import {
  getVersionControlErrorMessageKey,
  isHttpStatusError,
  isVersionControlOperationInProgressError,
  useMarketplaceVersionControlSession,
  type RepositorySetupMutationKind,
  type VersionControlBranch,
  type VersionControlCommitSummary,
  type VersionControlFileChange,
  type VersionControlRepositoryStatus,
} from '@/shared/version-control';
import { useI18n } from '@/shared/hooks/useI18n';

type MarketplaceVersionControlError = 'permissionDenied';
const VERSION_CONTROL_OPERATION_LOCKED_CODE = 'operation_locked';

interface MarketplaceVersionControlTabProps {
  repository: VersionControlRepositoryStatus | null;
  onRepositoryChange: (repository: VersionControlRepositoryStatus) => void;
  mode: VersionControlWorkbenchMode;
  renderSurface?: (surface: MarketplaceVersionControlRenderSurface) => React.ReactNode;
}

export interface MarketplaceVersionControlSurface {
  kind?: 'regions';
  navigator: React.ReactNode;
  navigatorActions: React.ReactNode;
  main: React.ReactNode;
  dialogs: React.ReactNode;
}

export interface MarketplaceVersionControlStateSurface {
  kind: 'state';
  content: React.ReactNode;
}

export type MarketplaceVersionControlRenderSurface =
  | MarketplaceVersionControlSurface
  | MarketplaceVersionControlStateSurface;

export const MarketplaceVersionControlTab: React.FC<MarketplaceVersionControlTabProps> = ({
  repository,
  onRepositoryChange,
  mode,
  renderSurface,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [operationError, setOperationError] = useState<MarketplaceVersionControlError | null>(null);
  const [registryMutationAllowed, setRegistryMutationAllowed] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const vc = useMarketplaceVersionControlSession({
    isGitRepo: !!repository?.isGitRepo,
  });
  const repositoryQuery = vc.remote.useRepositoryQuery();
  const {
    changesQuery,
    statusQuery,
    operationStatusQuery,
    branchesQuery,
    commitsQuery,
  } = useVersionControlProductQueryBindings(vc.changes, vc.history, {
    commitsLimit: 50,
    includeRemoteBranches: true,
    includeBranchMetadata: true,
  });
  const {
    stageMutation,
    unstageMutation,
    discardMutation,
    markResolvedMutation,
    abortConflictMutation,
    forceUnlockMutation,
    commitMutation,
  } = useVersionControlChangeMutationBindings(vc.changes);
  const revertCommitMutation = vc.history.useRevertCommitMutation();
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
  const initializeRepositoryMutation = vc.remote.useInitializeRepositoryMutation();
  const cloneRepositoryMutation = vc.remote.useCloneRepositoryMutation();
  const remoteBranchesMutation = vc.remote.useRemoteBranchesMutation();

  const currentRepository = repositoryQuery.data ?? repository;
  const branches = branchesQuery.data ?? [];
  const currentBranch = branches.find(branch => branch.isCurrent)?.name
    ?? statusQuery.data?.currentBranch
    ?? currentRepository?.currentBranch
    ?? '';
  const commits: VersionControlCommitSummary[] = useMemo(
    () => currentRepository?.isGitRepo
      ? (commitsQuery.data?.items ?? []).map(commit => ({
        ...commit,
        branch: commit.branch ?? (currentBranch || null),
      }))
      : [],
    [commitsQuery.data?.items, currentBranch, currentRepository?.isGitRepo],
  );
  const isOperationActive = operationStatusQuery.data?.isActive === true;

  useEffect(() => {
    if (repositoryQuery.data) {
      onRepositoryChange(repositoryQuery.data);
    }
  }, [onRepositoryChange, repositoryQuery.data]);

  const {
    changes,
    stagedFiles,
    unstagedFiles,
    conflictFiles,
    numstatParams,
    controller,
  } = useVersionControlWorkbenchModel({
    mode,
    changes: changesQuery.data,
    status: statusQuery.data,
    branches,
    repository: currentRepository,
    commits,
  });
  vc.changes.useChangesNumstatQuery(numstatParams);
  const { dialogs, mutation, pending, selection } = controller;
  const lfs = useVersionControlLfsDialogBinding({
    remote: vc.remote,
    controller,
    requestIdentity: 'marketplace-registry',
    operationStatus: statusQuery.data?.operationStatus,
  });
  const commitFilesQuery = vc.history.useCommitFilesQuery(selection.selectedCommitId);
  const commitFiles: VersionControlFileChange[] = commitFilesQuery.data ?? [];
  const selectedDiffFile = selection.selectedDiffFile;
  const workingDiffQuery = vc.changes.useDiffQuery({
    path: mode === 'changes' ? selectedDiffFile?.path ?? null : null,
    head: selection.selectedGroup === 'staged' ? 'INDEX' : 'WORKTREE',
  });
  const commitDiffQuery = vc.history.useCommitDiffQuery({
    path: mode === 'history' ? selectedDiffFile?.path ?? null : null,
    commitId: selection.selectedCommitId,
  });
  const diffContent = mode === 'history'
    ? commitDiffQuery.data?.patch || commitDiffQuery.data?.diff || ''
    : workingDiffQuery.data?.patch || workingDiffQuery.data?.diff || '';

  const runMutation = useCallback(async (
    mutationPromise: Promise<unknown>,
    options?: {
      kind?: 'commit' | 'stageAll' | 'unstageAll' | 'other';
      onError?: () => void | Promise<void>;
    },
  ) => {
    return mutation.run(mutationPromise, {
      kind: options?.kind,
      onSuccess: () => setOperationError(null),
      onError: async (err) => {
        if (isVersionControlOperationInProgressError(err, VERSION_CONTROL_OPERATION_LOCKED_CODE)) {
          toast({
            title: t('marketplace.settings.versionControl.toasts.operationInProgress.title'),
            description: t('marketplace.settings.versionControl.toasts.operationInProgress.description'),
            variant: 'destructive',
          });
          return;
        }
        if (isHttpStatusError(err, 403)) {
          setRegistryMutationAllowed(false);
          setOperationError('permissionDenied');
          return;
        }
        await options?.onError?.();
        toast({
          title: t('marketplace.settings.versionControl.toasts.operationFailed.title'),
          description: t(
            getVersionControlErrorMessageKey(err)
              ?? 'marketplace.settings.versionControl.toasts.operationFailed.description',
          ),
          variant: 'destructive',
        });
      },
    });
  }, [mutation, t, toast]);

  const {
    handleStageToggle,
    handleStageAll,
    handleUnstageAll,
    handleDiscard,
    handleMarkResolved,
    confirmDiscard,
  } = useVersionControlChangeCommands({
    controller,
    canMutate: registryMutationAllowed,
    runMutation,
    stage: stageMutation.mutateAsync,
    unstage: unstageMutation.mutateAsync,
    discard: discardMutation.mutateAsync,
    markResolved: markResolvedMutation.mutateAsync,
  });
  const handleForceUnlock = async () => {
    await forceUnlockMutation.mutateAsync();
    toast({ title: t('shared.versionControl.conflict.forceUnlockSuccess.title'), variant: 'success' });
  };
  const handleCommit = (data: { message: string }) => {
    void runMutation(commitMutation.mutateAsync(data.message), { kind: 'commit' });
  };
  const {
    handleSwitchBranch,
    handleCreateBranch,
    handleRenameBranch,
    handleDeleteBranch,
    handlePublishBranch,
  } = useVersionControlBranchCommands({
    controller,
    canMutate: registryMutationAllowed,
    currentBranch,
    runMutation,
    switchBranch: name => switchBranchMutation.mutateAsync({ name }),
    createBranch: createBranchMutation.mutateAsync,
    renameBranch: renameBranchMutation.mutateAsync,
    deleteBranch: name => deleteBranchMutation.mutateAsync({ name }),
    publishBranch: publishBranchMutation.mutateAsync,
    onSuccess: command => toast({
      title: t({
        switch: 'shared.versionControl.branch.switchSuccess',
        create: 'shared.versionControl.branch.createSuccess',
        rename: 'shared.versionControl.branch.rename.success',
        delete: 'shared.versionControl.branch.delete.success',
        publish: 'shared.versionControl.branch.publish.success',
      }[command]),
      variant: 'success',
    }),
  });
  const runRepositoryOperation = useCallback(async (operation: () => Promise<unknown>) => {
    try {
      await operation();
    } catch (err) {
      toast({
        title: t('marketplace.settings.versionControl.toasts.operationFailed.title'),
        description: t(
          getVersionControlErrorMessageKey(err)
            ?? 'marketplace.settings.versionControl.toasts.operationFailed.description',
        ),
        variant: 'destructive',
      });
    }
  }, [t, toast]);

  const handleSaveRemoteUrl = async (remoteUrl: string) => {
    await runRepositoryOperation(() => setRemoteUrlMutation.mutateAsync(remoteUrl));
  };
  const handleRepositorySetupComplete = useCallback(async (_kind: RepositorySetupMutationKind) => {
    const refreshedRepository = await repositoryQuery.refetch();
    if (refreshedRepository.data) onRepositoryChange(refreshedRepository.data);
  }, [onRepositoryChange, repositoryQuery]);

  const handleRefresh = useCallback(async () => {
    if (isRefreshing) {
      return;
    }
    setIsRefreshing(true);
    try {
      await vc.refresh(queryClient, ['changes', 'history', 'remote']);
    } catch (refreshError) {
      toast({
        title: t('marketplace.settings.versionControl.toasts.operationFailed.title'),
        description: t(
          getVersionControlErrorMessageKey(refreshError)
            ?? 'marketplace.settings.versionControl.toasts.operationFailed.description',
        ),
        variant: 'destructive',
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [isRefreshing, queryClient, t, toast, vc]);

  const actionItems = createVersionControlActionItems({
    refresh: { onClick: () => { void handleRefresh(); } },
    remoteSettings: { onClick: () => {
      setOperationError(null);
      dialogs.setRemoteSettingsOpen(true);
    }, disabled: !registryMutationAllowed },
    lfs: { onClick: lfs.open, disabled: !registryMutationAllowed || lfs.isPending },
    fetch: { onClick: () => void runMutation(fetchMutation.mutateAsync(undefined)), disabled: !registryMutationAllowed },
    pull: { onClick: () => void runMutation(pullMutation.mutateAsync(undefined)), disabled: !registryMutationAllowed },
    push: {
      onClick: () => {
        if (!statusQuery.data?.upstream) {
          dialogs.setPublishBranchOpen(true);
          return;
        }
        void runMutation(pushMutation.mutateAsync(undefined));
      },
      disabled: !registryMutationAllowed,
    },
  });
  const changesSidebar = (
    <VersionControlChangesSidebar
      branches={branches}
      currentBranch={currentBranch}
      actions={actionItems}
      stagedFiles={stagedFiles}
      unstagedFiles={unstagedFiles}
      stagedCount={changes.staged.total}
      unstagedCount={changes.unstaged.total + changes.untracked.total}
      conflictFiles={conflictFiles}
      selectedStagedPath={selection.selectedGroup === 'staged' ? selection.selectedFile?.path : null}
      selectedUnstagedPath={selection.selectedGroup === 'unstaged' ? selection.selectedFile?.path : null}
      selectedStagedPaths={selection.selectedStagedPaths}
      selectedUnstagedPaths={selection.selectedUnstagedPaths}
      pendingStagedPaths={pending.stagedPaths}
      pendingUnstagedPaths={pending.unstagedPaths}
      isMutating={mutation.isMutating || isOperationActive}
      isCommitting={mutation.activeMutation === 'commit'}
      isStageAllPending={mutation.activeMutation === 'stageAll'}
      isUnstageAllPending={mutation.activeMutation === 'unstageAll'}
      mutationDisabled={!registryMutationAllowed}
      operationStatus={operationStatusQuery.data ?? null}
      onForceUnlock={registryMutationAllowed ? handleForceUnlock : undefined}
      onBranchChange={handleSwitchBranch}
      onCreateBranch={() => dialogs.setCreateBranchOpen(true)}
      onRenameBranch={dialogs.setRenameBranch}
      onDeleteBranch={dialogs.setDeleteBranch}
      onCreateTrackingBranch={dialogs.setTrackingBranch}
      onCommit={handleCommit}
      onFileSelect={(file, group, event) => selection.selectFile(file, group as VersionControlFileGroup, event)}
      onStageToggle={(file, group) => handleStageToggle(file, group)}
      onMarkResolved={handleMarkResolved}
      onAbortConflict={() => dialogs.setAbortConflictOpen(true)}
      onDiscard={handleDiscard}
      onStageAll={handleStageAll}
      onUnstageAll={handleUnstageAll}
    />
  );
  const historySidebar = (
    <VersionControlHistorySidebar
      commits={commits}
      files={commitFiles}
      selectedCommitId={selection.selectedCommitId}
      selectedFile={selection.selectedCommitFile}
      onCommitSelect={selection.selectCommit}
      onFileSelect={selection.setSelectedCommitFile}
      mutationDisabled={!registryMutationAllowed || revertCommitMutation.isPending}
      onRevertCommit={dialogs.setRevertCommit}
    />
  );

  if (repositoryQuery.isLoading && !currentRepository) {
    const loadingSurface = (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t('marketplace.settings.versionControl.loading')}
      </div>
    );
    return renderSurface
      ? renderSurface({ kind: 'state', content: loadingSurface })
      : loadingSurface;
  }

  if (!currentRepository?.isGitRepo) {
    const setupSurface = (
      <VersionControlRepositorySetup
        target={{
          scopeKey: 'marketplace-registry',
          repository: currentRepository ?? null,
        }}
        capability={{ canMutate: registryMutationAllowed }}
        remoteEffects={{
          initialize: defaultBranch => initializeRepositoryMutation.mutateAsync({ defaultBranch }),
          clone: (remoteUrl, branch) => cloneRepositoryMutation.mutateAsync({
            remoteUrl,
            ...(branch ? { branch } : {}),
          }),
          discoverBranches: remoteBranchesMutation.mutateAsync,
        }}
        onSetupComplete={handleRepositorySetupComplete}
      />
    );
    return renderSurface
      ? renderSurface({ kind: 'state', content: setupSurface })
      : setupSurface;
  }

  const statusSlot = operationError ? (
    <Alert variant="destructive" className="m-2 p-2">
      <AlertDescription className="text-xs">
        {t(`marketplace.settings.versionControl.errors.${operationError}`)}
      </AlertDescription>
    </Alert>
  ) : null;
  const sidebar = mode === 'changes'
    ? (vc.changes.isFirstLoad(changesQuery) ? <VersionControlChangesSkeleton /> : changesSidebar)
    : historySidebar;
  const main = (
    <VersionControlMainDiff
      selectedPath={selectedDiffFile?.path ?? null}
      diffContent={diffContent}
      emptyKey={mode === 'changes'
        ? 'shared.versionControl.main.selectFile'
        : 'shared.versionControl.main.selectCommitFile'}
    />
  );
  const navigatorContent = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden">{sidebar}</div>
      {statusSlot ? (
        <div className="shrink-0 border-t border-border">{statusSlot}</div>
      ) : null}
    </div>
  );
  const dialogHost = (
      <VersionControlDialogHost
        controller={controller}
        activeBranch={currentBranch}
        repository={currentRepository ?? null}
        canManageRemote
        onSaveRemoteUrl={handleSaveRemoteUrl}
        isSavingRemoteUrl={setRemoteUrlMutation.isPending}
        onCreateBranch={handleCreateBranch}
        isCreatingBranch={createBranchMutation.isPending}
        onRenameBranch={handleRenameBranch}
        onDeleteBranch={handleDeleteBranch}
        onPublishBranch={handlePublishBranch}
        onDiscard={confirmDiscard}
        onAbortConflict={() => abortConflictMutation.mutateAsync()}
        onRevertCommit={(sha) => revertCommitMutation.mutateAsync(sha)}
        lfs={lfs.dialog}
      />
  );

  if (renderSurface) {
    return renderSurface({
      kind: 'regions',
      navigator: navigatorContent,
      navigatorActions: (
        <VersionControlRefreshButton
          onRefresh={() => { void handleRefresh(); }}
          isRefreshing={isRefreshing}
        />
      ),
      main,
      dialogs: dialogHost,
    });
  }

  return <>{navigatorContent}{main}{dialogHost}</>;
};
