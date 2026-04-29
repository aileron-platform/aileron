import React, { useCallback } from 'react';
import { Clock, FileText, GitCommit, Loader2, Search, User } from 'lucide-react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlBranch, VersionControlCommitSummary, VersionControlFileChange } from '@/shared/types/versionControl';
import { Input } from '@/shared/components/ui/input';
import { VersionControlFileChangeItem } from './VersionControlFileChangeItem';
import { VersionControlResizablePanels } from './VersionControlResizablePanels';
import { VersionControlBranchSelector } from './VersionControlBranchSelector';

interface VersionControlHistorySidebarProps {
  contextSlot?: React.ReactNode;
  commits: VersionControlCommitSummary[];
  files: VersionControlFileChange[];
  selectedCommitId?: string | null;
  selectedFile?: VersionControlFileChange | null;
  isFilesLoading?: boolean;
  filesError?: string | null;
  onCommitSelect: (commit: VersionControlCommitSummary) => void;
  onFileSelect: (file: VersionControlFileChange | null) => void;
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
  hasMore?: boolean;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  branchFilter?: string | null;
  branches?: VersionControlBranch[];
  onBranchFilterChange?: (branch: string | null) => void;
}

const COMMIT_ITEM_HEIGHT = 100;

export const VersionControlHistorySidebar: React.FC<VersionControlHistorySidebarProps> = ({
  contextSlot,
  commits,
  files,
  selectedCommitId,
  selectedFile,
  isFilesLoading = false,
  filesError = null,
  onCommitSelect,
  onFileSelect,
  onLoadMore,
  isLoadingMore = false,
  hasMore = false,
  searchValue,
  onSearchChange,
  branchFilter,
  branches = [],
  onBranchFilterChange,
}) => {
  const { t } = useI18n();
  const commitListRef = React.useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: commits.length,
    getScrollElement: () => commitListRef.current,
    estimateSize: () => COMMIT_ITEM_HEIGHT,
    overscan: 5,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const lastItem = virtualItems[virtualItems.length - 1];
  const commitRows = virtualItems.length > 0
    ? virtualItems
    : commits.map((_, index) => ({
      key: index,
      index,
      start: index * COMMIT_ITEM_HEIGHT,
    }));

  React.useEffect(() => {
    if (
      lastItem &&
      lastItem.index >= commits.length - 1 &&
      hasMore &&
      !isLoadingMore
    ) {
      onLoadMore?.();
    }
  }, [commits.length, hasMore, isLoadingMore, lastItem, onLoadMore]);

  const formatTime = useCallback((timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffDays > 0) {
      return t('shared.versionControl.commitHistory.time.daysAgo', { count: diffDays });
    }
    if (diffHours > 0) {
      return t('shared.versionControl.commitHistory.time.hoursAgo', { count: diffHours });
    }
    if (diffMinutes > 0) {
      return t('shared.versionControl.commitHistory.time.minutesAgo', { count: diffMinutes });
    }
    return t('shared.versionControl.commitHistory.time.justNow');
  }, [t]);

  const renderCommitList = (
    <div className="h-full flex flex-col">
      <div className="flex flex-shrink-0 flex-col gap-2 border-b border-border bg-muted/30 p-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="truncate text-sm font-medium text-foreground">
            {t('shared.versionControl.commitHistory.title')}
            <span className="ml-2 text-xs text-muted-foreground">
              ({t('shared.versionControl.commitHistory.commitCount', { count: commits.length })})
            </span>
          </h4>
        </div>
        {(onSearchChange || onBranchFilterChange) && (
          <div className="grid gap-2">
            {onSearchChange && (
              <div className="relative min-w-0">
                <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchValue ?? ''}
                  onChange={(event) => onSearchChange(event.target.value)}
                  placeholder={t('shared.versionControl.commitHistory.filters.searchPlaceholder')}
                  className="h-8 min-w-0 pl-7"
                  aria-label={t('shared.versionControl.commitHistory.filters.searchAriaLabel')}
                />
              </div>
            )}
          {onBranchFilterChange && (
            <VersionControlBranchSelector
              branches={[
                { name: '', displayName: t('shared.versionControl.commitHistory.filters.allBranches') },
                ...branches,
              ]}
              currentBranch={branchFilter ?? ''}
              onBranchChange={(branch) => onBranchFilterChange(branch || null)}
              hideLabel
              className="w-full"
              buttonClassName="h-8 w-full justify-between px-2"
            />
          )}
          </div>
        )}
      </div>
      {commits.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
          {t('shared.versionControl.commitHistory.empty')}
        </div>
      ) : (
        <div ref={commitListRef} className="flex-1 overflow-y-auto min-h-0">
          <div
            style={{
              height: `${virtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative',
            }}
          >
            {commitRows.map((virtualRow) => {
              const commit = commits[virtualRow.index];
              if (!commit) {
                return null;
              }

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
                    <button
                      type="button"
                      className={`w-full p-3 rounded cursor-pointer transition-colors text-left ${
                        selectedCommitId === commit.id ? 'bg-muted/70' : 'hover:bg-muted/50'
                      }`}
                      onClick={() => onCommitSelect(commit)}
                    >
                      <div className="mb-2">
                        <div className="text-sm font-medium text-foreground mb-1 line-clamp-2">
                          {commit.message}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <GitCommit className="w-3 h-3" />
                          <span className="font-mono">{commit.id.substring(0, 7)}</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <div className="flex items-center gap-1 min-w-0">
                          <User className="w-3 h-3 shrink-0" />
                          <span className="truncate">{commit.author}</span>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Clock className="w-3 h-3" />
                          <span>{formatTime(commit.timestamp)}</span>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          {isLoadingMore && (
            <div className="py-4 flex items-center justify-center">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderFilesPanel = (
    <div className="h-full flex flex-col">
      <div className="flex h-10 flex-shrink-0 items-center border-b border-border bg-muted/30 px-3">
        <h4 className="truncate text-sm font-medium text-foreground">
          {t('shared.versionControl.commitFiles.title')}
          {files.length > 0 && (
            <span className="ml-2 text-xs text-muted-foreground">
              ({t('shared.versionControl.commitFiles.fileCount', { count: files.length })})
            </span>
          )}
        </h4>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-2">
        {isFilesLoading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : filesError ? (
          <div className="flex h-full items-center justify-center text-sm text-destructive">
            {filesError}
          </div>
        ) : files.length === 0 ? (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-sm">
                {selectedCommitId
                  ? t('shared.versionControl.commitFiles.empty')
                  : t('shared.versionControl.commitHistory.selectPrompt')}
              </p>
            </div>
          </div>
        ) : (
          files.map((file) => (
            <VersionControlFileChangeItem
              key={`commit:${selectedCommitId}:${file.path}`}
              file={file}
              type="unstaged"
              isSelected={selectedFile?.path === file.path}
              isMultiSelected={false}
              selectedCount={1}
              onSelect={() => onFileSelect(file)}
              onStageToggle={() => undefined}
              readOnly
            />
          ))
        )}
      </div>
    </div>
  );

  return (
    <div className="h-full flex flex-col">
      {contextSlot}
      <VersionControlResizablePanels
        initialTopPercent={60}
        top={renderCommitList}
        bottom={renderFilesPanel}
      />
    </div>
  );
};

export default VersionControlHistorySidebar;
