/**
 * 統一的檔案樹工具列組件
 * 
 * 提供標準的工具列佈局，支援：
 * - 左側自定義內容（如 Scope 選擇器）
 * - 右側操作按鈕（重新整理 + Actions 選單）
 * - 完全自定義渲染
 */

import React from 'react';
import { Plus, FolderPlus, Upload, RefreshCw, MoreVertical } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

export interface FileTreeToolbarProps {
  /** 左側自定義內容（如 Scope 選擇器） */
  leftContent?: React.ReactNode;
  
  /** 右側自定義內容（如額外的按鈕） */
  rightContent?: React.ReactNode;
  
  /** 新增檔案回調 */
  onCreateFile?: () => void;
  
  /** 新增資料夾回調 */
  onCreateFolder?: () => void;
  
  /** 上傳檔案回調 */
  onUpload?: () => void;
  
  /** 重新整理回調 */
  onRefresh?: () => void;
  
  /** 是否載入中 */
  isLoading?: boolean;
  
  /** 是否唯讀模式（隱藏操作按鈕） */
  isReadOnly?: boolean;
  
  /** 是否顯示 Actions 選單 */
  showActionsMenu?: boolean;
  
  /** 是否顯示重新整理按鈕 */
  showRefreshButton?: boolean;
  
  /** 自定義 className */
  className?: string;
  
  /** 完全自定義渲染（覆蓋默認佈局） */
  renderToolbar?: () => React.ReactNode;
}

export const FileTreeToolbar: React.FC<FileTreeToolbarProps> = ({
  leftContent,
  rightContent,
  onCreateFile,
  onCreateFolder,
  onUpload,
  onRefresh,
  isLoading = false,
  isReadOnly = false,
  showActionsMenu = true,
  showRefreshButton = true,
  className,
  renderToolbar,
}) => {
  // 如果提供了自定義渲染，直接使用
  if (renderToolbar) {
    return <div className={cn('p-2 border-b bg-muted/30', className)}>{renderToolbar()}</div>;
  }

  // 標準佈局
  return (
    <div className={cn('h-10 px-3 border-b bg-card flex items-center justify-between', className)}>
      <div className="flex items-center gap-2 flex-1">
        {/* 左側內容 */}
        {leftContent}
      </div>

      {/* 右側操作按鈕 */}
      {!isReadOnly && (
        <div className="flex items-center gap-1">
          {/* 重新整理按鈕 */}
          {showRefreshButton && onRefresh && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              onClick={onRefresh}
              disabled={isLoading}
              title="重新整理"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            </Button>
          )}

          {/* Actions 下拉選單 */}
          {showActionsMenu && (onCreateFile || onCreateFolder || onUpload) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  disabled={isLoading}
                  title="更多操作"
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onCreateFile && (
                  <DropdownMenuItem onClick={onCreateFile} className="text-xs">
                    <Plus className="h-3.5 w-3.5 mr-2" />
                    新增檔案
                  </DropdownMenuItem>
                )}
                {onCreateFolder && (
                  <DropdownMenuItem onClick={onCreateFolder} className="text-xs">
                    <FolderPlus className="h-3.5 w-3.5 mr-2" />
                    新增資料夾
                  </DropdownMenuItem>
                )}
                {onUpload && (
                  <DropdownMenuItem onClick={onUpload} className="text-xs">
                    <Upload className="h-3.5 w-3.5 mr-2" />
                    上傳檔案
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* 自定義右側內容 */}
          {rightContent}
        </div>
      )}
    </div>
  );
};

export default FileTreeToolbar;

