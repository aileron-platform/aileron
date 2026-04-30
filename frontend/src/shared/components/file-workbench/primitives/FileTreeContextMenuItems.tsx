import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { DropdownMenuItem } from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

export interface FileTreeContextMenuAction {
  key: string;
  label: React.ReactNode;
  onSelect: () => void;
  icon?: LucideIcon;
  disabled?: boolean;
  variant?: 'default' | 'destructive';
  showDividerBefore?: boolean;
}

export interface FileTreeContextMenuItemsProps {
  items: FileTreeContextMenuAction[];
  variant?: 'panel' | 'dropdown';
  onItemSelect?: (action: FileTreeContextMenuAction) => void;
}

export const FileTreeContextMenuItems: React.FC<FileTreeContextMenuItemsProps> = ({
  items,
  variant = 'panel',
  onItemSelect,
}) => {
  return (
    <>
      {items.map((item, index) => {
        const Icon = item.icon;
        const content = (
          <>
            {Icon ? <Icon className="h-4 w-4" /> : null}
            <span className="flex-1 text-left text-sm">{item.label}</span>
          </>
        );

        const sharedClassName = cn(
          'flex w-full items-center gap-2 text-foreground',
          item.variant === 'destructive' ? 'text-destructive focus:text-destructive' : '',
        );

        const handleSelect = () => {
          if (item.disabled) {
            return;
          }
          onItemSelect?.(item);
          item.onSelect();
        };

        const nodes: React.ReactNode[] = [];
        if (item.showDividerBefore && index > 0) {
          nodes.push(
            <div key={`divider-${item.key}`} className="my-1 h-px bg-border" />,
          );
        }

        if (variant === 'dropdown') {
          nodes.push(
            <DropdownMenuItem
              key={item.key}
              onClick={event => {
                event.preventDefault();
                handleSelect();
              }}
              disabled={item.disabled}
              className={cn(sharedClassName, 'text-sm')}
            >
              {content}
            </DropdownMenuItem>,
          );
        } else {
          nodes.push(
            <button
              key={item.key}
              type="button"
              onClick={handleSelect}
              disabled={item.disabled}
              className={cn(
                sharedClassName,
                'px-3 py-2 text-left text-sm transition-colors hover:bg-muted/60 disabled:cursor-not-allowed disabled:opacity-60',
              )}
            >
              {content}
            </button>,
          );
        }

        return <React.Fragment key={`fragment-${item.key}`}>{nodes}</React.Fragment>;
      })}
    </>
  );
};

export default FileTreeContextMenuItems;
