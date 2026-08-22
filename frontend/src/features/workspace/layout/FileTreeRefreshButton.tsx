import React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

interface FileTreeRefreshButtonProps {
  onRefresh: () => void;
  isRefreshing: boolean;
  disabled?: boolean;
}

export const FileTreeRefreshButton: React.FC<FileTreeRefreshButtonProps> = ({
  onRefresh,
  isRefreshing,
  disabled = false,
}) => {
  const { t } = useI18n();
  const label = t('common.fileTree.contextMenu.refresh');

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-7 w-7 p-0"
      onClick={onRefresh}
      disabled={disabled || isRefreshing}
      aria-label={label}
      title={label}
    >
      <RefreshCw
        aria-hidden="true"
        className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`}
      />
    </Button>
  );
};
