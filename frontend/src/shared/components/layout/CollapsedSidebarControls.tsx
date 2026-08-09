import { ChevronLeft, type LucideIcon } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

export const collapsedSidebarActionClass =
  'rounded p-0.5 text-sidebar-foreground transition-colors hover:bg-sidebar-accent';

export const collapsedSidebarIconClass = 'h-3.5 w-3.5';

export interface SidebarCollapseToggleProps {
  collapsed: boolean;
  label: string;
  onClick: () => void;
  className?: string;
}

export const SidebarCollapseToggle = ({
  collapsed,
  label,
  onClick,
  className,
}: SidebarCollapseToggleProps) => (
  <button
    type="button"
    aria-label={label}
    title={label}
    onClick={onClick}
    className={cn(collapsedSidebarActionClass, className)}
  >
    <ChevronLeft className={cn(collapsedSidebarIconClass, 'transition-transform', collapsed && 'rotate-180')} aria-hidden="true" />
  </button>
);

export interface CollapsedSidebarIconProps {
  icon: LucideIcon;
  testId?: string;
  className?: string;
  iconClassName?: string;
}

export const CollapsedSidebarIcon = ({
  icon: Icon,
  testId,
  className,
  iconClassName,
}: CollapsedSidebarIconProps) => (
  <div data-testid={testId} className={cn(collapsedSidebarActionClass, 'inline-flex', className)}>
    <Icon className={cn(collapsedSidebarIconClass, 'text-current', iconClassName)} aria-hidden="true" />
  </div>
);
