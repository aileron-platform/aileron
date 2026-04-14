/**
 * 標準檔案樹佈局組件
 * 
 * 提供統一的三段式佈局：
 * 1. 標題列（可選）
 * 2. 搜尋列
 * 3. 工具列
 * 4. 檔案樹內容
 */

import React from 'react';
import { ChevronLeft } from 'lucide-react';
import { FileTreeSearchBar } from '@/shared/components/file-tree';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

export interface StandardFileTreeLayoutProps {
  /** 標題文字 */
  title?: string;
  
  /** 標題圖標 */
  icon?: React.ReactNode;
  
  /** 是否收折 */
  isCollapsed?: boolean;
  
  /** 收折切換回調 */
  onToggleCollapse?: () => void;
  
  /** 搜尋值 */
  searchValue: string;
  
  /** 搜尋變更回調 */
  onSearchChange: (value: string) => void;
  
  /** 搜尋清除回調 */
  onSearchClear: () => void;
  
  /** 搜尋 placeholder */
  searchPlaceholder?: string;
  
  /** 是否顯示搜尋列 */
  showSearch?: boolean;
  
  /** 工具列內容 */
  toolbarContent?: React.ReactNode;
  
  /** 是否顯示工具列 */
  showToolbar?: boolean;
  
  /** 檔案樹內容 */
  children: React.ReactNode;
  
  /** 自定義 className */
  className?: string;
  
  /** Header 自定義 className */
  headerClassName?: string;
  
  /** 搜尋列自定義 className */
  searchClassName?: string;
  
  /** 工具列自定義 className */
  toolbarClassName?: string;
  
  /** 內容區自定義 className */
  contentClassName?: string;
}

export const StandardFileTreeLayout: React.FC<StandardFileTreeLayoutProps> = ({
  title,
  icon,
  isCollapsed = false,
  onToggleCollapse,
  searchValue,
  onSearchChange,
  onSearchClear,
  searchPlaceholder,
  showSearch = true,
  toolbarContent,
  showToolbar = true,
  children,
  className,
  headerClassName,
  searchClassName,
  toolbarClassName,
  contentClassName,
}) => {
  const { t } = useI18n();
  const resolvedSearchPlaceholder = searchPlaceholder ?? t('common.fileTree.search.placeholder');

  return (
    <div className={cn('flex h-full min-h-0 flex-col bg-background', className)}>
      {/* 標題列（可選） */}
      {(title || icon || onToggleCollapse) && (
        <div className={cn(
          'h-10 px-3 border-b border-sidebar-border bg-card flex items-center',
          isCollapsed ? 'justify-center' : 'justify-between',
          headerClassName
        )}>
          {/* 左側：標題和圖標（收折時隱藏） */}
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              {/* 圖標 */}
              {icon && <div className="flex-shrink-0">{icon}</div>}

              {/* 標題 */}
              {title && (
                <h2 className="text-sm font-medium text-sidebar-foreground">{title}</h2>
              )}
            </div>
          )}

          {/* 右側：收折按鈕 */}
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground transition"
              aria-label={isCollapsed ? '展開側欄' : '收折側欄'}
              title={isCollapsed ? '展開側欄' : '收折側欄'}
            >
              <ChevronLeft
                className={cn(
                  'w-3.5 h-3.5 transition-transform',
                  isCollapsed && 'rotate-180'
                )}
              />
            </button>
          )}
        </div>
      )}

      {/* 搜尋列 */}
      {showSearch && (
        <div className={searchClassName}>
          <FileTreeSearchBar
            value={searchValue}
            onChange={onSearchChange}
            onClear={onSearchClear}
            placeholder={resolvedSearchPlaceholder}
            containerClassName="border-b border-sidebar-border bg-sidebar-accent/20"
          />
        </div>
      )}

      {/* 工具列 */}
      {showToolbar && toolbarContent && (
        <div className={toolbarClassName}>
          {toolbarContent}
        </div>
      )}

      {/* 檔案樹內容 */}
      <div className={cn('flex flex-1 min-h-0 flex-col overflow-hidden bg-background', contentClassName)}>
        {children}
      </div>
    </div>
  );
};

export default StandardFileTreeLayout;
