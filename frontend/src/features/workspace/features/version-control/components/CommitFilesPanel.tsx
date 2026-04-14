/**
 * CommitFilesPanel - 提交檔案面板組件
 *
 * 效能優化：
 * - 虛擬滾動處理大量檔案
 * - 固定高度項目提升效能
 */

import React, { useCallback } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import type { VersionControlFileChange } from '../types';
import { useI18n } from '@/shared/hooks/useI18n';
import { useFixedVirtualList } from '../hooks/useVirtualList';

interface CommitFilesPanelProps {
  files: VersionControlFileChange[];
  selectedFile?: VersionControlFileChange | null;
  onFileSelect?: (file: VersionControlFileChange | null) => void;
  isLoading?: boolean;
  error?: string | null;
}

const FILE_ITEM_HEIGHT = 40; // 每個檔案項目的固定高度

export const CommitFilesPanel: React.FC<CommitFilesPanelProps> = ({
  files,
  selectedFile,
  onFileSelect,
  isLoading = false,
  error = null,
}) => {
  const { t } = useI18n();

  // 虛擬滾動
  const { parentRef, virtualizer, virtualItems } = useFixedVirtualList({
    items: files,
    itemHeight: FILE_ITEM_HEIGHT,
    overscan: 5,
  });

  const getStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'M':
        return 'text-blue-500';
      case 'A':
        return 'text-green-500';
      case 'D':
        return 'text-red-500';
      case 'R':
        return 'text-yellow-500';
      default:
        return 'text-muted-foreground';
    }
  }, []);

  const getStatusText = useCallback((status: string) => {
    switch (status) {
      case 'M':
        return t('workspace.versionControl.commitFiles.status.modified');
      case 'A':
        return t('workspace.versionControl.commitFiles.status.added');
      case 'D':
        return t('workspace.versionControl.commitFiles.status.deleted');
      case 'R':
        return t('workspace.versionControl.commitFiles.status.renamed');
      default:
        return t('workspace.versionControl.commitFiles.status.unknown');
    }
  }, [t]);

  const handleFileClick = useCallback((file: VersionControlFileChange) => {
    onFileSelect?.(file);
  }, [onFileSelect]);

  // Loading 狀態
  if (isLoading) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-3 py-2 border-b border-border bg-muted/30">
          <h4 className="text-sm font-medium text-foreground">
            {t('workspace.versionControl.commitFiles.title')}
          </h4>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // Error 狀態
  if (error) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-3 py-2 border-b border-border bg-muted/30">
          <h4 className="text-sm font-medium text-foreground">
            {t('workspace.versionControl.commitFiles.title')}
          </h4>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-sm text-destructive">{error}</div>
        </div>
      </div>
    );
  }

  // Empty 狀態
  if (!files.length) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-3 py-2 border-b border-border bg-muted/30">
          <h4 className="text-sm font-medium text-foreground">
            {t('workspace.versionControl.commitFiles.title')}
          </h4>
        </div>
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <div className="text-center">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-sm">{t('workspace.versionControl.commitFiles.empty')}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-3 py-2 border-b border-border bg-muted/30 flex-shrink-0">
        <h4 className="text-sm font-medium text-foreground">
          {t('workspace.versionControl.commitFiles.title')}
          <span className="ml-2 text-xs text-muted-foreground">({files.length} files)</span>
        </h4>
      </div>

      {/* 虛擬滾動列表 */}
      <div ref={parentRef} className="flex-1 overflow-y-auto p-2 min-h-0">
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualItems().map((virtualRow) => {
            const file = files[virtualRow.index];
            if (!file) return null;

            const isSelected = selectedFile?.path === file.path;

            return (
              <div
                key={virtualRow.key}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <div
                  className={`px-3 py-2 rounded cursor-pointer transition-colors flex items-center justify-between ${
                    isSelected
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-muted/50 text-foreground'
                  }`}
                  onClick={() => handleFileClick(file)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <FileText className="h-4 w-4 flex-shrink-0" />
                    <span className="text-sm truncate">{file.path}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-xs font-medium ${getStatusColor(file.status)}`}>
                      {getStatusText(file.status)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

