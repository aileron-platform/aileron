import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

export interface FileTreeMultiSelectBarProps {
  selectedCount: number;
  totalCount: number;
  isAllSelected?: boolean;
  onToggleSelectAll?: () => void;
  primaryAction?: {
    label: string;
    onClick: () => void;
    disabled?: boolean;
    variant?: 'default' | 'destructive';
  };
  secondaryActions?: Array<{
    label: string;
    onClick: () => void;
    disabled?: boolean;
  }>;
  summaryText?: string;
  selectAllText?: string;
  unselectAllText?: string;
  className?: string;
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

      <span className="text-muted-foreground">{defaultSummaryText}</span>


      <div className="flex items-center gap-1">

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

