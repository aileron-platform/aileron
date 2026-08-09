import React from 'react';
import { cn } from '@/shared/utils/cn';

interface VersionControlFilePanelSectionProps {
  title: React.ReactNode;
  count: number;
  selectedCount?: number;
  actionIcon?: React.ReactNode;
  actionTitle?: string;
  onAction?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  actionDisabled?: boolean;
  actionBusy?: boolean;
  children: React.ReactNode;
  className?: string;
}

export const VersionControlFilePanelSection: React.FC<VersionControlFilePanelSectionProps> = ({
  title,
  count,
  selectedCount = 0,
  actionIcon,
  actionTitle,
  onAction,
  actionDisabled = false,
  actionBusy = false,
  children,
  className,
}) => (
  <div className={cn('flex h-full flex-col', className)}>
    <div className="flex h-10 flex-shrink-0 items-center justify-between border-b border-border bg-muted/30 px-3">
      <h4 className="flex min-w-0 items-center gap-2 text-sm font-medium text-foreground">
        <span className="truncate">{title}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{count}</span>
        {selectedCount > 0 && (
          <span className="rounded bg-primary/20 px-1.5 py-0.5 text-xs text-primary">
            {selectedCount}
          </span>
        )}
      </h4>
      {onAction && (
        <button
          className="flex h-6 w-6 items-center justify-center rounded p-0 transition-colors hover:bg-muted-foreground/10 disabled:opacity-50"
          onClick={onAction}
          disabled={actionDisabled}
          aria-busy={actionBusy}
          title={actionTitle}
          type="button"
        >
          {actionIcon}
        </button>
      )}
    </div>
    <div className="min-h-0 flex-1 overflow-y-auto p-2">
      {children}
    </div>
  </div>
);
