/**
 * FileChangesPanel - 檔案變更面板組件
 *
 * 功能：
 * - 顯示已暫存和未暫存的檔案變更
 * - 支援多選（Ctrl/Cmd + Click、Shift + Click）
 * - 無限滾動載入 untracked 檔案
 * - 拖拽調整面板高度
 *
 * 效能優化：
 * - 使用 useRef 避免不必要的函數重新創建
 * - React Query 自動快取和狀態管理
 * - 累加分頁數據避免數據閃爍
 */

import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileChangesPanel');
import {
  GitBranch,
  Loader2,
} from 'lucide-react';
import { useToast } from '@/shared/components/ui/use-toast';
import { GitContextSelector } from './GitContextSelector';
import { WorktreeSettingsDialog } from './WorktreeSettingsDialog';
import {
  VersionControlChangesSidebar,
  VersionControlCreateBranchDialog,
  useVersionControlFileSelection,
  type VersionControlActionMenuItem,
  type VersionControlCreateBranchPayload,
  type VersionControlFileGroup,
} from '@/shared/components/version-control';
import type { VersionControlFileChange } from '../types';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import {
  useChangesQuery,
  useBranchesQuery,
  useStatusQuery,
  useStageMutation,
  useUnstageMutation,
  useCommitMutation,
  useDiscardMutation,
  useCheckoutMutation,
  useFetchMutation,
  usePullMutation,
  usePushMutation,
} from '../hooks/useVersionControlQueries';
import { refreshVersionControlQueries, versionControlKeys } from '../lib/queryClient';
import { useQueryClient } from '@tanstack/react-query';
import { isVersionControlNotInitializedError } from '../utils';
import type { VersionControlChangesResponse } from '../types';

interface FileChangesPanelProps {
  onFileSelect?: (file: VersionControlFileChange | null) => void;
}

const DEFAULT_BRANCH = 'main';
const getErrorDescription = (error: unknown) => (
  error instanceof Error ? error.message : undefined
);

export const applyStagePathsToChangesResponse = (
  current: VersionControlChangesResponse | undefined,
  paths: string[],
): VersionControlChangesResponse | undefined => {
  if (!current || paths.length === 0) {
    return current;
  }

  const pathSet = new Set(paths);
  const movedFromUnstaged = current.unstaged.filter(file => pathSet.has(file.path));
  const movedFromUntracked = current.untracked.filter(file => pathSet.has(file.path));
  const movedFiles = [...movedFromUnstaged, ...movedFromUntracked].map(file => ({
    ...file,
    status: file.status === '?' || file.status === '??' ? 'A' : file.status,
    type: file.type === 'untracked' ? 'added' as const : file.type,
    changeType: 'staged' as const,
  }));

  if (movedFiles.length === 0) {
    return current;
  }

  const stagedByPath = new Map(current.staged.map(file => [file.path, file]));
  for (const file of movedFiles) {
    stagedByPath.set(file.path, file);
  }

  return {
    ...current,
    staged: Array.from(stagedByPath.values()),
    unstaged: current.unstaged.filter(file => !pathSet.has(file.path)),
    untracked: current.untracked.filter(file => !pathSet.has(file.path)),
    untrackedTotal: current.untrackedTotal === undefined
      ? current.untrackedTotal
      : Math.max(0, current.untrackedTotal - movedFromUntracked.length),
  };
};

/**
 * FileChangesPanel 組件
 */
export const FileChangesPanel: React.FC<FileChangesPanelProps> = ({ onFileSelect }) => {
  // ==================== State Management ====================

  // 分頁狀態
  const [untrackedPage, setUntrackedPage] = useState(1);
  const [accumulatedUntrackedFiles, setAccumulatedUntrackedFiles] = useState<VersionControlFileChange[]>([]);
  const [createBranchOpen, setCreateBranchOpen] = useState(false);
  const [worktreeSettingsOpen, setWorktreeSettingsOpen] = useState(false);

  // ==================== Refs ====================

  const unstagedLoadMoreRef = useRef<HTMLDivElement>(null);
  const previousViewIdentityRef = useRef<string | null>(null);

  // ==================== Hooks ====================

  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, state } = useWorkspace();
  const queryClient = useQueryClient();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const selectedGitContextId = state.versionControl.selectedGitContextId;

  // React Query - 查詢
  const changesQuery = useChangesQuery({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId }, untrackedPage);
  const branchesQuery = useBranchesQuery(
    { workspaceId, runtimeBaseUrl, contextId: selectedGitContextId },
    true,
    undefined,
    false,
  );
  const statusQuery = useStatusQuery({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });

  // React Query - 變更操作
  const stageMutation = useStageMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const unstageMutation = useUnstageMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const commitMutation = useCommitMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const discardMutation = useDiscardMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const checkoutMutation = useCheckoutMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const fetchMutation = useFetchMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const pullMutation = usePullMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });
  const pushMutation = usePushMutation({ workspaceId, runtimeBaseUrl, contextId: selectedGitContextId });

  // ==================== Computed Data ====================

  // 已暫存的檔案
  const stagedFiles = useMemo(() =>
    (changesQuery.data?.staged ?? []).map(f => ({ ...f, changeType: 'staged' as const })),
    [changesQuery.data?.staged]
  );

  // 未暫存的檔案
  const unstagedFiles = useMemo(() =>
    (changesQuery.data?.unstaged ?? []).map(f => ({ ...f, changeType: 'unstaged' as const })),
    [changesQuery.data?.unstaged]
  );

  // 累加 untracked 檔案（用於無限滾動）
  useEffect(() => {
    if (changesQuery.data?.untracked) {
      const newFiles = changesQuery.data.untracked.map(f => ({ ...f, changeType: 'untracked' as const }));

      if (untrackedPage === 1) {
        // 第一頁，直接設置
        setAccumulatedUntrackedFiles(newFiles);
      } else {
        // 後續頁，累加（去重）
        setAccumulatedUntrackedFiles(prev => {
          const existingPaths = new Set(prev.map(f => f.path));
          const uniqueNewFiles = newFiles.filter(f => !existingPaths.has(f.path));
          return [...prev, ...uniqueNewFiles];
        });
      }
    }
  }, [changesQuery.data?.untracked, untrackedPage]);

  const untrackedFiles = accumulatedUntrackedFiles;

  // 分支資訊
  const branches = useMemo(() => branchesQuery.data ?? [], [branchesQuery.data]);
  const currentBranch = useMemo(() => {
    const activeBranch = branches.find(b => b.isActive);
    return activeBranch?.name ?? statusQuery.data?.branch ?? DEFAULT_BRANCH;
  }, [branches, statusQuery.data]);

  // 合併 unstaged 和 untracked 檔案
  const allUnstagedFiles = useMemo(
    () => [...unstagedFiles, ...untrackedFiles],
    [unstagedFiles, untrackedFiles]
  );

  const fileSelection = useVersionControlFileSelection({
    stagedFiles,
    unstagedFiles: allUnstagedFiles,
    onFileSelect: (file) => onFileSelect?.(file),
  });

  const isMutating = commitMutation.isPending
    || stageMutation.isPending
    || unstageMutation.isPending
    || discardMutation.isPending
    || checkoutMutation.isPending
    || fetchMutation.isPending
    || pullMutation.isPending
    || pushMutation.isPending;

  // ==================== Effects ====================

  // 無限滾動 - Intersection Observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && changesQuery.data?.untrackedHasMore && !changesQuery.isFetching) {
          setUntrackedPage(prev => prev + 1);
        }
      },
      { threshold: 1.0, rootMargin: '100px' }
    );

    if (unstagedLoadMoreRef.current) {
      observer.observe(unstagedLoadMoreRef.current);
    }

    return () => observer.disconnect();
  }, [changesQuery.data?.untrackedHasMore, changesQuery.isFetching]);

  // ==================== Event Handlers ====================

  // 重置分頁狀態（在任何會改變檔案狀態的操作後調用）
  const resetPagination = useCallback(() => {
    setUntrackedPage(1);
  }, []);

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

    fileSelection.clearSelection();
    onFileSelect?.(null);
  }, [currentBranch, fileSelection.clearSelection, onFileSelect, selectedGitContextId]);

  // 分支切換
  const handleBranchChange = useCallback(async (branch: string) => {
    if (branch === currentBranch) return;

    try {
      const result = await checkoutMutation.mutateAsync({ branch, create: false, stashChanges: false });
      resetPagination();
      toast({
        title: t('workspace.versionControl.toasts.checkoutSuccess.title'),
        description: result.stashedChanges
          ? t('workspace.versionControl.toasts.checkoutSuccess.stashedDescription', { stash: result.stashedChanges })
          : t('workspace.versionControl.toasts.checkoutSuccess.description', { branch: result.branch }),
        variant: 'success',
      });
    } catch (err) {
      logger.error('Branch change error', { error: err });
      toast({
        title: t('workspace.versionControl.toasts.checkoutFailed.title'),
        description: getErrorDescription(err) ?? t('workspace.versionControl.toasts.checkoutFailed.description'),
        variant: 'destructive',
      });
    }
  }, [checkoutMutation, currentBranch, resetPagination, t, toast]);

  const handleRefresh = useCallback(async () => {
    try {
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: true,
        includeCommits: true,
        includeContexts: true,
        contextId: selectedGitContextId,
      });
      toast({ title: t('workspace.versionControl.toasts.refreshSuccess.title'), variant: 'success' });
    } catch (err) {
      logger.error('Git refresh error', { error: err });
      toast({
        title: t('workspace.versionControl.toasts.refreshFailed.title'),
        description: getErrorDescription(err) ?? t('workspace.versionControl.toasts.refreshFailed.description'),
        variant: 'destructive',
      });
    }
  }, [queryClient, selectedGitContextId, t, toast, workspaceId]);

  const applyStagePathsToCache = useCallback((paths: string[]) => {
    queryClient.setQueriesData<VersionControlChangesResponse>(
      { queryKey: versionControlKeys.changes(workspaceId, selectedGitContextId) },
      current => applyStagePathsToChangesResponse(current, paths),
    );
    const pathSet = new Set(paths);
    setAccumulatedUntrackedFiles(current => current.filter(file => !pathSet.has(file.path)));
  }, [queryClient, selectedGitContextId, workspaceId]);

  // Git 操作（Fetch/Pull/Push）
  const handleGitAction = useCallback(async (action: 'fetch' | 'pull' | 'push') => {
    try {
      if (action === 'fetch') {
        await fetchMutation.mutateAsync({ remote: 'origin' });
      } else if (action === 'pull') {
        await pullMutation.mutateAsync({ remote: 'origin', branch: currentBranch, rebase: true, autostash: true });
      } else {
        await pushMutation.mutateAsync({ remote: 'origin', branch: currentBranch, force: false });
      }
      resetPagination();
      toast({ title: t(`workspace.versionControl.toasts.${action}Success.title`), variant: 'success' });
    } catch (err) {
      logger.error(`Git ${action} error`, { error: err });
      toast({
        title: t(`workspace.versionControl.toasts.${action}Failed.title`),
        description: getErrorDescription(err) ?? t(`workspace.versionControl.toasts.${action}Failed.description`),
        variant: 'destructive',
      });
    }
  }, [currentBranch, fetchMutation, pullMutation, pushMutation, resetPagination, t, toast]);

  const handleCreateBranch = useCallback(async ({
    branch,
    startPoint,
    stashChanges,
  }: VersionControlCreateBranchPayload) => {
    if (!branch) return;

    try {
      const result = await checkoutMutation.mutateAsync({
        branch,
        create: true,
        startPoint: startPoint ?? null,
        stashChanges: stashChanges ?? false,
      });
      resetPagination();
      setCreateBranchOpen(false);
      toast({
        title: t('workspace.versionControl.toasts.createBranchSuccess.title'),
        description: result.stashedChanges
          ? t('workspace.versionControl.toasts.createBranchSuccess.stashedDescription', { branch: result.branch, stash: result.stashedChanges })
          : t('workspace.versionControl.toasts.createBranchSuccess.description', { branch: result.branch }),
        variant: 'success',
      });
    } catch (err) {
      logger.error('Create branch error', { error: err });
      toast({
        title: t('workspace.versionControl.toasts.createBranchFailed.title'),
        description: getErrorDescription(err) ?? t('workspace.versionControl.toasts.createBranchFailed.description'),
        variant: 'destructive',
      });
    }
  }, [checkoutMutation, resetPagination, t, toast]);

  // 處理檔案選擇（支援多選）
  const handleFileSelect = useCallback((
    file: VersionControlFileChange,
    type: VersionControlFileGroup,
    event?: React.MouseEvent
  ) => {
    fileSelection.selectFile(file, type, event);
  }, [fileSelection]);

  // 暫存/取消暫存
  const handleStageToggle = useCallback(async (file: VersionControlFileChange, type: VersionControlFileGroup) => {
    const pathsToProcess = fileSelection.getActionPaths(file, type);

    try {
      if (type === 'staged') {
        await unstageMutation.mutateAsync(pathsToProcess);
        fileSelection.clearSelection('staged');
      } else {
        await stageMutation.mutateAsync(pathsToProcess);
        applyStagePathsToCache(pathsToProcess);
        fileSelection.clearSelection('unstaged');
      }
      resetPagination();
    } catch (error) {
      logger.error('Stage/unstage failed', { error });
      toast({
        title: t(type === 'staged'
          ? 'workspace.versionControl.toasts.unstageFailed.title'
          : 'workspace.versionControl.toasts.stageFailed.title'),
        description: getErrorDescription(error) ?? t(type === 'staged'
          ? 'workspace.versionControl.toasts.unstageFailed.description'
          : 'workspace.versionControl.toasts.stageFailed.description'),
        variant: 'destructive',
      });
    }
  }, [applyStagePathsToCache, fileSelection, stageMutation, unstageMutation, resetPagination, t, toast]);

  // 暫存所有
  const handleStageAll = useCallback(async () => {
    const pathsToStage = allUnstagedFiles.map(f => f.path);
    if (pathsToStage.length === 0) return;

    try {
      fileSelection.selectAll('unstaged', allUnstagedFiles);
      await stageMutation.mutateAsync(pathsToStage);
      applyStagePathsToCache(pathsToStage);
      fileSelection.clearSelection('unstaged');
      resetPagination();
    } catch (error) {
      logger.error('Stage all failed', { error });
      toast({
        title: t('workspace.versionControl.toasts.stageFailed.title'),
        description: getErrorDescription(error) ?? t('workspace.versionControl.toasts.stageFailed.description'),
        variant: 'destructive',
      });
    }
  }, [allUnstagedFiles, applyStagePathsToCache, fileSelection, stageMutation, resetPagination, t, toast]);

  // 取消暫存所有
  const handleUnstageAll = useCallback(async () => {
    if (stagedFiles.length === 0) return;
    const pathsToUnstage = stagedFiles.map(f => f.path);

    try {
      fileSelection.selectAll('staged', stagedFiles);
      await unstageMutation.mutateAsync(pathsToUnstage);
      fileSelection.clearSelection('staged');
      resetPagination();
    } catch (error) {
      logger.error('Unstage all failed', { error });
      toast({
        title: t('workspace.versionControl.toasts.unstageFailed.title'),
        description: getErrorDescription(error) ?? t('workspace.versionControl.toasts.unstageFailed.description'),
        variant: 'destructive',
      });
    }
  }, [fileSelection, resetPagination, stagedFiles, t, toast, unstageMutation]);

  // 捨棄變更
  const handleDiscard = useCallback(async (file: VersionControlFileChange) => {
    const pathsToDiscard = fileSelection.getActionPaths(file, 'unstaged');

    try {
      await discardMutation.mutateAsync(pathsToDiscard);
      fileSelection.clearSelection('unstaged');
      onFileSelect?.(null);
      resetPagination();
    } catch (error) {
      logger.error('Discard failed', { error });
      toast({
        title: t('workspace.versionControl.toasts.discardFailed.title'),
        description: getErrorDescription(error) ?? t('workspace.versionControl.toasts.discardFailed.description'),
        variant: 'destructive',
      });
    }
  }, [discardMutation, fileSelection, onFileSelect, resetPagination, t, toast]);

  // 提交變更
  const handleCommit = useCallback(async (data: { message: string }) => {
    try {
      await commitMutation.mutateAsync(data.message);
      fileSelection.clearSelection();
      onFileSelect?.(null);
      resetPagination();
      toast({ title: t('workspace.versionControl.toasts.commitSuccess.title'), variant: 'success' });
    } catch (error) {
      logger.error('Commit failed', { error });
      toast({
        title: t('workspace.versionControl.toasts.commitFailed.title'),
        description: getErrorDescription(error) ?? t('workspace.versionControl.toasts.commitFailed.description'),
        variant: 'destructive',
      });
    }
  }, [commitMutation, fileSelection, onFileSelect, resetPagination, t, toast]);

  // ==================== Early Returns ====================

  // Loading 狀態
  if (changesQuery.isLoading || branchesQuery.isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error 狀態
  if (changesQuery.error || branchesQuery.error) {
    const error = changesQuery.error ?? branchesQuery.error;
    const isNotInitialized = isVersionControlNotInitializedError(error);

    if (isNotInitialized) {
      return (
        <div className="h-full flex items-center justify-center p-4">
          <div className="text-center max-w-sm">
            <GitBranch className="h-10 w-10 mx-auto mb-3 text-muted-foreground opacity-60" />
            <p className="text-sm font-medium text-foreground mb-1">
              {t('workspace.versionControl.errors.notInitialized.title')}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('workspace.versionControl.errors.notInitialized.description')}
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-destructive">
          {getErrorDescription(error) || t('workspace.versionControl.errors.loadFailed')}
        </div>
      </div>
    );
  }

  // ==================== Main Render ====================

  const actionItems: VersionControlActionMenuItem[] = [
    { id: 'refresh', onClick: () => void handleRefresh() },
    {
      id: 'worktreeSettings',
      labelKey: 'workspace.versionControl.worktree.menu.settings',
      onClick: () => setWorktreeSettingsOpen(true),
    },
    { id: 'fetch', onClick: () => void handleGitAction('fetch') },
    { id: 'pull', onClick: () => void handleGitAction('pull') },
    { id: 'push', onClick: () => void handleGitAction('push') },
  ];

  return (
    <>
      <VersionControlChangesSidebar
        contextSlot={<GitContextSelector />}
        branches={branches}
        currentBranch={currentBranch}
        actions={actionItems}
        stagedFiles={stagedFiles}
        unstagedFiles={allUnstagedFiles}
        selectedStagedPath={fileSelection.selectedStagedPath}
        selectedUnstagedPath={fileSelection.selectedUnstagedPath}
        selectedStagedPaths={fileSelection.selectedStagedPaths}
        selectedUnstagedPaths={fileSelection.selectedUnstagedPaths}
        isMutating={isMutating}
        onBranchChange={handleBranchChange}
        onCreateBranch={() => setCreateBranchOpen(true)}
        onCommit={handleCommit}
        onFileSelect={handleFileSelect}
        onStageToggle={handleStageToggle}
        onDiscard={handleDiscard}
        onStageAll={handleStageAll}
        onUnstageAll={handleUnstageAll}
        unstagedFooter={(
          <>
            {changesQuery.data?.untrackedHasMore && (
              <div ref={unstagedLoadMoreRef} className="h-1" />
            )}
            {changesQuery.isFetching && (
              <div className="text-center py-2 text-muted-foreground text-sm">
                <Loader2 className="inline-block w-4 h-4 animate-spin mr-2" />
                {t('shared.versionControl.fileChanges.loadingMore')}
              </div>
            )}
          </>
        )}
      />
      <VersionControlCreateBranchDialog
        open={createBranchOpen}
        onOpenChange={setCreateBranchOpen}
        onCreate={handleCreateBranch}
        isCreating={checkoutMutation.isPending}
        supportsStartPoint
        supportsStashBeforeCheckout
      />
      <WorktreeSettingsDialog
        open={worktreeSettingsOpen}
        workspaceId={workspaceId}
        onOpenChange={setWorktreeSettingsOpen}
        onSaved={workspaceRuntime.reload}
      />
    </>
  );
};
