import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

export interface VersionControlModeRailItem {
  id: string;
  label: string;
  icon: LucideIcon;
  count?: number;
}

interface VersionControlModeRailProps {
  items: VersionControlModeRailItem[];
  activeId: string;
  onChange: (id: string) => void;
  title?: string;
  titleIcon?: LucideIcon;
  footer?: React.ReactNode;
}

export const VersionControlModeRail: React.FC<VersionControlModeRailProps> = ({
  items,
  activeId,
  onChange,
  title,
  titleIcon: TitleIcon,
  footer,
}) => (
  <div className="flex h-full min-h-0 flex-col bg-background">
    {title ? (
      <div className="flex h-10 flex-shrink-0 items-center gap-2 border-b border-sidebar-border bg-card px-3 text-sm font-medium text-sidebar-foreground">
        {TitleIcon ? <TitleIcon className="h-4 w-4 text-sidebar-primary" /> : null}
        {title}
      </div>
    ) : null}
    <nav className="min-h-0 flex-1 overflow-y-auto p-2">
      {items.map((item) => {
        const Icon = item.icon;
        const active = item.id === activeId;
        return (
          <button
            key={item.id}
            type="button"
            className={cn(
              'mb-1 flex w-full items-center rounded-lg p-2 text-sm transition-colors',
              active
                ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-sm'
                : 'text-sidebar-foreground hover:bg-sidebar-accent',
            )}
            onClick={() => onChange(item.id)}
          >
            <span className="flex min-w-0 flex-1 items-center">
              <Icon className="h-4 w-4 shrink-0" />
              <span className="ml-2 truncate text-left">{item.label}</span>
            </span>
            {typeof item.count === 'number' ? (
              <span
                className={cn(
                  'ml-2 min-w-5 rounded-full px-1.5 py-0.5 text-center text-[11px] leading-none',
                  active
                    ? 'bg-sidebar-primary-foreground/20 text-sidebar-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
    {footer ? <div className="mt-auto border-t border-border p-2">{footer}</div> : null}
  </div>
);

export default VersionControlModeRail;
