import React from 'react';
import { LucideIcon } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface CollapsedSidebarPlaceholderProps {
  icon: LucideIcon;
  label?: string;
  className?: string;
  iconClassName?: string;
  labelClassName?: string;
}

export const CollapsedSidebarPlaceholder: React.FC<CollapsedSidebarPlaceholderProps> = ({
  icon: Icon,
  label,
  className,
  iconClassName,
  labelClassName,
}) => {
  return (
    <div className={cn('flex flex-1 flex-col items-center pt-4', className)}>
      <Icon className={cn('h-4 w-4 text-sidebar-foreground', iconClassName)} />
      {label ? (
        <span className={cn('mt-2 text-[11px] text-muted-foreground text-center leading-snug', labelClassName)}>
          {label}
        </span>
      ) : null}
    </div>
  );
};

export default CollapsedSidebarPlaceholder;
