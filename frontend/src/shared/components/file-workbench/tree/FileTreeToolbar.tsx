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
import { useI18n } from '@/shared/hooks/useI18n';

export interface FileTreeToolbarProps {
  leftContent?: React.ReactNode;
  rightContent?: React.ReactNode;
  onCreateFile?: () => void;
  onCreateFolder?: () => void;
  onUpload?: () => void;
  onRefresh?: () => void;
  isLoading?: boolean;
  isReadOnly?: boolean;
  showActionsMenu?: boolean;
  showRefreshButton?: boolean;
  className?: string;
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
  const { t } = useI18n();

  if (renderToolbar) {
    return <div className={cn('p-2 border-b bg-muted/30', className)}>{renderToolbar()}</div>;
  }

  return (
    <div className={cn('h-10 px-3 border-b bg-card flex items-center justify-between', className)}>
      <div className="flex items-center gap-2 flex-1">
        {leftContent}
      </div>

      {!isReadOnly && (
        <div className="flex items-center gap-1">
          {showRefreshButton && onRefresh && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              onClick={onRefresh}
              disabled={isLoading}
              title={t('common.fileTree.contextMenu.refresh')}
              aria-label={t('common.fileTree.contextMenu.refresh')}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
            </Button>
          )}

          {showActionsMenu && (onCreateFile || onCreateFolder || onUpload) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  disabled={isLoading}
                  title={t('common.fileTree.toolbar.moreActions')}
                  aria-label={t('common.fileTree.toolbar.moreActions')}
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onCreateFile && (
                  <DropdownMenuItem onClick={onCreateFile} className="text-xs">
                    <Plus className="h-3.5 w-3.5 mr-2" />
                    {t('common.fileTree.contextMenu.createFile')}
                  </DropdownMenuItem>
                )}
                {onCreateFolder && (
                  <DropdownMenuItem onClick={onCreateFolder} className="text-xs">
                    <FolderPlus className="h-3.5 w-3.5 mr-2" />
                    {t('common.fileTree.contextMenu.createFolder')}
                  </DropdownMenuItem>
                )}
                {onUpload && (
                  <DropdownMenuItem onClick={onUpload} className="text-xs">
                    <Upload className="h-3.5 w-3.5 mr-2" />
                    {t('common.fileTree.contextMenu.upload')}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {rightContent}
        </div>
      )}
    </div>
  );
};

export default FileTreeToolbar;
