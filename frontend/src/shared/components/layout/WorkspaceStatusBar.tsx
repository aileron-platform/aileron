import React from 'react';
import { cn } from '@/shared/utils/cn';

export interface WorkspaceStatusBarProps {
  /** Left-aligned content (e.g. current path, active tab name, connection state). */
  left?: React.ReactNode;
  /** Right-aligned content (e.g. selection badge, clear-selection action). */
  right?: React.ReactNode;
  /** Custom class name. */
  className?: string;
  'data-testid'?: string;
}

export const WorkspaceStatusBar: React.FC<WorkspaceStatusBarProps> = ({
  left,
  right,
  className,
  'data-testid': dataTestId,
}) => (
  <div
    data-testid={dataTestId}
    className={cn(
      'flex h-8 shrink-0 items-center justify-between gap-2 border-t border-border bg-muted/30 px-3 text-xs text-muted-foreground',
      className,
    )}
  >
    <div className="flex min-w-0 flex-1 items-center gap-2">{left}</div>
    <div className="flex shrink-0 items-center gap-2">{right}</div>
  </div>
);
