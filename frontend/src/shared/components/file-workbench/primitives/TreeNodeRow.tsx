import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

export interface TreeNodeRowProps extends React.HTMLAttributes<HTMLDivElement> {
  depth: number;
  label: React.ReactNode;
  icon?: React.ReactNode;
  multiSelectIndicator?: React.ReactNode;
  trailingContent?: React.ReactNode;
  isSelected?: boolean;
  isMultiSelected?: boolean;
  isExpanded?: boolean;
  isDragging?: boolean;
  isDropTarget?: boolean;
  showExpandIcon?: boolean;
  expandIcon?: React.ReactNode;
  collapseIcon?: React.ReactNode;
  indentSize?: number;
  indentOffset?: number;
  onExpandToggle?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  disableContextMenu?: boolean;
  disableDragInteractions?: boolean;
}

export const TreeNodeRow = React.forwardRef<HTMLDivElement, TreeNodeRowProps>(
  (
    {
      depth,
      label,
      icon,
      multiSelectIndicator,
      trailingContent,
      isSelected = false,
      isMultiSelected = false,
      isExpanded = false,
      isDragging = false,
      isDropTarget = false,
      showExpandIcon = false,
      expandIcon,
      collapseIcon,
      indentSize = 16,
      indentOffset = 8,
      onExpandToggle,
      disableContextMenu = false,
      disableDragInteractions = false,
      className,
      style,
      onContextMenu,
      onDragStart,
      onDragEnd,
      onDragOver,
      onDragLeave,
      onDrop,
      draggable,
      ...rest
    },
    ref,
  ) => {
    const combinedClassName = cn(
      'flex items-center gap-2 rounded px-2 py-1 text-sm transition-colors cursor-pointer outline-none select-none',
      isSelected && !isMultiSelected && 'bg-primary/10 text-primary',
      isMultiSelected && 'bg-primary/20 text-primary',
      isDropTarget && 'bg-primary/30 ring-2 ring-primary',
      isDragging && 'opacity-50',
      className,
    );

    const resolvedExpandIcon = expandIcon ?? <ChevronRight className="h-4 w-4 text-muted-foreground" />;
    const resolvedCollapseIcon = collapseIcon ?? <ChevronDown className="h-4 w-4 text-muted-foreground" />;

    const handleContextMenu = (event: React.MouseEvent<HTMLDivElement>) => {
      if (disableContextMenu) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      onContextMenu?.(event);
    };

    return (
      <div
        {...rest}
        ref={ref}
        className={combinedClassName}
        style={{
          paddingLeft: indentOffset + depth * indentSize,
          ...style,
        }}
        onContextMenu={handleContextMenu}
        draggable={disableDragInteractions ? false : draggable}
        onDragStart={disableDragInteractions ? undefined : onDragStart}
        onDragEnd={disableDragInteractions ? undefined : onDragEnd}
        onDragOver={disableDragInteractions ? undefined : onDragOver}
        onDragLeave={disableDragInteractions ? undefined : onDragLeave}
        onDrop={disableDragInteractions ? undefined : onDrop}
      >
        {showExpandIcon ? (
          <button
            type="button"
            className="w-4 h-4 flex items-center justify-center text-muted-foreground"
            onClick={event => {
              event.stopPropagation();
              onExpandToggle?.(event);
            }}
          >
            {isExpanded ? resolvedCollapseIcon : resolvedExpandIcon}
          </button>
        ) : (
          <span className="w-4" />
        )}
        {icon ? <div className="flex-shrink-0">{icon}</div> : null}
        <div className="flex-1 min-w-0 truncate text-left">{label}</div>
        {trailingContent ? <div className="ml-2 flex-shrink-0">{trailingContent}</div> : null}
      </div>
    );
  },
);

TreeNodeRow.displayName = 'TreeNodeRow';
