/**
 * CommitHistoryPanel - 提交歷史面板組件
 *
 * 效能優化：
 * - React Query Infinite Query 實現無限滾動
 * - TanStack Virtual 虛擬滾動
 * - 自動快取和背景更新
 * - 預載入下一頁
 */

import React, { useState, useRef, useCallback, useMemo } from 'react';
import { GitCommit, User, Clock, Loader2 } from 'lucide-react';
import { CommitFilesPanel } from './CommitFilesPanel';
import type { VersionControlCommitSummary, VersionControlFileChange } from '../types';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useCommitsInfiniteQuery, useCommitFilesQuery } from '../hooks/useVersionControlQueries';
import { useVirtualizer } from '@tanstack/react-virtual';

interface CommitHistoryPanelProps {
  selectedCommitId?: string;
  onCommitSelect?: (commit: VersionControlCommitSummary | null) => void;
  onFileSelect?: (file: VersionControlFileChange | null) => void;
}

const COMMIT_ITEM_HEIGHT = 100; // 每個 commit 項目的估計高度

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
  const [panelHeight, setPanelHeight] = useState(60);
  const [isDragging, setIsDragging] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const commitListRef = useRef<HTMLDivElement>(null);
  const { t } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const workspaceId = workspaceRuntime.workspaceId ?? '';

  // React Query Infinite Query
  const commitsQuery = useCommitsInfiniteQuery(
    { workspaceId, runtimeBaseUrl },
    20 // pageSize
  );

  // Commit Files Query
  const filesQuery = useCommitFilesQuery(
    { workspaceId, runtimeBaseUrl },
    internalSelectedCommitId
  );

  // 合併所有頁面的 commits
  const allCommits = useMemo(() => {
    return commitsQuery.data?.pages.flatMap(page => page.items ?? []) ?? [];
  }, [commitsQuery.data]);

  // 虛擬滾動
  const virtualizer = useVirtualizer({
    count: allCommits.length,
    getScrollElement: () => commitListRef.current,
    estimateSize: () => COMMIT_ITEM_HEIGHT,
    overscan: 5,
  });

  // 無限滾動：當接近底部時載入更多
  const virtualItems = virtualizer.getVirtualItems();
  const lastItem = virtualItems[virtualItems.length - 1];

  React.useEffect(() => {
    if (!lastItem) return;

    if (
      lastItem.index >= allCommits.length - 1 &&
      commitsQuery.hasNextPage &&
      !commitsQuery.isFetchingNextPage
    ) {
      commitsQuery.fetchNextPage();
    }
  }, [lastItem, allCommits.length, commitsQuery]);

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
  const handleCommitSelect = useCallback((commitId: string) => {
    setInternalSelectedCommitId(commitId);
    setSelectedFile(null);
    onFileSelect?.(null);
  }, [onFileSelect]);

  // 處理檔案選擇
  const handleFileSelect = useCallback((file: VersionControlFileChange | null) => {
    setSelectedFile(file);
    onFileSelect?.(file);
  }, [onFileSelect]);

  // 處理拖拽調整面板高度
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

  // 格式化時間
  const formatTime = useCallback((timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffDays > 0) {
      return t('workspace.versionControl.commitHistory.time.daysAgo', { count: diffDays });
    }
    if (diffHours > 0) {
      return t('workspace.versionControl.commitHistory.time.hoursAgo', { count: diffHours });
    }
    if (diffMinutes > 0) {
      return t('workspace.versionControl.commitHistory.time.minutesAgo', { count: diffMinutes });
    }
    return t('workspace.versionControl.commitHistory.time.justNow');
  }, [t]);

  const formatCommitId = useCallback((id: string) => id.substring(0, 7), []);

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
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-destructive">{commitsQuery.error.message}</div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full flex flex-col">
      {/* 上方：Commit 歷史列表 */}
      <div className="min-h-0 overflow-hidden" style={{ height: `${panelHeight}%` }}>
        <div className="h-full flex flex-col">
          <div className="px-3 py-2 border-b border-border bg-muted/30 flex-shrink-0">
            <h4 className="text-sm font-medium text-foreground">
              {t('workspace.versionControl.commitHistory.title')}
              <span className="ml-2 text-xs text-muted-foreground">
                ({allCommits.length} commits)
              </span>
            </h4>
          </div>

          {/* 虛擬滾動列表 */}
          <div ref={commitListRef} className="flex-1 overflow-y-auto min-h-0">
            <div
              style={{
                height: `${virtualizer.getTotalSize()}px`,
                width: '100%',
                position: 'relative',
              }}
            >
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const commit = allCommits[virtualRow.index];
                if (!commit) return null;

                return (
                  <div
                    key={virtualRow.key}
                    data-index={virtualRow.index}
                    ref={virtualizer.measureElement}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <div className="px-2 py-1">
                      <div
                        className={`p-3 rounded cursor-pointer transition-colors ${
                          internalSelectedCommitId === commit.id
                            ? 'bg-muted/70'
                            : 'hover:bg-muted/50'
                        }`}
                        onClick={() => handleCommitSelect(commit.id)}
                      >
                        {/* 提交訊息 */}
                        <div className="mb-2">
                          <div className="text-sm font-medium text-foreground mb-1 line-clamp-2">
                            {commit.message}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <GitCommit className="w-3 h-3" />
                            <span className="font-mono">{formatCommitId(commit.id)}</span>
                          </div>
                        </div>

                        {/* 作者和時間 */}
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            <span>{commit.author}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            <span>{formatTime(commit.timestamp)}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 載入更多指示器 */}
            {commitsQuery.isFetchingNextPage && (
              <div className="py-4 flex items-center justify-center">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Resizable Divider */}
      <div
        className={`h-1 bg-border hover:bg-primary/50 cursor-row-resize transition-colors flex-shrink-0 ${
          isDragging ? 'bg-primary' : ''
        }`}
        onMouseDown={handleMouseDown}
      />

      {/* 下方：Commit 檔案列表 */}
      <div className="min-h-0 overflow-hidden" style={{ height: `${100 - panelHeight}%` }}>
        <CommitFilesPanel
          files={filesQuery.data ?? []}
          isLoading={filesQuery.isLoading}
          error={filesQuery.error?.message ?? null}
          selectedFile={selectedFile}
          onFileSelect={handleFileSelect}
        />
      </div>
    </div>
  );
};

