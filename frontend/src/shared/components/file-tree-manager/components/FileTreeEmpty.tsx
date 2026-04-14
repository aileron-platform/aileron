/**
 * FileTreeEmpty 組件
 *
 * 檔案樹空狀態顯示組件
 */

import React from 'react';
import { FileX, Search, Folder } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

export interface FileTreeEmptyProps {
  /** 空狀態類型 */
  type?: 'empty' | 'search' | 'error';
  
  /** 標題 */
  title?: string;
  
  /** 描述 */
  description?: string;
  
  /** 圖示 */
  icon?: React.ReactNode;
  
  /** 操作按鈕 */
  action?: React.ReactNode;
  
  /** 自訂 className */
  className?: string;
}

export const FileTreeEmpty: React.FC<FileTreeEmptyProps> = ({
  type = 'empty',
  title,
  description,
  icon,
  action,
  className,
}) => {
  const { t } = useI18n();

  // 預設內容
  const defaultContent = {
    empty: {
      icon: <Folder className="h-12 w-12 text-muted-foreground/50" />,
      title: t('common.fileTree.empty.title'),
      description: t('common.fileTree.empty.description'),
    },
    search: {
      icon: <Search className="h-12 w-12 text-muted-foreground/50" />,
      title: t('common.fileTree.searchEmpty.title'),
      description: t('common.fileTree.searchEmpty.description'),
    },
    error: {
      icon: <FileX className="h-12 w-12 text-destructive/50" />,
      title: t('common.fileTree.error.title'),
      description: t('common.fileTree.error.description'),
    },
  };

  const content = defaultContent[type];
  const displayIcon = icon ?? content.icon;
  const displayTitle = title ?? content.title;
  const displayDescription = description ?? content.description;

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-12 px-4 text-center',
        className
      )}
    >
      <div className="mb-4">{displayIcon}</div>
      
      <h3 className="text-sm font-medium text-foreground mb-1">
        {displayTitle}
      </h3>
      
      {displayDescription && (
        <p className="text-xs text-muted-foreground mb-4 max-w-xs">
          {displayDescription}
        </p>
      )}
      
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
};

