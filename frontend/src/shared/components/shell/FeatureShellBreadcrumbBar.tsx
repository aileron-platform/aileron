import React from 'react';
import { ChevronRight, type LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/shared/utils/cn';

export interface FeatureShellBreadcrumbItem {
  label: React.ReactNode;
  to?: string;
}

export interface FeatureShellBreadcrumbBarProps {
  items: FeatureShellBreadcrumbItem[];
  title?: React.ReactNode;
  icon?: LucideIcon;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const FeatureShellBreadcrumbBar: React.FC<FeatureShellBreadcrumbBarProps> = ({
  items,
  title,
  icon: Icon,
  info,
  actions,
  className,
}) => {
  if (items.length === 0 && !title) {
    return null;
  }

  const lastIndex = items.length - 1;
  const isIntegratedHeader = title !== undefined;

  return (
    <nav
      aria-label="Breadcrumb"
      data-testid="feature-shell-breadcrumb-bar"
      className={cn(
        isIntegratedHeader
          ? 'flex h-10 w-full min-w-0 shrink-0 items-center justify-between overflow-hidden border-b border-border bg-card px-3'
          : 'flex h-8 shrink-0 items-center overflow-hidden border-b border-border bg-card px-3 text-xs text-muted-foreground',
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {Icon ? (
          <Icon
            data-testid="feature-shell-breadcrumb-icon"
            className="h-4 w-4 shrink-0 text-primary"
          />
        ) : null}
        {items.length > 0 ? (
          <ol className={cn(
            'flex min-w-0 items-center gap-1',
            isIntegratedHeader ? 'text-sm text-muted-foreground' : undefined,
          )}>
            {items.map((item, index) => {
              const isCurrent = index === lastIndex && !isIntegratedHeader;
              return (
                <li key={index} className="flex min-w-0 items-center gap-1">
                  {item.to && !isCurrent ? (
                    <Link
                      to={item.to}
                      className="max-w-48 truncate hover:text-foreground hover:underline"
                    >
                      {item.label}
                    </Link>
                  ) : (
                    <span
                      className={cn('max-w-56 truncate', isCurrent && 'font-medium text-foreground')}
                      aria-current={isCurrent ? 'page' : undefined}
                    >
                      {item.label}
                    </span>
                  )}
                  {isIntegratedHeader || !isCurrent ? (
                    <ChevronRight
                      data-testid="feature-shell-breadcrumb-separator"
                      className="h-3 w-3 shrink-0"
                      aria-hidden="true"
                    />
                  ) : null}
                </li>
              );
            })}
          </ol>
        ) : null}
        {title ? (
          <h2 className="min-w-0 truncate text-sm font-medium text-foreground">
            {title}
          </h2>
        ) : null}
        {info ? (
          <div className="min-w-0 flex-1 overflow-hidden">
            {info}
          </div>
        ) : null}
      </div>
      {actions ? (
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {actions}
        </div>
      ) : null}
    </nav>
  );
};
