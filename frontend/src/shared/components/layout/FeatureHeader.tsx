/**
 */

import React from 'react';
import { ChevronRight, LucideIcon } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface FeatureHeaderProps {
  /** Feature title. */
  title: string;
  /** Feature icon. */
  icon: LucideIcon;
  /** Tool actions. */
  actions?: React.ReactNode;
  /** Additional metadata. */
  info?: React.ReactNode;
  /** Breadcrumb labels shown before the current title. */
  breadcrumbs?: React.ReactNode[];
  /** Custom class name. */
  className?: string;
  /** Whether the title and icon are hidden while actions stay visible. */
  isCollapsed?: boolean;
}

export const FeatureHeader: React.FC<FeatureHeaderProps> = ({
  title,
  icon: Icon,
  actions,
  info,
  breadcrumbs = [],
  className,
  isCollapsed = false,
}) => {
  const hasActions = Boolean(actions);

  return (
    <div className={cn(
      "h-10 w-full px-3 border-b border-border bg-card flex items-center",
      isCollapsed ? "justify-center" : hasActions ? "justify-between" : "justify-start",
      className
    )}>
      {!isCollapsed && (
        <div className={cn(
          "flex min-w-0 items-center gap-2",
          hasActions && "flex-1",
        )}>
          <Icon className="h-4 w-4 text-primary flex-shrink-0" />
          {breadcrumbs.length > 0 ? (
            <div className="hidden min-w-0 items-center gap-1 text-xs text-muted-foreground md:flex">
              {breadcrumbs.map((breadcrumb, index) => (
                <React.Fragment key={index}>
                  <span className="max-w-32 truncate">{breadcrumb}</span>
                  <ChevronRight className="h-3 w-3 shrink-0" aria-hidden="true" />
                </React.Fragment>
              ))}
            </div>
          ) : null}
          <h2 className="min-w-0 truncate text-sm font-medium text-foreground">{title}</h2>

          {info && (
            <div className={cn(
              "min-w-0 overflow-hidden",
              hasActions && "flex-1",
            )}>
              {info}
            </div>
          )}
        </div>
      )}

      {actions && (
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  );
};
