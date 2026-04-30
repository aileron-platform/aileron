import React from 'react';
import { ChevronLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

export interface FileTreeToolbarProps {
  title: React.ReactNode;
  titleExtras?: React.ReactNode;
  actions?: React.ReactNode;
  multiSelectBar?: React.ReactNode;
  variant?: 'muted' | 'sidebar';
  className?: string;
  contentClassName?: string;
  titleClassName?: string;
  actionsClassName?: string;
  titleContainerClassName?: string;
  multiSelectBarClassName?: string;
  showCollapseButton?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  collapseTooltip?: string;
  leadingIcon?: React.ReactNode;
  collapsedIcon?: React.ReactNode;
  hideTitleWhenCollapsed?: boolean;
}

export const FileTreeToolbar: React.FC<FileTreeToolbarProps> = ({
  title,
  titleExtras,
  actions,
  multiSelectBar,
  variant = 'muted',
  className,
  contentClassName,
  titleClassName,
  actionsClassName,
  titleContainerClassName,
  multiSelectBarClassName,
  showCollapseButton = false,
  isCollapsed = false,
  onToggleCollapse,
  collapseTooltip,
  leadingIcon,
  collapsedIcon,
  hideTitleWhenCollapsed = false,
}) => {
  const containerClasses = cn(
    'flex flex-col flex-shrink-0',
    variant === 'sidebar' ? 'bg-card border-b border-sidebar-border' : 'bg-muted/30 border-b border-border',
    className,
  );

  const innerClasses = cn(
    'flex items-center justify-between gap-2 h-10 px-3 py-2',
    contentClassName,
  );

  const resolvedTitleClass = cn(
    'text-sm font-medium truncate',
    variant === 'sidebar' ? 'text-sidebar-foreground' : 'text-foreground',
    titleClassName,
  );

  const resolvedTitleContainerClass = cn(
    'flex items-center gap-1.5 min-w-0',
    isCollapsed && hideTitleWhenCollapsed ? 'justify-center' : '',
    titleContainerClassName,
  );

  const shouldHideTitle = hideTitleWhenCollapsed && isCollapsed;

  const resolvedLeadingIcon = shouldHideTitle ? collapsedIcon ?? null : leadingIcon ?? null;

  const resolvedActionsClass = cn('flex items-center gap-1', actionsClassName);

  const collapseButton =
    showCollapseButton && onToggleCollapse ? (
      <Button
        type="button"
        size="icon"
        variant="ghost"
        onClick={onToggleCollapse}
        className={cn(
          'h-7 w-7 text-foreground transition-transform',
          variant === 'sidebar' ? 'text-sidebar-foreground hover:bg-sidebar-accent' : 'hover:bg-muted/80',
        )}
        title={collapseTooltip}
      >
        <ChevronLeft className={cn('h-3.5 w-3.5 transition-transform', isCollapsed ? 'rotate-180' : '')} />
      </Button>
    ) : null;

  const multiSelectContainerClass = cn(
    'border-t',
    variant === 'sidebar' ? 'border-sidebar-border bg-sidebar-accent/50 px-3 py-1.5' : 'border-border bg-muted/50 px-3 py-1.5',
    multiSelectBarClassName,
  );

  return (
    <div className={containerClasses}>
      <div className={innerClasses}>
        <div className={resolvedTitleContainerClass}>
          {resolvedLeadingIcon ? <div className="flex-shrink-0">{resolvedLeadingIcon}</div> : null}
          {!shouldHideTitle ? (
            <>
              <span className={resolvedTitleClass}>{title}</span>
              {titleExtras}
            </>
          ) : null}
        </div>
        <div className={resolvedActionsClass}>
          {!isCollapsed ? actions : null}
          {collapseButton}
        </div>
      </div>
      {multiSelectBar ? <div className={multiSelectContainerClass}>{multiSelectBar}</div> : null}
    </div>
  );
};

export default FileTreeToolbar;
