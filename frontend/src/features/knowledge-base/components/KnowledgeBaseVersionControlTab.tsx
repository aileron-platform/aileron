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
} from '@/shared/components/version-control';
import {
  getVersionControlErrorMessageKey,
  isVersionControlOperationInProgressError,
  useKnowledgeBaseVersionControlSession,
  type RepositorySetupMutationKind,
  type VersionControlBranch,
  type VersionControlCommitSummary,
  type VersionControlFileChange,
  type VersionControlRepositoryStatus,
} from '@/shared/version-control';
import { useI18n } from '@/shared/hooks/useI18n';
import type { OperationId } from '@/shared/authorization/operationIds';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import { resolveKnowledgeBasePermissions } from '@/features/knowledge-base/model/knowledgeBasePermissions';
import {
  KnowledgeBaseVersionControlPresentation,
  type KnowledgeBaseVersionControlRegions,
} from './KnowledgeBaseVersionControlPresentation';

type VersionControlMode = 'changes' | 'history';

interface KnowledgeBaseVersionControlTabProps {
  knowledgeBaseId: string;
  accessRole: ResourceAccessRole;
  allowedOperations: OperationId[];
  mode: VersionControlMode;
  versionControlEnabled?: boolean;
  renderRegions?: (regions: KnowledgeBaseVersionControlRegions) => React.ReactNode;
}

const VERSION_CONTROL_OPERATION_LOCKED_CODE = 'operation_locked';

const blobToContextPatch = (path: string, content: string): string => {
  const lines = content.split('\n');
  const lineCount = Math.max(lines.length, 1);
  return [
    `@@ -1,${lineCount} +1,${lineCount} @@ ${path}`,
    ...lines.map((line) => ` ${line}`),
  ].join('\n');
};

export const KnowledgeBaseVersionControlTab: React.FC<KnowledgeBaseVersionControlTabProps> = ({
  knowledgeBaseId,
  accessRole,
  allowedOperations,
  mode,
  versionControlEnabled = false,
  renderRegions,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const permissions = resolveKnowledgeBasePermissions(
    accessRole,
    allowedOperations,
  );
  const [repositoryStatus, setRepositoryStatus] = useState<VersionControlRepositoryStatus | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const queryClient = useQueryClient();
  const vc = useKnowledgeBaseVersionControlSession({
    knowledgeBaseId,
    isGitRepo: versionControlEnabled || !!repositoryStatus?.isGitRepo,
  });
  const repositoryQuery = vc.remote.useRepositoryQuery(permissions.canWrite);
  const {
    changesQuery,
    statusQuery,
    operationStatusQuery,
    branchesQuery,
    commitsQuery,
  } = useVersionControlProductQueryBindings(vc.changes, vc.history, { commitsLimit: 20 });
  const {
    stageMutation,
    unstageMutation,
    discardMutation,
    markResolvedMutation,
    abortConflictMutation,
    commitMutation,
    forceUnlockMutation,
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
  const initializeRepositoryMutation =
    vc.remote.useInitializeRepositoryMutation();
  const cloneRepositoryMutation = vc.remote.useCloneRepositoryMutation();
  const remoteBranchesMutation = vc.remote.useRemoteBranchesMutation();

  useEffect(() => {
    if (!permissions.canWrite) {
      setRepositoryStatus(null);
      queryClient.removeQueries({
        predicate: query => (
          query.queryKey[0] === 'version-control'
          && query.queryKey[1] === 'knowledge-bases'
          && query.queryKey[2] === knowledgeBaseId
          && query.queryKey[4] === 'remote'
          && query.queryKey[5] === 'repository'
        ),
      });
    }
  }, [knowledgeBaseId, permissions.canManage, permissions.canWrite, queryClient]);

  const branches: VersionControlBranch[] = useMemo(
    () => branchesQuery.data ?? [],
    [branchesQuery.data],
  );
  const commits: VersionControlCommitSummary[] = useMemo(
    () => commitsQuery.data?.items ?? [],
    [commitsQuery.data?.items],
  );

  const isOperationActive = operationStatusQuery.data?.isActive === true;
  const {
    changes,
    stagedFiles,
    unstagedFiles: allUnstagedFiles,
    conflictFiles,
    numstatParams,
    currentBranch: activeBranch,
    changeCount,
    controller,
  } = useVersionControlWorkbenchModel({
    mode,
    changes: changesQuery.data,
    status: statusQuery.data,
    branches,
    repository: repositoryStatus,
    commits,
  });
  vc.changes.useChangesNumstatQuery(numstatParams);
  const { dialogs, mutation, pending, selection } = controller;
  const lfs = useVersionControlLfsDialogBinding({
    remote: vc.remote,
    controller,
    requestIdentity: `knowledge-base:${knowledgeBaseId}`,
    operationStatus: statusQuery.data?.operationStatus,
  });
  useEffect(() => {
    if (!permissions.canManage) {
      dialogs.setRemoteSettingsOpen(false);
    }
  }, [dialogs.setRemoteSettingsOpen, permissions.canManage]);
  const commitFilesQuery = vc.history.useCommitFilesQuery(selection.selectedCommitId);
  const commitFiles: VersionControlFileChange[] = useMemo(
    () => commitFilesQuery.data ?? [],
    [commitFilesQuery.data],
  );
  const selectedDiffFile = selection.selectedDiffFile;

  useEffect(() => {
    if (permissions.canWrite && repositoryQuery.data) {
      setRepositoryStatus(repositoryQuery.data);
    }
  }, [permissions.canWrite, repositoryQuery.data]);

  useEffect(() => {
    if (permissions.canWrite && repositoryQuery.error) {
      const messageKey = getVersionControlErrorMessageKey(repositoryQuery.error);
      const message = messageKey
        ? t(messageKey)
        : t('knowledgeBase.versionControl.loadFailed');
      toast({
        title: t('knowledgeBase.versionControl.toasts.loadFailed.title'),
        description: message,
        variant: 'destructive',
      });
    }
  }, [permissions.canWrite, repositoryQuery.error, t, toast]);

  const inlineHistoryDiff = selection.selectedCommitFile?.patch || selection.selectedCommitFile?.diff || '';
  const workingDiffQuery = vc.changes.useDiffQuery({
    path: mode === 'changes' ? selection.selectedFile?.path ?? null : null,
    head: selection.selectedGroup === 'staged' ? 'INDEX' : 'WORKTREE',
  });
  const commitBlobQuery = vc.history.useCommitBlobQuery({
    path: mode === 'history' && !inlineHistoryDiff
      ? selection.selectedCommitFile?.path ?? null
      : null,
    revision: selection.selectedCommitId,
  });
  const diffContent = mode === 'history'
    ? inlineHistoryDiff || (
      commitBlobQuery.data
        ? blobToContextPatch(commitBlobQuery.data.path, commitBlobQuery.data.content)
        : ''
    )
    : workingDiffQuery.data?.patch || workingDiffQuery.data?.diff || '';
  const activeDiffQuery = mode === 'history' ? commitBlobQuery : workingDiffQuery;
  const diffErrorKey = getVersionControlErrorMessageKey(activeDiffQuery.error);
  const diffError = diffErrorKey
    ? t(diffErrorKey)
    : activeDiffQuery.error
      ? t('shared.versionControl.diff.loadFailed')
      : null;
  const isDiffLoading = !inlineHistoryDiff && activeDiffQuery.isLoading;

  const runMutation = useCallback(async (
    mutationPromise: Promise<unknown>,
    options?: {
      successKey?: string;
      onSuccess?: () => void;
      kind?: 'commit' | 'stageAll' | 'unstageAll' | 'other';
    },
  ) => {
    await mutation.run(mutationPromise, {
      kind: options?.kind,
      clearSelectionOnSuccess: false,
      onSuccess: async () => {
        if (options?.successKey) {
          toast({ title: t(options.successKey), variant: 'success' });
        }
        options?.onSuccess?.();
      },
      onError: (mutationError) => {
        if (isVersionControlOperationInProgressError(mutationError, VERSION_CONTROL_OPERATION_LOCKED_CODE)) {
          toast({
            title: t('knowledgeBase.versionControl.toasts.operationInProgress.title'),
            description: t('knowledgeBase.versionControl.toasts.operationInProgress.description'),
            variant: 'destructive',
          });
          return;
        }
        toast({
          title: t('knowledgeBase.versionControl.toasts.operationFailed.title'),
          description: t(
            getVersionControlErrorMessageKey(mutationError)
              ?? 'knowledgeBase.versionControl.toasts.operationFailed.description',
          ),
          variant: 'destructive',
        });
      },
    });
  }, [mutation, t, toast]);

  const handleRepositorySetupComplete = useCallback(async (kind: RepositorySetupMutationKind) => {
    try {
      const refreshedRepository = await repositoryQuery.refetch();
      if (refreshedRepository.data) setRepositoryStatus(refreshedRepository.data);
      toast({
        title: t(kind === 'initialize'
          ? 'knowledgeBase.versionControl.toasts.initializeSuccess.title'
          : 'knowledgeBase.versionControl.toasts.cloneSuccess.title'),
        variant: 'success',
      });
    } catch (error) {
      toast({
        title: t('knowledgeBase.versionControl.toasts.loadFailed.title'),
        description: t(
          getVersionControlErrorMessageKey(error)
            ?? 'knowledgeBase.versionControl.loadFailed',
        ),
        variant: 'destructive',
      });
    }
  }, [getVersionControlErrorMessageKey, repositoryQuery, t, toast]);

  const handleFileSelect = (file: VersionControlFileChange, group: VersionControlFileGroup, event?: React.MouseEvent) => {
    selection.selectFile(file, group, event);
  };

  const {
    handleStageToggle,
    handleStageAll,
    handleUnstageAll,
    handleDiscard,
    handleMarkResolved,
    confirmDiscard,
  } = useVersionControlChangeCommands({
    controller,
    canMutate: permissions.canWrite,
    runMutation,
    stage: stageMutation.mutateAsync,
    unstage: unstageMutation.mutateAsync,
    discard: discardMutation.mutateAsync,
    markResolved: markResolvedMutation.mutateAsync,
  });

  const handleCommit = ({ message }: { message: string }) => {
    if (!permissions.canWrite) {
      return;
    }
    void runMutation(commitMutation.mutateAsync(message), {
      kind: 'commit',
      successKey: 'knowledgeBase.versionControl.toasts.commitSuccess.title',
      onSuccess: selection.clearChangeSelection,
    });
  };

  const handleRemoteAction = (action: 'fetch' | 'pull' | 'push') => {
    if (!permissions.canWrite) {
      return;
    }
    if (action === 'push' && !status?.upstream) {
      dialogs.setPublishBranchOpen(true);
      return;
    }
    const payload = { branch: activeBranch || undefined };
    void runMutation(
      action === 'fetch'
        ? fetchMutation.mutateAsync({})
        : action === 'pull'
          ? pullMutation.mutateAsync(payload)
          : pushMutation.mutateAsync(payload),
      { successKey: `knowledgeBase.versionControl.toasts.${action}Success.title` },
    );
  };

  const {
    handleSwitchBranch,
    handleCreateBranch,
    handleRenameBranch,
    handleDeleteBranch,
    handlePublishBranch,
  } = useVersionControlBranchCommands({
    controller,
    canMutate: permissions.canWrite,
    currentBranch: activeBranch,
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

  const handleSetRemoteUrl = (remoteUrl: string) => {
    if (!permissions.canManage) {
      return;
    }
    const nextUrl = remoteUrl.trim();
    if (!nextUrl) {
      return;
    }
    void runMutation(setRemoteUrlMutation.mutateAsync(nextUrl), {
      successKey: 'knowledgeBase.versionControl.toasts.remoteUrlSuccess.title',
    });
  };

  const handleForceUnlock = async () => {
    await forceUnlockMutation.mutateAsync();
    toast({ title: t('shared.versionControl.conflict.forceUnlockSuccess.title'), variant: 'success' });
  };

  const handleRefresh = useCallback(async () => {
    if (isRefreshing) {
      return;
    }
    setIsRefreshing(true);
    try {
      await runMutation(
        vc.refresh(
          queryClient,
          permissions.canManage
            ? ['changes', 'history', 'remote']
            : ['changes', 'history'],
        ),
      );
    } finally {
      setIsRefreshing(false);
    }
  }, [isRefreshing, permissions.canManage, queryClient, runMutation, vc]);

  const isGitRepo = versionControlEnabled || repositoryStatus?.isGitRepo === true;
  const renderUninitializedSurface = (navigator: React.ReactNode) => (
    <KnowledgeBaseVersionControlPresentation
      mode={mode}
      count={0}
      sidebar={navigator}
      main={(
        <VersionControlMainDiff
          selectedPath={null}
          emptyKey={mode === 'changes'
            ? 'shared.versionControl.main.selectFile'
            : 'shared.versionControl.main.selectCommitFile'}
        />
      )}
      renderRegions={renderRegions}
    />
  );

  if (permissions.canWrite && repositoryQuery.isLoading && !isGitRepo) {
    return renderUninitializedSurface(
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {t('knowledgeBase.versionControl.loading')}
      </div>
    );
  }

  if (!isGitRepo) {
    return renderUninitializedSurface(
      <VersionControlRepositorySetup
        target={{
          scopeKey: knowledgeBaseId ? `knowledge-base:${knowledgeBaseId}` : '',
          repository: repositoryStatus,
        }}
        capability={{ canMutate: permissions.canManageSettings }}
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
  }

  const actionItems = createVersionControlActionItems({
    refresh: {
      onClick: () => { void handleRefresh(); },
    },
    fetch: {
      onClick: () => handleRemoteAction('fetch'),
      disabled: !permissions.canWrite || (permissions.canManage && !repositoryStatus?.hasOrigin),
    },
    pull: {
      onClick: () => handleRemoteAction('pull'),
      disabled: !permissions.canWrite || (permissions.canManage && !repositoryStatus?.hasOrigin),
    },
    push: {
      onClick: () => handleRemoteAction('push'),
      disabled: !permissions.canWrite || (permissions.canManage && !repositoryStatus?.hasOrigin),
    },
    ...(permissions.canManage ? {
      remoteSettings: { onClick: () => dialogs.setRemoteSettingsOpen(true) },
      lfs: {
        onClick: lfs.open,
        disabled: lfs.isPending,
      },
    } : {}),
  });

  const changesSidebar = (
    <VersionControlChangesSidebar
      branches={branches}
      currentBranch={activeBranch}
      actions={actionItems}
      stagedFiles={stagedFiles}
      unstagedFiles={allUnstagedFiles}
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
      mutationDisabled={!permissions.canWrite}
      operationStatus={operationStatusQuery.data ?? null}
      onForceUnlock={permissions.canManage ? handleForceUnlock : undefined}
      onBranchChange={handleSwitchBranch}
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
      mutationDisabled={!permissions.canWrite || revertCommitMutation.isPending}
      onRevertCommit={dialogs.setRevertCommit}
    />
  );

  const secondColumnCount = mode === 'changes' ? changeCount : commits.length;

  return (
    <>
      <KnowledgeBaseVersionControlPresentation
        mode={mode}
        count={secondColumnCount}
        sidebar={mode === 'changes'
            ? (vc.changes.isFirstLoad(changesQuery) ? <VersionControlChangesSkeleton /> : changesSidebar)
            : historySidebar}
        navigatorActions={(
          <VersionControlRefreshButton
            onRefresh={() => { void handleRefresh(); }}
            isRefreshing={isRefreshing}
          />
        )}
        main={(
          <VersionControlMainDiff
            selectedPath={selectedDiffFile?.path ?? null}
            diffContent={diffContent}
            isLoading={isDiffLoading}
            error={diffError}
            emptyKey={mode === 'changes'
              ? 'shared.versionControl.main.selectFile'
              : 'shared.versionControl.main.selectCommitFile'}
          />
        )}
        renderRegions={renderRegions}
      />
      <VersionControlDialogHost
        controller={controller}
        activeBranch={activeBranch}
        repository={{
          currentBranch: activeBranch || repositoryStatus?.currentBranch,
          remoteUrl: repositoryStatus?.remoteUrl ?? null,
          hasOrigin: repositoryStatus?.hasOrigin ?? false,
        }}
        canManageRemote={permissions.canManage}
        onSaveRemoteUrl={handleSetRemoteUrl}
        isSavingRemoteUrl={setRemoteUrlMutation.isPending}
        onDiscard={confirmDiscard}
        onAbortConflict={() => abortConflictMutation.mutateAsync()}
        onRevertCommit={(sha) => revertCommitMutation.mutateAsync(sha)}
        onCreateBranch={handleCreateBranch}
        isCreatingBranch={createBranchMutation.isPending}
        onRenameBranch={handleRenameBranch}
        onDeleteBranch={handleDeleteBranch}
        onPublishBranch={handlePublishBranch}
        lfs={lfs.dialog}
      />
    </>
  );
};
