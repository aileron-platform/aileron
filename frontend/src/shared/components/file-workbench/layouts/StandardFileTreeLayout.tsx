/**
 * 
 */

import React from 'react';
import { ChevronLeft } from 'lucide-react';
import { FileTreeSearchBar } from '@/shared/components/file-workbench/primitives';
import { cn } from '@/shared/utils/cn';
import { useI18n } from '@/shared/hooks/useI18n';

export interface StandardFileTreeLayoutProps {
  title?: string;
  
  icon?: React.ReactNode;
  
  isCollapsed?: boolean;
  
  onToggleCollapse?: () => void;
  
  searchValue: string;
  
  onSearchChange: (value: string) => void;
  
  onSearchClear: () => void;
  
  searchPlaceholder?: string;
  
  showSearch?: boolean;
  
  toolbarContent?: React.ReactNode;
  
  showToolbar?: boolean;
  
  children: React.ReactNode;
  
  className?: string;
  
  headerClassName?: string;
  
  searchClassName?: string;
  
  toolbarClassName?: string;
  
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

      {(title || icon || onToggleCollapse) && (
        <div className={cn(
          'h-10 px-3 border-b border-sidebar-border bg-card flex items-center',
          isCollapsed ? 'justify-center' : 'justify-between',
          headerClassName
        )}>

          {!isCollapsed && (
            <div className="flex items-center gap-2">

              {icon && <div className="flex-shrink-0">{icon}</div>}


              {title && (
                <h2 className="text-sm font-medium text-sidebar-foreground">{title}</h2>
              )}
            </div>
          )}


          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="p-0.5 hover:bg-sidebar-accent rounded text-sidebar-foreground transition"
              aria-label={isCollapsed ? t('common.fileTree.sidebar.expand') : t('common.fileTree.sidebar.collapse')}
              title={isCollapsed ? t('common.fileTree.sidebar.expand') : t('common.fileTree.sidebar.collapse')}
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


      {showToolbar && toolbarContent && (
        <div className={toolbarClassName}>
          {toolbarContent}
        </div>
      )}


      <div className={cn('flex flex-1 min-h-0 flex-col overflow-hidden bg-background', contentClassName)}>
        {children}
      </div>
    </div>
  );
};

export default StandardFileTreeLayout;
