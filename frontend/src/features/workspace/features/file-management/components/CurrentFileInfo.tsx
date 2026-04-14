/**
 * CurrentFileInfo - 當前檔案資訊顯示組件
 * 顯示當前活動檔案的名稱、類型等資訊
 */

import React from 'react';
import { Badge } from '../../../../../shared/components/ui/badge';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';

export const CurrentFileInfo: React.FC = () => {
  const { workspace } = useWorkspace();
  const { t } = useI18n();

  // 當前活動檔案
  const activeTab = workspace.openTabs.find(tab => tab.id === workspace.activeTabId);

  if (!activeTab) {
    return (
      <div className="text-xs text-muted-foreground">
        {t('workspace.fileManagement.info.empty')}
      </div>
    );
  }

  // 獲取檔案類型
  const getFileType = (fileName: string): string => {
    const extension = fileName.split('.').pop()?.toLowerCase();
    const typeMap: Record<string, string> = {
      'tsx': 'TypeScript React',
      'ts': 'TypeScript',
      'jsx': 'JavaScript React',
      'js': 'JavaScript',
      'json': 'JSON',
      'md': 'Markdown',
      'css': 'CSS',
      'scss': 'SCSS',
      'html': 'HTML',
      'py': 'Python',
      'java': 'Java',
      'cpp': 'C++',
      'c': 'C',
      'go': 'Go',
      'rs': 'Rust',
      'php': 'PHP',
      'rb': 'Ruby',
      'vue': 'Vue',
      'svelte': 'Svelte',
    };
    return typeMap[extension || ''] || 'Text';
  };

  // 獲取檔案大小顯示
  const getFileSizeDisplay = (content: string): string => {
    const bytes = new Blob([content]).size;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // 獲取行數
  const getLineCount = (content: string): number => {
    return content.split('\n').length;
  };

  const fileType = getFileType(activeTab.name);
  const fileSize = getFileSizeDisplay(activeTab.content);
  const lineCount = getLineCount(activeTab.content);

  return (
    <div className="flex items-center gap-2 px-3 py-1 bg-muted/50 rounded-lg">
      <div className="text-xs text-muted-foreground flex items-center gap-2">
        <span>{t('workspace.fileManagement.info.currentFile', { name: activeTab.name })}</span>
        <Badge variant="outline" className="text-xs">
          {fileType}
        </Badge>
        <span className="text-muted-foreground/70">
          {t('workspace.fileManagement.info.lineAndSize', { lines: lineCount, size: fileSize })}
        </span>
        {/* 修改狀態指示 */}
        {/* TODO: 實作檔案修改狀態檢查 */}
        {false && (
          <span className="text-primary">●</span>
        )}
      </div>
    </div>
  );
};

export default CurrentFileInfo;
