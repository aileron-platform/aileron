/**
 *
 */

import React from 'react';
import { FileX, Search, Folder, type LucideIcon } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { EmptyState } from '@/shared/components/ui/empty-state';

export interface FileTreeEmptyProps {
  type?: 'empty' | 'search' | 'error';
  
  title?: string;
  
  description?: string;
  
  icon?: LucideIcon;
  
  action?: React.ReactNode;
  
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


  const defaultContent = {
    empty: {
      icon: Folder,
      title: t('common.fileTree.empty.title'),
      description: t('common.fileTree.empty.description'),
    },
    search: {
      icon: Search,
      title: t('common.fileTree.searchEmpty.title'),
      description: t('common.fileTree.searchEmpty.description'),
    },
    error: {
      icon: FileX,
      title: t('common.fileTree.error.title'),
      description: t('common.fileTree.error.description'),
    },
  };

  const content = defaultContent[type];
  const displayIcon = icon ?? content.icon;
  const displayTitle = title ?? content.title;
  const displayDescription = description ?? content.description;

  return (
    <EmptyState
      icon={displayIcon}
      title={displayTitle}
      description={displayDescription}
      action={action}
      tone={type === 'error' ? 'destructive' : 'default'}
      className={className}
    />
  );
};
