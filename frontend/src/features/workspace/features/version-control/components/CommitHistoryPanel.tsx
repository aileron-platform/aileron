/**
 * CommitHistoryPanel - 提交歷史面板組件
 *
 * 效能優化：
 * - React Query Infinite Query 實現無限滾動
 * - TanStack Virtual 虛擬滾動
 * - 自動快取和背景更新
 * - 預載入下一頁
 */

import React, { useState, useCallback, useMemo } from 'react';
import { GitCommit, Loader2 } from 'lucide-react';
import { GitContextSelector } from './GitContextSelector';
import type { VersionControlCommitSummary, VersionControlFileChange } from '../types';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useCommitsInfiniteQuery, useCommitFilesQuery } from '../hooks/useVersionControlQueries';
import { isVersionControlNotInitializedError } from '../utils';
import { useI18n } from '@/shared/hooks/useI18n';
import { VersionControlHistorySidebar } from '@/shared/components/version-control';

interface CommitHistoryPanelProps {
  selectedCommitId?: string;
  onCommitSelect?: (commit: VersionControlCommitSummary | null) => void;
  onFileSelect?: (file: VersionControlFileChange | null) => void;
}

/**
 * CommitHistoryPanel 組件
 */
export const CommitHistoryPanel: React.FC<CommitHistoryPanelProps> = ({
  selectedCommitId: externalSelectedCommitId,
  onCommitSelect,
  onFileSelect,
}) => {
  const [internalSelectedCommitId, setInternalSelectedCommitId] = useState(externalSelectedCommitId || '');
  const [selectedFile, setSelectedFile] = useState<VersionControlFileChange | null>(null);

  const { t } = useI18n();
  const { workspaceRuntime, state } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const selectedGitContextId = state.versionControl.selectedGitContextId;

  // React Query Infinite Query
  const commitsQuery = useCommitsInfiniteQuery(
    { workspaceId, runtimeBaseUrl, contextId: selectedGitContextId },
    20 // pageSize
  );

  // Commit Files Query
  const filesQuery = useCommitFilesQuery(
    { workspaceId, runtimeBaseUrl, contextId: selectedGitContextId },
    internalSelectedCommitId
  );

  // 合併所有頁面的 commits
  const allCommits = useMemo(() => {
    return commitsQuery.data?.pages.flatMap(page => page.items ?? []) ?? [];
  }, [commitsQuery.data]);

  // 同步外部選中的 commit
  React.useEffect(() => {
    if (externalSelectedCommitId) {
      setInternalSelectedCommitId(externalSelectedCommitId);
    }
  }, [externalSelectedCommitId]);

  // 當選中的 commit 改變時，通知父組件
  React.useEffect(() => {
    if (internalSelectedCommitId) {
      const commit = allCommits.find(c => c.id === internalSelectedCommitId) ?? null;
      onCommitSelect?.(commit);
    }
  }, [internalSelectedCommitId, allCommits, onCommitSelect]);

  // 處理 commit 選擇
  const handleCommitSelect = useCallback((commit: VersionControlCommitSummary) => {
    setInternalSelectedCommitId(commit.id);
    setSelectedFile(null);
    onFileSelect?.(null);
  }, [onFileSelect]);

  // 處理檔案選擇
  const handleFileSelect = useCallback((file: VersionControlFileChange | null) => {
    setSelectedFile(file);
    onFileSelect?.(file);
  }, [onFileSelect]);

  // Loading 狀態
  if (commitsQuery.isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error 狀態
  if (commitsQuery.error) {
    if (isVersionControlNotInitializedError(commitsQuery.error)) {
      return (
        <div className="h-full flex items-center justify-center p-4">
          <div className="text-center max-w-sm">
            <GitCommit className="h-10 w-10 mx-auto mb-3 text-muted-foreground opacity-60" />
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
        <div className="text-sm text-destructive">{commitsQuery.error.message}</div>
      </div>
    );
  }

  return (
    <VersionControlHistorySidebar
      contextSlot={<GitContextSelector />}
      commits={allCommits}
      files={filesQuery.data ?? []}
      selectedCommitId={internalSelectedCommitId}
      selectedFile={selectedFile}
      isFilesLoading={filesQuery.isLoading}
      filesError={filesQuery.error?.message ?? null}
      onCommitSelect={handleCommitSelect}
      onFileSelect={handleFileSelect}
      hasMore={commitsQuery.hasNextPage}
      isLoadingMore={commitsQuery.isFetchingNextPage}
      onLoadMore={() => void commitsQuery.fetchNextPage()}
    />
  );
};
