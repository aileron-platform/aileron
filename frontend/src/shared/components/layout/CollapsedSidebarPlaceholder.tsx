import React from 'react';
import { LucideIcon } from 'lucide-react';
import { cn } from '../../utils/cn';
import { CollapsedSidebarIcon } from './CollapsedSidebarControls';

export interface CollapsedSidebarPlaceholderProps {
  icon: LucideIcon;
  label?: string;
  testId?: string;
  className?: string;
  iconWrapperClassName?: string;
  iconClassName?: string;
  labelClassName?: string;
}

export const CollapsedSidebarPlaceholder: React.FC<CollapsedSidebarPlaceholderProps> = ({
  icon: Icon,
  label,
  testId,
  className,
  iconWrapperClassName,
  iconClassName,
  labelClassName,
}) => {
  return (
    <div className={cn('flex flex-1 flex-col items-center pt-3', className)}>
      <CollapsedSidebarIcon
        icon={Icon}
        testId={testId}
        className={iconWrapperClassName}
        iconClassName={iconClassName}
      />
      {label ? (
        <span className={cn('mt-2 text-[11px] text-muted-foreground text-center leading-snug', labelClassName)}>
          {label}
        </span>
      ) : null}
    </div>
  );
};
