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
import { ApiClient } from '@/shared/api/apiClient';
import { GitContextSelector } from './GitContextSelector';
import { VersionControlChangesSidebar, type VersionControlActionMenuItem } from '@/shared/components/version-control';
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
} from '../hooks/useVersionControlQueries';
import { refreshVersionControlQueries } from '../lib/queryClient';
import { useQueryClient } from '@tanstack/react-query';
import { isVersionControlNotInitializedError } from '../utils';

interface FileChangesPanelProps {
  onFileSelect?: (file: VersionControlFileChange | null) => void;
}

const DEFAULT_BRANCH = 'main';

/**
 * FileChangesPanel 組件
 */
export const FileChangesPanel: React.FC<FileChangesPanelProps> = ({ onFileSelect }) => {
  // ==================== State Management ====================

  // 選擇狀態
  const [selectedStagedPath, setSelectedStagedPath] = useState<string | null>(null);
  const [selectedUnstagedPath, setSelectedUnstagedPath] = useState<string | null>(null);
  const [selectedStagedPaths, setSelectedStagedPaths] = useState<Set<string>>(new Set());
  const [selectedUnstagedPaths, setSelectedUnstagedPaths] = useState<Set<string>>(new Set());
  const [lastSelectedStagedPath, setLastSelectedStagedPath] = useState<string | null>(null);
  const [lastSelectedUnstagedPath, setLastSelectedUnstagedPath] = useState<string | null>(null);

  // 分頁狀態
  const [untrackedPage, setUntrackedPage] = useState(1);
  const [accumulatedUntrackedFiles, setAccumulatedUntrackedFiles] = useState<VersionControlFileChange[]>([]);

  // ==================== Refs ====================

  const unstagedLoadMoreRef = useRef<HTMLDivElement>(null);
  const previousViewIdentityRef = useRef<string | null>(null);

  // 使用 ref 避免 callback 依賴問題
  const stagedFilesRef = useRef<VersionControlFileChange[]>([]);
  const allUnstagedFilesRef = useRef<VersionControlFileChange[]>([]);
  // ==================== Hooks ====================

  const { t } = useI18n();
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

  // ==================== Effects ====================

  // 更新 ref（避免 callback 依賴問題）
  useEffect(() => {
    stagedFilesRef.current = stagedFiles;
    allUnstagedFilesRef.current = allUnstagedFiles;
  }, [stagedFiles, allUnstagedFiles]);

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

    setSelectedStagedPath(null);
    setSelectedUnstagedPath(null);
    setSelectedStagedPaths(new Set());
    setSelectedUnstagedPaths(new Set());
    setLastSelectedStagedPath(null);
    setLastSelectedUnstagedPath(null);
    onFileSelect?.(null);
  }, [currentBranch, onFileSelect, selectedGitContextId]);

  // 分支切換
  const handleBranchChange = useCallback(async (branch: string) => {
    if (branch === currentBranch) return;

    try {
      // 使用 ApiClient 來確保請求攜帶 Authorization header
      const client = new ApiClient({ baseUrl: runtimeBaseUrl });
      const suffix = selectedGitContextId ? `?contextId=${encodeURIComponent(selectedGitContextId)}` : '';
      const path = `/api/v1/workspaces/${workspaceId}/version-control/branches/${encodeURIComponent(branch)}/checkout${suffix}`;

      await client.post(path, { create: false, stashChanges: false });
      resetPagination();
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: true,
        includeContexts: true,
        contextId: selectedGitContextId,
      });
    } catch (err) {
      logger.error('Branch change error', { error: err });
    }
  }, [currentBranch, queryClient, resetPagination, runtimeBaseUrl, selectedGitContextId, workspaceId]);

  // Git 操作（Pull/Push）
  const handleGitAction = useCallback(async (action: 'pull' | 'push') => {
    try {
      const client = new ApiClient({ baseUrl: runtimeBaseUrl });
      const suffix = selectedGitContextId ? `?contextId=${encodeURIComponent(selectedGitContextId)}` : '';
      const path = `/api/v1/workspaces/${workspaceId}/version-control/${action}${suffix}`;
      const body = action === 'pull'
        ? { remote: 'origin', branch: currentBranch, rebase: true, autostash: true }
        : { remote: 'origin', branch: currentBranch, force: false };

      await client.post(path, body);
      resetPagination();
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: true,
        includeCommits: true,
        includeContexts: true,
        contextId: selectedGitContextId,
      });
    } catch (err) {
      logger.error(`Git ${action} error`, { error: err });
    }
  }, [currentBranch, queryClient, resetPagination, runtimeBaseUrl, selectedGitContextId, workspaceId]);

  // 處理檔案選擇（支援多選）
  const handleFileSelect = useCallback((
    file: VersionControlFileChange,
    type: 'staged' | 'unstaged',
    event?: React.MouseEvent
  ) => {
    // 防止文字選取
    if (event?.shiftKey) {
      event.preventDefault();
    }

    const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    const isCtrlOrCmd = isMac ? event?.metaKey : event?.ctrlKey;
    const isShift = event?.shiftKey;

    if (type === 'staged') {
      if (isCtrlOrCmd) {
        setSelectedStagedPaths(prev => {
          const newSet = new Set(prev);
          if (newSet.has(file.path)) {
            newSet.delete(file.path);
          } else {
            newSet.add(file.path);
          }
          return newSet;
        });
        setLastSelectedStagedPath(file.path);
      } else if (isShift && lastSelectedStagedPath) {
        // 使用 ref 來避免依賴問題
        const currentStagedFiles = stagedFilesRef.current;
        const lastIndex = currentStagedFiles.findIndex(f => f.path === lastSelectedStagedPath);
        const currentIndex = currentStagedFiles.findIndex(f => f.path === file.path);

        if (lastIndex !== -1 && currentIndex !== -1) {
          const [start, end] = [Math.min(lastIndex, currentIndex), Math.max(lastIndex, currentIndex)];
          const pathsToSelect = currentStagedFiles.slice(start, end + 1).map(f => f.path);
          setSelectedStagedPaths(new Set(pathsToSelect));
        }
      } else {
        setSelectedStagedPaths(new Set([file.path]));
        setLastSelectedStagedPath(file.path);
      }
      setSelectedStagedPath(file.path);
      setSelectedUnstagedPath(null);
      setSelectedUnstagedPaths(new Set());
    } else {
      // 類似邏輯處理 unstaged
      if (isCtrlOrCmd) {
        setSelectedUnstagedPaths(prev => {
          const newSet = new Set(prev);
          if (newSet.has(file.path)) {
            newSet.delete(file.path);
          } else {
            newSet.add(file.path);
          }
          return newSet;
        });
        setLastSelectedUnstagedPath(file.path);
      } else if (isShift && lastSelectedUnstagedPath) {
        // 使用 ref 來避免依賴問題
        const currentUnstagedFiles = allUnstagedFilesRef.current;
        const lastIndex = currentUnstagedFiles.findIndex(f => f.path === lastSelectedUnstagedPath);
        const currentIndex = currentUnstagedFiles.findIndex(f => f.path === file.path);

        if (lastIndex !== -1 && currentIndex !== -1) {
          const [start, end] = [Math.min(lastIndex, currentIndex), Math.max(lastIndex, currentIndex)];
          const pathsToSelect = currentUnstagedFiles.slice(start, end + 1).map(f => f.path);
          setSelectedUnstagedPaths(new Set(pathsToSelect));
        }
      } else {
        setSelectedUnstagedPaths(new Set([file.path]));
        setLastSelectedUnstagedPath(file.path);
      }
      setSelectedUnstagedPath(file.path);
      setSelectedStagedPath(null);
      setSelectedStagedPaths(new Set());
    }
    onFileSelect?.(file);
  }, [lastSelectedStagedPath, lastSelectedUnstagedPath, onFileSelect]);

  // 暫存/取消暫存
  const handleStageToggle = useCallback(async (file: VersionControlFileChange, type: 'staged' | 'unstaged') => {
    const selectedPaths = type === 'staged' ? selectedStagedPaths : selectedUnstagedPaths;
    const pathsToProcess = selectedPaths.has(file.path) && selectedPaths.size > 1
      ? Array.from(selectedPaths)
      : [file.path];

    try {
      if (type === 'staged') {
        await unstageMutation.mutateAsync(pathsToProcess);
        setSelectedStagedPaths(new Set());
      } else {
        await stageMutation.mutateAsync(pathsToProcess);
        setSelectedUnstagedPaths(new Set());
      }
      resetPagination();
    } catch (error) {
      logger.error('Stage/unstage failed', { error });
    }
  }, [selectedStagedPaths, selectedUnstagedPaths, stageMutation, unstageMutation, resetPagination]);

  // 暫存所有
  const handleStageAll = useCallback(async () => {
    const currentUnstagedFiles = allUnstagedFilesRef.current;
    const pathsToStage = currentUnstagedFiles.map(f => f.path);
    if (pathsToStage.length === 0) return;

    try {
      setSelectedUnstagedPaths(new Set(pathsToStage));
      await stageMutation.mutateAsync(pathsToStage);
      setSelectedUnstagedPaths(new Set());
      setSelectedUnstagedPath(null);
      resetPagination();
    } catch (error) {
      logger.error('Stage all failed', { error });
    }
  }, [stageMutation, resetPagination]);

  // 取消暫存所有
  const handleUnstageAll = useCallback(async () => {
    const currentStagedFiles = stagedFilesRef.current;
    if (currentStagedFiles.length === 0) return;
    const pathsToUnstage = currentStagedFiles.map(f => f.path);

    try {
      setSelectedStagedPaths(new Set(pathsToUnstage));
      await unstageMutation.mutateAsync(pathsToUnstage);
      setSelectedStagedPaths(new Set());
      setSelectedStagedPath(null);
      resetPagination();
    } catch (error) {
      logger.error('Unstage all failed', { error });
    }
  }, [unstageMutation, resetPagination]);

  // 捨棄變更
  const handleDiscard = useCallback(async (file: VersionControlFileChange) => {
    const pathsToDiscard = selectedUnstagedPaths.has(file.path) && selectedUnstagedPaths.size > 1
      ? Array.from(selectedUnstagedPaths)
      : [file.path];

    await discardMutation.mutateAsync(pathsToDiscard);
    setSelectedUnstagedPaths(new Set());
    if (pathsToDiscard.includes(selectedUnstagedPath ?? '')) {
      onFileSelect?.(null);
      setSelectedUnstagedPath(null);
    }
    resetPagination();
  }, [selectedUnstagedPaths, selectedUnstagedPath, discardMutation, onFileSelect, resetPagination]);

  // 提交變更
  const handleCommit = useCallback(async (data: { message: string }) => {
    await commitMutation.mutateAsync(data.message);
    setSelectedStagedPath(null);
    onFileSelect?.(null);
    resetPagination();
  }, [commitMutation, onFileSelect, resetPagination]);

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
          {error?.message || t('workspace.versionControl.errors.loadFailed')}
        </div>
      </div>
    );
  }

  // ==================== Main Render ====================

  const actionItems: VersionControlActionMenuItem[] = [
    { id: 'pull', onClick: () => void handleGitAction('pull') },
    { id: 'push', onClick: () => void handleGitAction('push') },
  ];

  return (
    <VersionControlChangesSidebar
      contextSlot={<GitContextSelector />}
      branches={branches}
      currentBranch={currentBranch}
      actions={actionItems}
      stagedFiles={stagedFiles}
      unstagedFiles={allUnstagedFiles}
      selectedStagedPath={selectedStagedPath}
      selectedUnstagedPath={selectedUnstagedPath}
      selectedStagedPaths={selectedStagedPaths}
      selectedUnstagedPaths={selectedUnstagedPaths}
      isMutating={commitMutation.isPending || stageMutation.isPending || unstageMutation.isPending || discardMutation.isPending}
      onBranchChange={handleBranchChange}
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
  );
};
