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
  Minus,
  Plus,
  ChevronDown,
  MoreHorizontal,
  ArrowDown,
  ArrowUp,
  GitBranch,
  Loader2,
} from 'lucide-react';
import { ApiClient } from '@/shared/api/apiClient';
import { CommitForm } from './CommitForm';
import { FileChangeItem } from './FileChangeItem';
import { GitContextSelector } from './GitContextSelector';
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

  // UI 狀態
  const [panelHeight, setPanelHeight] = useState(50);
  const [showBranchDropdown, setShowBranchDropdown] = useState(false);
  const [showActionMenu, setShowActionMenu] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // 分頁狀態
  const [untrackedPage, setUntrackedPage] = useState(1);
  const [accumulatedUntrackedFiles, setAccumulatedUntrackedFiles] = useState<VersionControlFileChange[]>([]);

  // ==================== Refs ====================

  const containerRef = useRef<HTMLDivElement>(null);
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
    setShowBranchDropdown(false);
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
    setShowActionMenu(false);
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

  // 拖拽調整面板高度
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);

    const startY = e.clientY;
    const startHeight = panelHeight;

    const handleMouseMove = (event: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const deltaY = event.clientY - startY;
      const deltaPercent = (deltaY / containerRect.height) * 100;
      const newHeight = Math.max(20, Math.min(80, startHeight + deltaPercent));
      setPanelHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  }, [panelHeight]);

  // ==================== Render Functions ====================

  // 渲染檔案列表
  const renderFileList = useCallback((
    type: 'staged' | 'unstaged'
  ) => {
    const files = type === 'staged' ? stagedFiles : allUnstagedFiles;
    const selectedPath = type === 'staged' ? selectedStagedPath : selectedUnstagedPath;
    const selectedPaths = type === 'staged' ? selectedStagedPaths : selectedUnstagedPaths;

    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div
          className="px-3 py-2 border-b border-border bg-muted/30 flex items-center justify-between flex-shrink-0"
        >
          <h4 className="text-sm font-medium text-foreground flex items-center gap-2">
            {type === 'staged'
              ? t('workspace.versionControl.fileChanges.stagedTitle')
              : t('workspace.versionControl.fileChanges.unstagedTitle')}
            <span className="text-xs px-1.5 py-0.5 bg-muted text-muted-foreground rounded">{files.length}</span>
            {selectedPaths.size > 0 && (
              <span className="text-xs px-1.5 py-0.5 bg-primary/20 text-primary rounded">
                {selectedPaths.size} 已選
              </span>
            )}
          </h4>
          <button
            className="h-6 w-6 p-0 hover:bg-muted-foreground/10 rounded flex items-center justify-center disabled:opacity-50 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              if (type === 'staged') {
                handleUnstageAll();
              } else {
                handleStageAll();
              }
            }}
            disabled={files.length === 0}
            title={type === 'staged'
              ? t('workspace.versionControl.fileChanges.unstageAllTooltip')
              : t('workspace.versionControl.fileChanges.stageAllTooltip')}
          >
            {type === 'staged' ? <Minus className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
          </button>
        </div>

        {/* 簡單列表渲染 */}
        <div className="flex-1 overflow-y-auto p-2 min-h-0">
          {files.map((file: VersionControlFileChange) => (
            <FileChangeItem
              key={file.path}
              file={file}
              isSelected={selectedPath === file.path}
              isMultiSelected={selectedPaths.has(file.path)}
              type={type}
              onSelect={handleFileSelect}
              onStageToggle={(item) => handleStageToggle(item, type)}
              onDiscard={type === 'unstaged' ? handleDiscard : undefined}
              selectedCount={selectedPaths.size}
            />
          ))}

          {/* 無限滾動觸發器（僅用於 unstaged）*/}
          {type === 'unstaged' && changesQuery.data?.untrackedHasMore && (
            <div ref={unstagedLoadMoreRef} className="h-1" />
          )}

          {/* 載入中指示器 */}
          {type === 'unstaged' && changesQuery.isFetching && (
            <div className="text-center py-2 text-muted-foreground text-sm">
              <Loader2 className="inline-block w-4 h-4 animate-spin mr-2" />
              {t('workspace.versionControl.fileChanges.loadingMore')}
            </div>
          )}
        </div>
      </div>
    );
  }, [
    stagedFiles, allUnstagedFiles,
    selectedStagedPath, selectedUnstagedPath, selectedStagedPaths, selectedUnstagedPaths,
    handleStageAll, handleUnstageAll, handleFileSelect, handleStageToggle, handleDiscard,
    changesQuery.data?.untrackedHasMore, changesQuery.isFetching, unstagedLoadMoreRef, t
  ]);

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

  return (
    <div ref={containerRef} className="h-full flex flex-col version-control-container">
      <GitContextSelector />
      {/* Branch and Actions Header */}
      <div className="px-4 py-2 border-b border-border bg-muted/30 flex items-center justify-between flex-shrink-0">
        {/* Branch Selector */}
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
            <GitBranch className="h-3 w-3" />
            {t('workspace.versionControl.actions.branch.label')}
          </span>
          <div className="relative">
          <button
            onClick={() => setShowBranchDropdown(!showBranchDropdown)}
            className="flex items-center gap-2 px-3 py-1 bg-background border border-border rounded-md hover:bg-muted/30 transition-colors"
          >
            <GitBranch className="h-3 w-3 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">{currentBranch}</span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </button>

          {/* Branch Dropdown */}
            {showBranchDropdown && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-background border border-border rounded-md shadow-lg z-10">
                <div className="py-1">
                  {branches.map((branch) => (
                    <button
                      key={branch.name}
                      onClick={() => handleBranchChange(branch.name)}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 ${
                        branch.name === currentBranch ? 'bg-primary/10 text-primary' : 'text-foreground'
                      }`}
                    >
                      <GitBranch className="h-3 w-3" />
                      {branch.displayName ?? branch.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Actions Menu */}
        <div className="relative">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowActionMenu(!showActionMenu)}
              className="p-1 hover:bg-muted/30 rounded transition-colors"
              aria-label={t('workspace.versionControl.actions.menu.label')}
              title={t('workspace.versionControl.actions.menu.label')}
            >
              <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
            </button>
          </div>

          {/* Actions Dropdown */}
          {showActionMenu && (
            <div className="absolute top-full right-0 mt-1 w-32 bg-background border border-border rounded-md shadow-lg z-10">
              <div className="py-1">
                <button
                  onClick={() => handleGitAction('pull')}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 text-foreground"
                >
                  <ArrowDown className="h-3 w-3" />
                  {t('workspace.versionControl.actions.pull.label')}
                </button>
                <button
                  onClick={() => handleGitAction('push')}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors flex items-center gap-2 text-foreground"
                >
                  <ArrowUp className="h-3 w-3" />
                  {t('workspace.versionControl.actions.push.label')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Commit Section */}
      <CommitForm
        onCommit={handleCommit}
        isLoading={commitMutation.isPending}
        stagedCount={stagedFiles.length}
        currentBranch={currentBranch}
      />

      {/* File Panels with Resizable Divider */}
      <div className="flex-1 flex flex-col min-h-0 file-panels-container">
        {/* Staged Changes Panel */}
        <div className="min-h-0 overflow-hidden" style={{ height: `${panelHeight}%` }}>
          {renderFileList('staged')}
        </div>

        {/* Resizable Divider */}
        <div
          className={`h-1 bg-border hover:bg-primary/50 cursor-row-resize transition-colors flex-shrink-0 ${
            isDragging ? 'bg-primary' : ''
          }`}
          onMouseDown={handleMouseDown}
        />

        {/* Unstaged Changes Panel */}
        <div className="min-h-0 overflow-hidden" style={{ height: `${100 - panelHeight}%` }}>
          {renderFileList('unstaged')}
        </div>
      </div>
    </div>
  );
};
