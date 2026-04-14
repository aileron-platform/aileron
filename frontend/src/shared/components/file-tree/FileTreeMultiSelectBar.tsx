import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

export interface FileTreeMultiSelectBarProps {
  /** 已選擇的項目數量 */
  selectedCount: number;
  /** 總項目數量 */
  totalCount: number;
  /** 是否全選 */
  isAllSelected?: boolean;
  /** 全選/取消全選的回調 */
  onToggleSelectAll?: () => void;
  /** 主要操作按鈕（例如：下載、刪除） */
  primaryAction?: {
    label: string;
    onClick: () => void;
    disabled?: boolean;
    variant?: 'default' | 'destructive';
  };
  /** 次要操作按鈕 */
  secondaryActions?: Array<{
    label: string;
    onClick: () => void;
    disabled?: boolean;
  }>;
  /** 摘要文字（例如：已選擇 3 個檔案） */
  summaryText?: string;
  /** 全選按鈕文字 */
  selectAllText?: string;
  /** 取消全選按鈕文字 */
  unselectAllText?: string;
  /** 自定義樣式 */
  className?: string;
  /** 變體 */
  variant?: 'muted' | 'sidebar';
}

export const FileTreeMultiSelectBar: React.FC<FileTreeMultiSelectBarProps> = ({
  selectedCount,
  totalCount,
  isAllSelected,
  onToggleSelectAll,
  primaryAction,
  secondaryActions = [],
  summaryText,
  selectAllText,
  unselectAllText,
  className,
  variant = 'muted',
}) => {
  const { t } = useI18n();

  const containerClass = cn(
    'flex items-center justify-between text-xs',
    variant === 'sidebar' ? 'text-sidebar-foreground' : 'text-foreground',
    className,
  );

  const defaultSummaryText = summaryText || t('common.fileTree.multiSelect.selectedCount', { count: selectedCount });
  const computedIsAllSelected = isAllSelected ?? (selectedCount > 0 && selectedCount === totalCount);
  const selectAllLabel = selectAllText ?? t('common.fileTree.multiSelect.selectAll');
  const unselectAllLabel = unselectAllText ?? t('common.fileTree.multiSelect.unselectAll');

  return (
    <div className={containerClass}>
      {/* 左側：摘要 */}
      <span className="text-muted-foreground">{defaultSummaryText}</span>

      {/* 右側：操作按鈕 */}
      <div className="flex items-center gap-1">
        {/* 全選/取消全選按鈕 */}
        {onToggleSelectAll && (
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-xs"
            onClick={onToggleSelectAll}
          >
            {computedIsAllSelected ? unselectAllLabel : selectAllLabel}
          </Button>
        )}

        {/* 次要操作按鈕 */}
        {secondaryActions.map((action, index) => (
          <Button
            key={index}
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-xs"
            onClick={action.onClick}
            disabled={action.disabled}
          >
            {action.label}
          </Button>
        ))}

        {/* 主要操作按鈕 */}
        {primaryAction && (
          <Button
            size="sm"
            variant={primaryAction.variant || 'default'}
            className="h-6 px-2 text-xs"
            onClick={primaryAction.onClick}
            disabled={primaryAction.disabled ?? selectedCount === 0}
          >
            {primaryAction.label}
          </Button>
        )}
      </div>
    </div>
  );
};

export default FileTreeMultiSelectBar;

